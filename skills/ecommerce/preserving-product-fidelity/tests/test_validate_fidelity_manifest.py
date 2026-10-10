import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional


TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
VALIDATOR = TESTS.parent / "scripts" / "validate_fidelity_manifest.py"


def run_validator(fixture_name: str) -> subprocess.CompletedProcess[str]:
    return run_validator_path(FIXTURES / fixture_name)


def run_validator_path(manifest_path: Path, emit_contract: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR)]
        + (["--emit-prompt-contract"] if emit_contract else [])
        + [str(manifest_path)],
        text=True,
        capture_output=True,
        check=False,
    )


def valid_manifest() -> dict:
    return json.loads(
        (FIXTURES / "valid-deterministic-composite.json").read_text(encoding="utf-8")
    )


def evidence_generation_manifest() -> dict:
    return json.loads(
        (FIXTURES / "accept-evidence-constrained-generation.json").read_text(
            encoding="utf-8"
        )
    )


def run_validator_data(data: dict, emit_contract: bool = False) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        manifest_path = Path(temporary_directory) / "manifest.json"
        manifest_path.write_text(json.dumps(data), encoding="utf-8")
        return run_validator_path(manifest_path, emit_contract=emit_contract)


class ValidateFidelityManifestTests(unittest.TestCase):
    def assertAccepted(self, result: subprocess.CompletedProcess[str]) -> dict:
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertIs(payload["valid"], True)
        self.assertEqual(payload["errors"], [])
        return payload

    def assertRejected(
        self,
        result: subprocess.CompletedProcess[str],
        expected_error_code: str,
        expected_effective_status: Optional[str] = None,
    ) -> dict:
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIs(payload["valid"], False)
        if expected_effective_status is None:
            self.assertIn(
                payload["effective_delivery_status"],
                ("blocked", "rejected"),
            )
        else:
            self.assertEqual(
                payload["effective_delivery_status"], expected_effective_status
            )
        self.assertIn(
            expected_error_code,
            [error["code"] for error in payload["errors"]],
        )
        return payload

    def assertRejectedCodes(
        self, result: subprocess.CompletedProcess[str], expected_error_codes: list[str]
    ) -> dict:
        payload = self.assertRejected(result, expected_error_codes[0])
        self.assertEqual(
            [error["code"] for error in payload["errors"]],
            expected_error_codes,
        )
        return payload

    def test_valid_deterministic_composite_passes(self):
        result = run_validator("valid-deterministic-composite.json")

        payload = self.assertAccepted(result)

        self.assertEqual(payload["effective_delivery_status"], "verified_composite")

    def test_verified_composite_requires_landmark_qa_for_all_visible_identity_records(self):
        result = run_validator("reject-incomplete-landmark-qa.json")

        self.assertRejected(result, "MISSING_LANDMARK_QA")

    def test_verified_composite_rejects_protected_product_pixel_drift(self):
        result = run_validator("reject-protected-pixel-drift.json")

        self.assertRejected(
            result,
            "PROTECTED_PRODUCT_PIXEL_DRIFT",
            expected_effective_status="rejected",
        )

    def test_verified_composite_requires_complete_well_formed_qa_proof(self):
        malformed_qa_values = (None, [], "pass")
        for qa in malformed_qa_values:
            with self.subTest(qa=repr(qa)):
                fixture = valid_manifest()
                fixture["qa"] = qa

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_QA")

        fixture = valid_manifest()
        fixture["qa"]["original_resolution_comparison"] = "true"

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_ORIGINAL_RESOLUTION_COMPARISON")

        fixture = valid_manifest()
        fixture["qa"]["overall_verdict"] = "pending"

        result = run_validator_data(fixture)

        self.assertRejected(result, "QA_OVERALL_VERDICT_NOT_PASS")

    def test_landmark_qa_requires_unique_source_backed_pass_records(self):
        fixture = valid_manifest()
        fixture["qa"]["landmark_records"].append(
            dict(fixture["qa"]["landmark_records"][0])
        )

        result = run_validator_data(fixture)

        self.assertRejected(result, "DUPLICATE_LANDMARK_QA")

        fixture = valid_manifest()
        fixture["qa"]["landmark_records"][0]["source_id"] = "target-model-scene"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_LANDMARK_QA_SOURCE")

        fixture = valid_manifest()
        fixture["qa"]["landmark_records"][0]["normalized_region"] = [0.8, 0.2, 0.3, 0.4]

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_LANDMARK_QA_REGION")

    def test_identity_landmark_failure_rejects_the_delivery(self):
        fixture = valid_manifest()
        fixture["qa"]["landmark_records"][0]["verdict"] = "fail"

        result = run_validator_data(fixture)

        self.assertRejected(
            result,
            "IDENTITY_LANDMARK_QA_FAILED",
            expected_effective_status="rejected",
        )

    def test_duplicate_landmark_record_cannot_hide_a_failed_identity_verdict(self):
        fixture = valid_manifest()
        failed_duplicate = dict(fixture["qa"]["landmark_records"][0])
        failed_duplicate["verdict"] = "fail"
        fixture["qa"]["landmark_records"].append(failed_duplicate)

        result = run_validator_data(fixture)

        payload = self.assertRejected(
            result,
            "DUPLICATE_LANDMARK_QA",
            expected_effective_status="rejected",
        )
        self.assertIn(
            "IDENTITY_LANDMARK_QA_FAILED",
            [error["code"] for error in payload["errors"]],
        )

    def test_landmark_and_protected_pixel_qa_verdicts_have_closed_string_enums(self):
        fixture = valid_manifest()
        fixture["qa"]["landmark_records"][0]["verdict"] = []

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_LANDMARK_QA_VERDICT")

        fixture = valid_manifest()
        fixture["qa"]["protected_pixels"]["verdict"] = "pending"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PROTECTED_PIXEL_QA")

    def test_protected_pixel_qa_requires_complete_comparison_coverage(self):
        fixture = valid_manifest()
        fixture["qa"]["protected_pixels"]["compared_region_ids"] = []

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_LANDMARK_QA")

    def test_facts_require_closed_commercial_importance_labels(self):
        fixture = valid_manifest()
        fixture["facts"][0].pop("commercial_importance")

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_COMMERCIAL_IMPORTANCE")

        for malformed_importance in (None, [], {}, "HIGH"):
            with self.subTest(commercial_importance=repr(malformed_importance)):
                fixture = valid_manifest()
                fixture["facts"][0]["commercial_importance"] = malformed_importance

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_COMMERCIAL_IMPORTANCE")

    def test_explicit_identity_landmarks_remain_required_when_fact_is_low_importance(self):
        fixture = valid_manifest()
        fixture["facts"][1]["commercial_importance"] = "low"
        fixture["qa"]["landmark_records"] = [
            record
            for record in fixture["qa"]["landmark_records"]
            if record["landmark_id"] != "front-clasp"
        ]

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_LANDMARK_QA")

    def test_malformed_landmarks_cannot_hide_protected_pixel_drift(self):
        fixture = valid_manifest()
        fixture["qa"]["landmark_records"] = None
        fixture["qa"]["protected_pixels"]["verdict"] = "drift"

        result = run_validator_data(fixture)

        payload = self.assertRejected(
            result,
            "INVALID_LANDMARK_QA",
            expected_effective_status="rejected",
        )
        self.assertIn(
            "PROTECTED_PRODUCT_PIXEL_DRIFT",
            [error["code"] for error in payload["errors"]],
        )

    def test_failed_landmark_retains_rejection_with_invalid_source_or_region(self):
        fixture = valid_manifest()
        fixture["qa"]["landmark_records"][0]["verdict"] = "fail"
        fixture["qa"]["landmark_records"][0]["source_id"] = "target-model-scene"

        result = run_validator_data(fixture)

        payload = self.assertRejected(
            result,
            "IDENTITY_LANDMARK_QA_FAILED",
            expected_effective_status="rejected",
        )
        self.assertIn(
            "INVALID_LANDMARK_QA_SOURCE",
            [error["code"] for error in payload["errors"]],
        )

        fixture = valid_manifest()
        fixture["qa"]["landmark_records"][0]["verdict"] = "fail"
        fixture["qa"]["landmark_records"][0]["normalized_region"] = [0.8, 0.2, 0.3, 0.4]

        result = run_validator_data(fixture)

        payload = self.assertRejected(
            result,
            "IDENTITY_LANDMARK_QA_FAILED",
            expected_effective_status="rejected",
        )
        self.assertIn(
            "INVALID_LANDMARK_QA_REGION",
            [error["code"] for error in payload["errors"]],
        )

    def test_verified_composite_requires_both_identity_lists_and_never_exports_when_missing(self):
        fixture = valid_manifest()
        del fixture["scene_plan"]["visible_identity_critical_regions"]
        fixture["qa"]["landmark_records"] = []

        payload = self.assertRejected(
            run_validator_data(fixture, emit_contract=True),
            "MISSING_IDENTITY_REGION_LIST",
        )
        self.assertNotIn("prompt_contract", payload)

        fixture = valid_manifest()
        fixture["scene_plan"]["visible_identity_critical_regions"] = []
        fixture["scene_plan"]["redrawn_identity_critical_regions"] = []
        fixture["qa"]["landmark_records"] = []

        payload = self.assertRejected(
            run_validator_data(fixture, emit_contract=True),
            "MISSING_IDENTITY_LANDMARK_DECLARATION",
        )
        self.assertNotIn("prompt_contract", payload)

    def test_visible_attachment_topology_must_be_identity_tracked_and_qa_covered(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["visible_identity_critical_regions"].remove(
            "front-chain-path"
        )
        fixture["qa"]["landmark_records"] = [
            record
            for record in fixture["qa"]["landmark_records"]
            if record["landmark_id"] != "front-chain-path"
        ]

        payload = self.assertRejected(
            run_validator_data(fixture, emit_contract=True),
            "ATTACHMENT_TOPOLOGY_NOT_IDENTITY_TRACKED",
        )
        self.assertNotIn("prompt_contract", payload)

    def test_explicit_draft_qa_failures_reject_and_do_not_export(self):
        fixture = valid_manifest()
        fixture["delivery_status"] = "unverified_draft"
        fixture["qa"]["landmark_records"][0]["verdict"] = "mismatch"
        fixture["qa"]["protected_pixels"]["verdict"] = "drift"

        payload = self.assertRejected(
            run_validator_data(fixture, emit_contract=True),
            "IDENTITY_LANDMARK_QA_FAILED",
            expected_effective_status="rejected",
        )
        self.assertIn(
            "PROTECTED_PRODUCT_PIXEL_DRIFT",
            [error["code"] for error in payload["errors"]],
        )
        self.assertNotIn("prompt_contract", payload)

    def test_pending_draft_qa_remains_an_unverified_draft(self):
        fixture = valid_manifest()
        fixture["delivery_status"] = "unverified_draft"
        fixture["qa"] = {"overall_verdict": "pending"}

        payload = self.assertAccepted(run_validator_data(fixture))

        self.assertEqual(payload["effective_delivery_status"], "unverified_draft")

    def test_full_generative_redraw_cannot_be_delivered_as_verified_composite(self):
        result = run_validator("reject-full-generative-commercial.json")

        self.assertRejected(
            result,
            "UNSAFE_COMMERCIAL_METHOD",
            expected_effective_status="unverified_draft",
        )

    def test_full_generative_redraw_is_allowed_only_as_an_unverified_draft(self):
        fixture = json.loads(
            (FIXTURES / "reject-full-generative-commercial.json").read_text(
                encoding="utf-8"
            )
        )
        fixture["delivery_status"] = "unverified_draft"

        result = run_validator_data(fixture)

        payload = self.assertAccepted(result)
        self.assertEqual(payload["effective_delivery_status"], "unverified_draft")

    def test_full_generative_redraw_preserves_explicit_restrictive_delivery_statuses(self):
        for delivery_status in ("blocked", "rejected"):
            with self.subTest(delivery_status=delivery_status):
                fixture = json.loads(
                    (FIXTURES / "reject-full-generative-commercial.json").read_text(
                        encoding="utf-8"
                    )
                )
                fixture["delivery_status"] = delivery_status

                result = run_validator_data(fixture)

                payload = self.assertAccepted(result)
                self.assertEqual(payload["effective_delivery_status"], delivery_status)

    def test_evidence_constrained_generation_can_reach_verified_reference_match(self):
        payload = self.assertAccepted(
            run_validator("accept-evidence-constrained-generation.json")
        )

        self.assertEqual(
            payload["effective_delivery_status"], "verified_reference_match"
        )

    def test_evidence_generation_requires_false_pixel_preservation(self):
        fixture = evidence_generation_manifest()
        fixture["method"]["product_pixels_preserved"] = True

        self.assertRejected(
            run_validator_data(fixture), "INVALID_GENERATIVE_PIXEL_PRESERVATION"
        )

    def test_evidence_generation_requires_selected_product_view_anchors(self):
        fixture = evidence_generation_manifest()
        fixture["method"]["view_anchor_source_ids"] = []
        self.assertRejected(run_validator_data(fixture), "MISSING_VIEW_ANCHOR")

        fixture = evidence_generation_manifest()
        fixture["method"]["view_anchor_source_ids"] = ["target-model-scene"]
        self.assertRejected(run_validator_data(fixture), "INVALID_VIEW_ANCHOR_SOURCE")

        fixture = evidence_generation_manifest()
        fixture["sources"][1]["required"] = False
        fixture["reference_plan"]["selected_source_ids"].remove(
            "product-material-detail"
        )
        self.assertRejected(run_validator_data(fixture), "UNSELECTED_VIEW_ANCHOR")

    def test_evidence_generation_requires_all_identity_regions_to_be_redrawn(self):
        fixture = evidence_generation_manifest()
        fixture["scene_plan"]["visible_identity_critical_regions"] = [
            "material-crosshatch"
        ]
        fixture["scene_plan"]["redrawn_identity_critical_regions"] = [
            "front-geometry"
        ]

        self.assertRejected(
            run_validator_data(fixture), "GENERATED_IDENTITY_NOT_MARKED_REDRAWN"
        )

    def test_evidence_generation_requires_material_fact_coverage(self):
        fixture = evidence_generation_manifest()
        fixture["scene_plan"]["material_identity_fact_ids"] = []

        self.assertRejected(run_validator_data(fixture), "MISSING_MATERIAL_FACT")

        fixture = evidence_generation_manifest()
        fixture["scene_plan"]["material_identity_fact_ids"] = ["front-geometry"]
        self.assertRejected(run_validator_data(fixture), "INVALID_MATERIAL_FACT")

    def test_verified_reference_match_requires_passing_material_qa(self):
        fixture = evidence_generation_manifest()
        fixture["qa"]["material_comparison"]["verdict"] = "fail"

        self.assertRejected(
            run_validator_data(fixture),
            "MATERIAL_QA_FAILED",
            expected_effective_status="rejected",
        )

        fixture = evidence_generation_manifest()
        del fixture["qa"]["material_comparison"]
        self.assertRejected(run_validator_data(fixture), "MISSING_MATERIAL_QA")

    def test_evidence_generation_cannot_claim_verified_composite(self):
        fixture = evidence_generation_manifest()
        fixture["delivery_status"] = "verified_composite"

        self.assertRejected(
            run_validator_data(fixture), "WRONG_VERIFIED_STATUS_FOR_METHOD"
        )

    def test_prompt_contract_exports_anchor_and_material_constraints(self):
        payload = self.assertAccepted(
            run_validator_data(evidence_generation_manifest(), emit_contract=True)
        )
        contract = payload["prompt_contract"]

        self.assertEqual(
            contract["method"]["view_anchor_source_ids"],
            ["product-front", "product-material-detail"],
        )
        self.assertIs(contract["method"]["material_fidelity_required"], True)
        self.assertEqual(
            contract["material_identity_fact_ids"], ["material-crosshatch"]
        )

    def test_independent_blocker_outranks_full_redraw_delivery_ceiling(self):
        fixture = json.loads(
            (FIXTURES / "reject-full-generative-commercial.json").read_text(
                encoding="utf-8"
            )
        )
        fixture["scene_plan"]["final_visible_surfaces"].append("right_side")

        result = run_validator_data(fixture)

        payload = self.assertRejected(
            result,
            "UNSAFE_COMMERCIAL_METHOD",
            expected_effective_status="blocked",
        )
        self.assertIn(
            "UNSUPPORTED_VISIBLE_SURFACE",
            [error["code"] for error in payload["errors"]],
        )

    def test_masked_generative_contact_requires_literal_protective_capabilities(self):
        result = run_validator("reject-maskless-contact-edit.json")

        self.assertRejected(result, "MISSING_PROTECTIVE_TOOL_CAPABILITY")

    def test_capability_complete_masked_contact_edit_can_be_verified(self):
        fixture = valid_manifest()
        fixture["method"]["type"] = "masked_generative_contact"

        result = run_validator_data(fixture)

        payload = self.assertAccepted(result)
        self.assertEqual(payload["effective_delivery_status"], "verified_composite")

    def test_deterministic_composite_requires_preserved_product_pixels_and_protected_region(self):
        fixture = valid_manifest()
        fixture["method"]["product_pixels_preserved"] = False

        result = run_validator_data(fixture)

        self.assertRejected(result, "PRODUCT_PIXELS_NOT_PRESERVED")

        fixture = valid_manifest()
        fixture["method"]["protected_regions"] = []

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_PROTECTED_PRODUCT_REGION")

    def test_masked_contact_edit_rejects_invalid_masks_and_scalar_method_fields(self):
        fixture = valid_manifest()
        fixture["method"]["type"] = "masked_generative_contact"
        fixture["method"]["allowed_edit_mask"] = {"regions": ["product_repaint"]}

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_ALLOWED_EDIT_MASK")

        for malformed_method in (None, [], "deterministic_composite"):
            with self.subTest(method=repr(malformed_method)):
                fixture = valid_manifest()
                fixture["method"] = malformed_method

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_METHOD")

        fixture = valid_manifest()
        fixture["method"]["type"] = []

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_METHOD_TYPE")

    def test_concept_draft_cannot_be_mislabeled_as_verified_composite(self):
        fixture = valid_manifest()
        fixture["mode"] = "concept_draft"

        result = run_validator_data(fixture)

        self.assertRejected(
            result,
            "UNVERIFIED_DRAFT_REQUIRED",
            expected_effective_status="unverified_draft",
        )

    def test_invalid_utf8_manifest_is_rejected_as_structured_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "invalid-utf8.json"
            manifest_path.write_bytes(b'{"mode": "commercial_exact_product\xff"}')

            result = run_validator_path(manifest_path)

        self.assertRejected(result, "INVALID_ENCODING")

    def test_non_string_delivery_status_is_rejected(self):
        fixture = valid_manifest()
        fixture["delivery_status"] = None

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "null-delivery-status.json"
            manifest_path.write_text(json.dumps(fixture), encoding="utf-8")

            result = run_validator_path(manifest_path)

        self.assertRejected(result, "INVALID_FIELD_TYPE")

    def test_unknown_delivery_status_is_rejected_by_the_real_cli(self):
        fixture = valid_manifest()
        fixture["delivery_status"] = "not_a_delivery_state"

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["INVALID_DELIVERY_STATUS"])

    def test_mode_must_be_a_recognized_string_before_commercial_gates_branch(self):
        for invalid_mode in (None, "commercial_exact", "handbag"):
            with self.subTest(mode=repr(invalid_mode)):
                fixture = valid_manifest()
                fixture["mode"] = invalid_mode

                result = run_validator_data(fixture)

                self.assertRejectedCodes(result, ["INVALID_MODE"])

    def test_unknown_handle_count_cannot_support_exactly_one_claim(self):
        result = run_validator("reject-unknown-handle-claim.json")

        self.assertRejected(result, "UNSUPPORTED_PROMPT_CLAIM")

    def test_generic_approval_does_not_confirm_hidden_structure(self):
        result = run_validator("reject-generic-approval.json")

        self.assertRejected(result, "UNRESOLVED_HIGH_RISK_FACT")

    def test_required_product_sources_cannot_be_dropped_to_fit_reference_limit(self):
        result = run_validator("reject-dropped-product-references.json")

        self.assertRejected(result, "UNCOVERED_REQUIRED_SOURCE")

    def test_selected_deterministic_atlases_preserve_required_source_coverage(self):
        result = run_validator("accept-provenance-atlas.json")

        self.assertAccepted(result)

    def test_front_only_envelope_rejects_a_side_and_opening_in_the_final_scene(self):
        result = run_validator("reject-front-only-side-opening.json")

        self.assertRejected(result, "UNSUPPORTED_VISIBLE_SURFACE")

    def test_front_only_envelope_accepts_permitted_pose_and_crop_adjustments(self):
        result = run_validator("accept-front-only-adjusted-pose.json")

        self.assertAccepted(result)

    def test_presentation_envelope_requires_nonempty_typed_final_view_fields(self):
        malformed_fields = {
            "supported_orientations": [],
            "visible_surfaces": "front",
            "must_remain_hidden": None,
        }
        for field, malformed_value in malformed_fields.items():
            with self.subTest(field=field):
                fixture = valid_manifest()
                fixture["scene_plan"]["presentation_envelope"][field] = malformed_value

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_PRESENTATION_ENVELOPE_FIELD")

        for field, malformed_value in {
            "final_orientation": [],
            "final_visible_surfaces": [],
        }.items():
            with self.subTest(field=field):
                fixture = valid_manifest()
                fixture["scene_plan"][field] = malformed_value

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_FINAL_PRESENTATION_FIELD")

    def test_presentation_envelope_and_mirror_flag_cannot_be_malformed(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"] = []

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PRESENTATION_ENVELOPE")

        fixture = valid_manifest()
        fixture["scene_plan"]["mirrored_product_view"] = "false"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_MIRRORED_PRODUCT_VIEW")

    def test_product_view_evidence_must_be_a_nonempty_string(self):
        fixture = valid_manifest()
        fixture["sources"][0]["view"] = []

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PRODUCT_SOURCE_VIEW")

    def test_surface_evidence_must_be_a_complete_typed_object(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["surface_evidence"] = []

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_SURFACE_EVIDENCE")

        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["surface_evidence"] = {}

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_SURFACE_EVIDENCE")

    def test_surface_evidence_rejects_unknown_and_target_scene_sources(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["surface_evidence"] = {
            "front": ["unknown-source"]
        }

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNKNOWN_SURFACE_EVIDENCE_SOURCE")

        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["surface_evidence"] = {
            "front": ["target-model-scene"]
        }

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_SURFACE_EVIDENCE_SOURCE_ROLE")

    def test_surface_evidence_source_view_must_support_its_surface(self):
        # Surface evidence uses the validator's narrow view mapping: a
        # ``front`` source supports only ``front``, never an implied side.
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["surface_evidence"] = {
            "right_side": ["product-front"]
        }
        fixture["scene_plan"]["presentation_envelope"]["visible_surfaces"] = [
            "right_side"
        ]
        fixture["scene_plan"]["final_visible_surfaces"] = ["right_side"]
        fixture["scene_plan"]["presentation_envelope"]["must_remain_hidden"].remove(
            "right_side"
        )
        fixture["scene_plan"]["forbidden_invented_regions"].remove("right_side")

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNSUPPORTED_SURFACE_EVIDENCE_VIEW")

    def test_detail_source_with_a_front_view_can_support_the_front_surface(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["surface_evidence"] = {
            "front": ["product-clasp-detail"]
        }

        result = run_validator_data(fixture)

        self.assertAccepted(result)

    def test_commercial_envelope_must_explicitly_hide_every_other_canonical_surface(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["must_remain_hidden"].remove(
            "top"
        )

        result = run_validator_data(fixture)

        self.assertRejected(result, "INCOMPLETE_CANONICAL_SURFACE_ENVELOPE")

    def test_commercial_envelope_rejects_unknown_surface_labels(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["must_remain_hidden"].append(
            "logo_side"
        )

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNKNOWN_SURFACE_LABEL")

    def test_product_views_and_presentation_orientations_must_be_recognized(self):
        fixture = valid_manifest()
        fixture["sources"][0]["view"] = "handbag"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PRODUCT_SOURCE_VIEW")

        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["supported_orientations"] = [
            "handbag"
        ]
        fixture["scene_plan"]["final_orientation"] = "handbag"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PRESENTATION_ORIENTATION")

    def test_envelope_cannot_self_authorize_a_right_side_with_front_evidence(self):
        fixture = valid_manifest()
        envelope = fixture["scene_plan"]["presentation_envelope"]
        envelope["visible_surfaces"].append("right_side")
        envelope["surface_evidence"]["right_side"] = ["product-front"]
        fixture["scene_plan"]["final_visible_surfaces"] = ["front", "right_side"]
        envelope["must_remain_hidden"].remove("right_side")
        fixture["scene_plan"]["forbidden_invented_regions"].remove("right_side")

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNSUPPORTED_SURFACE_EVIDENCE_VIEW")

    def test_envelope_orientation_must_be_supported_by_a_product_source_view(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["supported_orientations"] = [
            "right_side"
        ]
        fixture["scene_plan"]["final_orientation"] = "right_side"

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNSUPPORTED_ENVELOPE_ORIENTATION")

    def test_mirroring_cannot_substitute_for_an_unphotographed_opposite_side(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["mirrored_product_view"] = True
        fixture["scene_plan"]["presentation_envelope"]["visible_surfaces"] = [
            "front",
            "left_side",
        ]
        fixture["scene_plan"]["final_visible_surfaces"] = ["front", "left_side"]
        fixture["scene_plan"]["presentation_envelope"]["must_remain_hidden"].remove(
            "left_side"
        )
        fixture["scene_plan"]["forbidden_invented_regions"].remove("left_side")

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNSUPPORTED_MIRRORED_PRODUCT_VIEW")

    def test_commercial_exact_product_rejects_any_mirrored_product_view(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["mirrored_product_view"] = True

        result = run_validator_data(fixture)

        self.assertRejected(result, "MIRRORED_PRODUCT_VIEW_UNSUPPORTED")

    def test_mirrored_right_side_rejects_even_with_independent_right_side_evidence(self):
        fixture = valid_manifest()
        fixture["sources"].append(
            {
                "id": "product-right-side",
                "role": "product_truth",
                "view": "right_side",
                "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "required": False,
            }
        )
        envelope = fixture["scene_plan"]["presentation_envelope"]
        envelope["supported_orientations"].append("right_side")
        envelope["visible_surfaces"].append("right_side")
        envelope["surface_evidence"]["right_side"] = ["product-right-side"]
        envelope["must_remain_hidden"].remove("right_side")
        fixture["scene_plan"]["forbidden_invented_regions"].remove("right_side")
        fixture["scene_plan"]["final_orientation"] = "right_side"
        fixture["scene_plan"]["final_visible_surfaces"] = ["right_side"]
        fixture["scene_plan"]["mirrored_product_view"] = True

        result = run_validator_data(fixture)

        self.assertRejected(result, "MIRRORED_PRODUCT_VIEW_UNSUPPORTED")

    def test_final_surfaces_cannot_be_marked_hidden_or_forbidden(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["presentation_envelope"]["must_remain_hidden"].append(
            "front"
        )

        result = run_validator_data(fixture)

        self.assertRejected(result, "VISIBLE_MUST_REMAIN_HIDDEN")

        fixture = valid_manifest()
        fixture["scene_plan"]["forbidden_invented_regions"].append("front")

        result = run_validator_data(fixture)

        self.assertRejected(result, "VISIBLE_FORBIDDEN_REGION")

    def test_product_deformation_and_view_change_are_not_permitted_scene_adjustments(self):
        fixture = valid_manifest()
        fixture["scene_plan"]["permitted_scene_adjustments"].append(
            "product_deformation"
        )
        fixture["scene_plan"]["applied_scene_adjustments"].append(
            "product_deformation"
        )

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNSUPPORTED_SCENE_ADJUSTMENT")

    def test_reference_plan_collections_are_not_treated_as_empty_coverage(self):
        malformed_fields = {
            "reference_plan": None,
            "selected_source_ids": {},
            "deterministic_atlases": {},
        }
        for field, malformed_value in malformed_fields.items():
            with self.subTest(field=field):
                fixture = valid_manifest()
                if field == "reference_plan":
                    fixture[field] = malformed_value
                else:
                    fixture["reference_plan"][field] = malformed_value

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_REFERENCE_PLAN")

    def test_sources_must_not_silently_become_an_empty_coverage_set(self):
        fixture = valid_manifest()
        fixture["sources"] = None

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_SOURCES_COLLECTION")

        fixture = valid_manifest()
        fixture["sources"] = ["not-a-source"]

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_SOURCE_RECORD")

    def test_selected_reference_ids_must_be_known_and_fit_the_limit(self):
        fixture = valid_manifest()
        fixture["reference_plan"]["selected_source_ids"].append("unknown-reference")

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNKNOWN_SELECTED_REFERENCE")

        fixture = valid_manifest()
        fixture["reference_plan"]["tool_reference_limit"] = 2

        result = run_validator_data(fixture)

        self.assertRejected(result, "REFERENCE_LIMIT_EXCEEDED")

    def test_atlas_provenance_requires_safe_complete_crop_mappings(self):
        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["reference_plan"]["deterministic_atlases"][0]["deterministic"] = False

        result = run_validator_data(fixture)

        self.assertRejected(result, "NONDETERMINISTIC_ATLAS")

        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["reference_plan"]["deterministic_atlases"][0]["crop_mappings"].pop()

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_ATLAS_CROP_MAPPING")

        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["reference_plan"]["deterministic_atlases"][0]["crop_mappings"][0][
            "identity_landmarks_readable"
        ] = False

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNREADABLE_IDENTITY_CRITICAL_ATLAS_CROP")

    def test_atlases_cannot_have_unknown_parents_or_duplicate_ids(self):
        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        atlas = fixture["reference_plan"]["deterministic_atlases"][0]
        atlas["parent_source_ids"][0] = "unknown-parent"
        atlas["crop_mappings"][0]["parent_source_id"] = "unknown-parent"

        result = run_validator_data(fixture)

        self.assertRejected(result, "UNKNOWN_ATLAS_PARENT_SOURCE")

        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        duplicate = dict(fixture["reference_plan"]["deterministic_atlases"][0])
        fixture["reference_plan"]["deterministic_atlases"].append(duplicate)
        fixture["reference_plan"]["selected_source_ids"].append(duplicate["id"])

        result = run_validator_data(fixture)

        self.assertRejected(result, "DUPLICATE_ATLAS_ID")

    def test_sources_and_atlases_require_sha256_hashes(self):
        fixture = valid_manifest()
        fixture["sources"][0].pop("sha256")

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_SOURCE_HASH")

        fixture = valid_manifest()
        fixture["sources"][0]["sha256"] = "not-a-hash"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_SOURCE_HASH")

        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["reference_plan"]["deterministic_atlases"][0].pop("sha256")

        result = run_validator_data(fixture)

        self.assertRejected(result, "MISSING_ATLAS_SOURCE_HASH")

        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["reference_plan"]["deterministic_atlases"][0]["sha256"] = "g" * 64

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_ATLAS_SOURCE_HASH")

    def test_atlas_output_regions_cannot_overlap_or_duplicate_mappings(self):
        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["reference_plan"]["deterministic_atlases"][0]["crop_mappings"][0][
            "atlas_normalized_region"
        ] = [0.25, 0.0, 0.5, 0.5]

        result = run_validator_data(fixture)

        self.assertRejected(result, "OVERLAPPING_ATLAS_OUTPUT_REGION")

        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        mapping = dict(fixture["reference_plan"]["deterministic_atlases"][0]["crop_mappings"][0])
        fixture["reference_plan"]["deterministic_atlases"][0]["crop_mappings"].append(mapping)

        result = run_validator_data(fixture)

        self.assertRejected(result, "DUPLICATE_ATLAS_CROP_MAPPING")

    def test_distinct_nonoverlapping_crops_from_one_parent_are_accepted(self):
        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["reference_plan"]["deterministic_atlases"][0]["crop_mappings"].append(
            {
                "parent_source_id": "product-view-1",
                "source_normalized_region": [0.0, 0.0, 0.5, 0.5],
                "atlas_normalized_region": [0.5, 0.5, 0.5, 0.5],
                "identity_landmarks_readable": True,
            }
        )

        result = run_validator_data(fixture)

        self.assertAccepted(result)

    def test_atlas_landmark_readability_must_be_a_boolean_when_present(self):
        for malformed_value in (0, 1, "true", None):
            with self.subTest(value=repr(malformed_value)):
                fixture = json.loads(
                    (FIXTURES / "accept-provenance-atlas.json").read_text(
                        encoding="utf-8"
                    )
                )
                fixture["reference_plan"]["deterministic_atlases"][0][
                    "crop_mappings"
                ][0]["identity_landmarks_readable"] = malformed_value

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_ATLAS_IDENTITY_LANDMARKS_READABLE")

    def test_source_roles_are_closed_and_product_evidence_cannot_use_target_scene(self):
        for malformed_role in (None, "other_role", [], {}):
            with self.subTest(role=repr(malformed_role)):
                fixture = valid_manifest()
                fixture["sources"][0]["role"] = malformed_role

                result = run_validator_data(fixture)

                self.assertRejected(result, "INVALID_SOURCE_ROLE")

        fixture = valid_manifest()
        fixture["facts"][0]["evidence"][0]["source_id"] = "target-model-scene"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PRODUCT_EVIDENCE_SOURCE_ROLE")

        fixture = valid_manifest()
        fixture["facts"][0]["status"] = "unknown"
        fixture["facts"][0]["commercial_importance"] = "low"
        fixture["facts"][0]["evidence"][0]["source_id"] = "target-model-scene"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PRODUCT_EVIDENCE_SOURCE_ROLE")

        fixture = valid_manifest()
        fixture["topology"][0]["evidence"][0]["source_id"] = "target-model-scene"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_PRODUCT_EVIDENCE_SOURCE_ROLE")

    def test_atlas_parents_cannot_be_target_scene_sources(self):
        fixture = json.loads(
            (FIXTURES / "accept-provenance-atlas.json").read_text(encoding="utf-8")
        )
        fixture["sources"].append(
            {
                "id": "target-scene",
                "role": "target_scene",
                "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
                "required": False,
            }
        )
        atlas = fixture["reference_plan"]["deterministic_atlases"][0]
        atlas["parent_source_ids"][0] = "target-scene"
        atlas["crop_mappings"][0]["parent_source_id"] = "target-scene"

        result = run_validator_data(fixture)

        self.assertRejected(result, "INVALID_ATLAS_PARENT_SOURCE_ROLE")

    def test_duplicate_selected_references_are_rejected(self):
        fixture = valid_manifest()
        fixture["reference_plan"]["selected_source_ids"].append("product-front")

        result = run_validator_data(fixture)

        self.assertRejected(result, "DUPLICATE_SELECTED_REFERENCE")

        fixture = valid_manifest()
        fixture["reference_plan"]["selected_source_ids"] = ["unknown", "unknown"]

        result = run_validator_data(fixture)

        self.assertRejected(result, "DUPLICATE_SELECTED_REFERENCE")

    def test_sections_must_be_arrays(self):
        for section in ("facts", "topology", "prompt_claims"):
            with self.subTest(section=section):
                fixture = valid_manifest()
                fixture[section] = {}

                result = run_validator_data(fixture)

                self.assertRejectedCodes(result, ["INVALID_SECTION_TYPE"])

    def test_section_records_must_be_objects(self):
        for section in ("facts", "topology", "prompt_claims"):
            with self.subTest(section=section):
                fixture = valid_manifest()
                fixture[section] = ["not-a-record"]

                result = run_validator_data(fixture)

                self.assertRejectedCodes(result, ["INVALID_RECORD_TYPE"])

    def test_records_require_nonempty_ids(self):
        for section in ("facts", "topology", "prompt_claims"):
            with self.subTest(section=section):
                fixture = valid_manifest()
                fixture[section][0]["id"] = ""

                result = run_validator_data(fixture)

                self.assertRejectedCodes(result, ["MISSING_RECORD_ID"])

    def test_fact_and_topology_statuses_must_be_known(self):
        for section in ("facts", "topology"):
            with self.subTest(section=section):
                fixture = valid_manifest()
                fixture[section][0]["status"] = "inferred"

                result = run_validator_data(fixture)

                self.assertRejectedCodes(result, ["INVALID_STATUS"])

    def test_fact_and_topology_statuses_must_be_strings(self):
        for section in ("facts", "topology"):
            for malformed_status in ([], {}):
                with self.subTest(section=section, status=type(malformed_status).__name__):
                    fixture = valid_manifest()
                    fixture[section][0]["status"] = malformed_status

                    result = run_validator_data(fixture)

                    self.assertRejectedCodes(result, ["INVALID_STATUS"])

    def test_fact_evidence_regions_must_be_finite_normalized_rectangles(self):
        invalid_regions = {
            "negative": [-0.01, 0.2, 0.4, 0.4],
            "out_of_bounds": [0.7, 0.2, 0.4, 0.4],
            "zero_size": [0.2, 0.2, 0.0, 0.4],
            "boolean": [True, 0.2, 0.4, 0.4],
            "non_finite": [float("inf"), 0.2, 0.4, 0.4],
        }
        for case, region in invalid_regions.items():
            with self.subTest(case=case):
                fixture = valid_manifest()
                fixture["facts"][0]["evidence"][0]["normalized_region"] = region

                result = run_validator_data(fixture)

                self.assertRejectedCodes(
                    result,
                    ["MISSING_FACT_EVIDENCE", "UNSUPPORTED_PROMPT_CLAIM"],
                )

    def test_topology_evidence_regions_must_be_finite_normalized_rectangles(self):
        fixture = valid_manifest()
        fixture["topology"][0]["evidence"][0]["normalized_region"] = [
            0.8,
            0.2,
            0.3,
            0.4,
        ]

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, [
            "UNSUPPORTED_VISIBLE_ATTACHMENT_POINT",
            "UNSUPPORTED_VISIBLE_ATTACHMENT_POINT",
            "UNRESOLVED_HIGH_RISK_TOPOLOGY",
            "MISSING_FACT_EVIDENCE",
        ])

    def test_arbitrarily_large_evidence_integer_is_structured_rejection(self):
        for huge_integer in (10**400, (1 << 1024) - 1):
            with self.subTest(bit_length=huge_integer.bit_length()):
                fixture = valid_manifest()
                fixture["facts"][0]["evidence"][0]["normalized_region"] = [
                    huge_integer,
                    0.2,
                    0.4,
                    0.4,
                ]
                fixture["prompt_claims"] = []

                result = run_validator_data(fixture)

                self.assertRejectedCodes(result, ["INVALID_EVIDENCE_REGION"])

    def test_scene_plan_must_be_an_object(self):
        fixture = valid_manifest()
        fixture["scene_plan"] = None

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["INVALID_FIELD_TYPE"])

    def test_identity_region_lists_must_contain_nonempty_string_ids(self):
        malformed_fields = {
            "visible_identity_critical_regions": None,
            "redrawn_identity_critical_regions": "front-silhouette",
        }
        for field, malformed_value in malformed_fields.items():
            with self.subTest(field=field):
                fixture = valid_manifest()
                fixture["scene_plan"][field] = malformed_value

                result = run_validator_data(fixture)

                self.assertRejectedCodes(result, ["INVALID_SECTION_TYPE"])

        fixture = valid_manifest()
        fixture["scene_plan"]["visible_identity_critical_regions"] = [""]

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["INVALID_REGION_ID"])

    def test_duplicate_fact_ids_are_rejected_before_claim_lookup(self):
        fixture = valid_manifest()
        duplicate = dict(fixture["facts"][0])
        fixture["facts"].append(duplicate)

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["DUPLICATE_SUPPORT_ID"])

    def test_duplicate_topology_ids_are_rejected_before_claim_lookup(self):
        fixture = valid_manifest()
        duplicate = dict(fixture["topology"][0])
        fixture["topology"].insert(0, duplicate)

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["DUPLICATE_SUPPORT_ID"])

    def test_fact_and_topology_id_collision_is_rejected(self):
        fixture = valid_manifest()
        fixture["topology"][0]["id"] = fixture["facts"][0]["id"]

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["DUPLICATE_SUPPORT_ID"])

    def test_visible_conflicting_high_risk_fact_is_rejected_without_claim(self):
        fixture = valid_manifest()
        fixture["facts"][0]["status"] = "conflict"
        fixture["prompt_claims"] = []

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["UNRESOLVED_HIGH_RISK_FACT"])

    def test_redrawn_unknown_high_risk_fact_is_rejected_without_claim(self):
        fixture = valid_manifest()
        fixture["facts"][0]["status"] = "unknown"
        fixture["prompt_claims"] = []
        fixture["scene_plan"]["visible_identity_critical_regions"] = []
        fixture["scene_plan"]["redrawn_identity_critical_regions"] = [
            "front-silhouette"
        ]
        fixture["scene_plan"]["presentation_envelope"]["visible_attachment_points"] = []

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["UNRESOLVED_HIGH_RISK_FACT"])

    def test_unapproved_user_confirmed_fact_has_distinct_diagnostic(self):
        fixture = valid_manifest()
        fixture["facts"][0]["status"] = "user_confirmed"
        fixture["approval"]["confirmed_fact_ids"] = []
        fixture["prompt_claims"] = []

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["UNCONFIRMED_USER_FACT"])

    def test_unapproved_user_confirmed_topology_has_distinct_diagnostic(self):
        fixture = valid_manifest()
        fixture["topology"][0]["status"] = "user_confirmed"
        fixture["approval"]["confirmed_fact_ids"] = []
        fixture["prompt_claims"] = []

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, [
            "UNSUPPORTED_VISIBLE_ATTACHMENT_POINT",
            "UNSUPPORTED_VISIBLE_ATTACHMENT_POINT",
            "UNRESOLVED_HIGH_RISK_TOPOLOGY",
            "UNCONFIRMED_USER_FACT",
        ])

    def test_observed_fact_without_evidence_is_rejected(self):
        fixture = valid_manifest()
        fixture["facts"][0]["evidence"] = []
        fixture["prompt_claims"] = []

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["MISSING_FACT_EVIDENCE"])

    def test_missing_prompt_claim_support_is_rejected(self):
        fixture = valid_manifest()
        fixture["prompt_claims"] = [
            {"id": "missing-support", "claim": "Preserve the handle.", "supporting_ids": ["missing"]}
        ]

        result = run_validator_data(fixture)

        self.assertRejectedCodes(result, ["UNSUPPORTED_PROMPT_CLAIM"])

    def test_source_backed_topology_can_support_prompt_claim(self):
        fixture = valid_manifest()
        fixture["prompt_claims"] = [
            {
                "id": "topology-claim",
                "claim": "Preserve the observed chain path.",
                "supporting_ids": ["front-chain-path"],
            }
        ]

        result = run_validator_data(fixture)

        self.assertAccepted(result)

    def test_explicit_user_confirmation_with_evidence_is_accepted(self):
        fixture = valid_manifest()
        fixture["facts"][0]["status"] = "user_confirmed"
        fixture["approval"]["confirmed_fact_ids"] = ["front-silhouette"]

        result = run_validator_data(fixture)

        self.assertAccepted(result)


class PromptContractAndTopologyTests(unittest.TestCase):
    """Follow-up regressions for executable contract coverage."""

    assertAccepted = ValidateFidelityManifestTests.assertAccepted
    assertRejected = ValidateFidelityManifestTests.assertRejected

    def test_unresolved_visible_or_redrawn_topology_blocks_without_prompt_claim(self):
        for status in ("unknown", "conflict", "user_confirmed"):
            for scope in ("visible_identity_critical_regions", "redrawn_identity_critical_regions"):
                with self.subTest(status=status, scope=scope):
                    data = valid_manifest()
                    data["topology"][0]["status"] = status
                    data["prompt_claims"] = []
                    data["scene_plan"]["visible_identity_critical_regions"] = []
                    data["scene_plan"][scope] = ["front-chain-path"]
                    self.assertRejected(run_validator_data(data), "UNRESOLVED_HIGH_RISK_TOPOLOGY")

    def test_attachment_points_require_unique_nonempty_string_array(self):
        for value in (None, "left_attachment", [""], [1], ["left_attachment", "left_attachment"]):
            with self.subTest(value=value):
                data = valid_manifest()
                data["scene_plan"]["presentation_envelope"]["visible_attachment_points"] = value
                self.assertRejected(run_validator_data(data), "INVALID_VISIBLE_ATTACHMENT_POINTS")
        data = valid_manifest()
        del data["scene_plan"]["presentation_envelope"]["visible_attachment_points"]
        self.assertRejected(run_validator_data(data), "INVALID_VISIBLE_ATTACHMENT_POINTS")

    def test_attachment_points_must_be_resolved_source_backed_topology_endpoints(self):
        for point, status, source in (("invented_ring", "observed", "product-front"),
                                      ("left_attachment", "unknown", "product-front"),
                                      ("left_attachment", "user_confirmed", "product-front"),
                                      ("left_attachment", "observed", "target-model-scene")):
            with self.subTest(point=point, status=status, source=source):
                data = valid_manifest()
                data["scene_plan"]["presentation_envelope"]["visible_attachment_points"] = [point]
                data["topology"][0]["status"] = status
                data["topology"][0]["evidence"][0]["source_id"] = source
                self.assertRejected(run_validator_data(data), "UNSUPPORTED_VISIBLE_ATTACHMENT_POINT")

    def test_empty_and_explicitly_confirmed_attachment_points_are_accepted(self):
        data = valid_manifest()
        data["scene_plan"]["presentation_envelope"]["visible_attachment_points"] = []
        self.assertAccepted(run_validator_data(data))
        data["scene_plan"]["presentation_envelope"]["visible_attachment_points"] = ["left_attachment"]
        data["topology"][0]["status"] = "user_confirmed"
        data["approval"]["confirmed_fact_ids"] = ["front-chain-path"]
        self.assertAccepted(run_validator_data(data))

    def test_emit_mode_preserves_ids_evidence_and_validated_edit_scope(self):
        data = valid_manifest()
        result = run_validator_data(data, emit_contract=True)
        contract = self.assertAccepted(result)["prompt_contract"]
        self.assertEqual(contract["facts"][0]["id"], "front-silhouette")
        self.assertEqual(contract["facts"][0]["evidence"], data["facts"][0]["evidence"])
        self.assertEqual(contract["topology"][0]["id"], "front-chain-path")
        self.assertEqual(contract["prompt_claims"], data["prompt_claims"])
        self.assertEqual(contract["source_roles"][0], {"id": "product-front", "role": "product_truth"})
        self.assertEqual(contract["presentation_envelope"], data["scene_plan"]["presentation_envelope"])
        self.assertEqual(contract["permitted_scene_adjustments"], data["scene_plan"]["permitted_scene_adjustments"])
        self.assertEqual(contract["method"]["type"], "deterministic_composite")
        self.assertEqual(contract["method"]["allowed_edit_mask"], data["method"]["allowed_edit_mask"])

    def test_emit_mode_is_deterministic_and_normal_mode_has_no_contract(self):
        data = valid_manifest()
        first = run_validator_data(data, emit_contract=True)
        second = run_validator_data(data, emit_contract=True)
        self.assertAccepted(first)
        self.assertEqual(first.stdout, second.stdout)
        self.assertNotIn("prompt_contract", self.assertAccepted(run_validator_data(data)))

    def test_emit_mode_omits_hidden_unknowns_and_unrecognized_freeform_fields(self):
        data = valid_manifest()
        data["facts"].append({"id": "hidden-count", "status": "unknown", "commercial_importance": "high", "assertion": "UNSAFE UNKNOWN COUNT", "evidence": []})
        data["topology"].append({"id": "hidden-path", "status": "conflict", "path": "UNSAFE CONFLICT PATH", "evidence": []})
        data["freeform_prompt"] = "UNSAFE FREEFORM STRUCTURE"
        data["facts"][0]["extra_instruction"] = "UNSAFE EXTRA INSTRUCTION"
        data["scene_plan"]["presentation_envelope"]["extra_instruction"] = "UNSAFE ENVELOPE INSTRUCTION"
        data["method"]["allowed_edit_mask"]["extra_instruction"] = "UNSAFE MASK INSTRUCTION"
        result = run_validator_data(data, emit_contract=True)
        contract = self.assertAccepted(result)["prompt_contract"]
        self.assertNotIn("UNSAFE", json.dumps(contract))
        self.assertNotIn("hidden-count", [record["id"] for record in contract["facts"]])
        self.assertNotIn("hidden-path", [record["id"] for record in contract["topology"]])

    def test_invalid_emit_request_never_returns_a_contract(self):
        data = valid_manifest()
        data["prompt_claims"][0]["supporting_ids"] = ["unknown-id"]
        payload = self.assertRejected(run_validator_data(data, emit_contract=True), "UNSUPPORTED_PROMPT_CLAIM")
        self.assertNotIn("prompt_contract", payload)
        data = valid_manifest()
        data["topology"][0]["status"] = "unknown"
        data["prompt_claims"] = []
        payload = self.assertRejected(run_validator_data(data, emit_contract=True), "UNRESOLVED_HIGH_RISK_TOPOLOGY")
        self.assertNotIn("prompt_contract", payload)

    def test_forbidden_mutations_require_support_and_export_only_validated_records(self):
        data = valid_manifest()
        data["forbidden_mutations"] = [{"id": "no-clasp-change", "claim": "Do not change the observed front clasp.", "supporting_ids": ["front-clasp"]}]
        contract = self.assertAccepted(run_validator_data(data, emit_contract=True))["prompt_contract"]
        self.assertEqual(contract["forbidden_mutations"], data["forbidden_mutations"])
        data["forbidden_mutations"][0]["supporting_ids"] = ["invented-fact"]
        payload = self.assertRejected(run_validator_data(data, emit_contract=True), "UNSUPPORTED_PROMPT_CLAIM")
        self.assertNotIn("prompt_contract", payload)
        data["forbidden_mutations"] = ["Never add a second handle."]
        self.assertRejected(run_validator_data(data), "INVALID_RECORD_TYPE")

    def test_emit_rejects_malformed_structural_values_instead_of_exporting_nested_prose(self):
        for section, field in (("facts", "assertion"), ("topology", "path"), ("prompt_claims", "claim")):
            with self.subTest(section=section, field=field):
                data = valid_manifest()
                data[section][0][field] = {"instruction": "invent a new handle"}
                payload = self.assertRejected(run_validator_data(data, emit_contract=True), "INVALID_PROMPT_CONTRACT_CONTENT")
                self.assertNotIn("prompt_contract", payload)

    def test_full_redraw_export_rejects_unvalidated_method_prose(self):
        data = valid_manifest()
        data["method"]["type"] = "full_generative_redraw"
        data["delivery_status"] = "unverified_draft"
        data["method"]["product_pixels_preserved"] = {"instruction": "invent a handle"}
        payload = self.assertRejected(run_validator_data(data, emit_contract=True), "INVALID_PROMPT_CONTRACT_CONTENT")
        self.assertNotIn("prompt_contract", payload)

    def test_concept_export_still_requires_supported_presentation(self):
        data = valid_manifest()
        data["mode"] = "concept_draft"
        data["delivery_status"] = "unverified_draft"
        self.assertAccepted(run_validator_data(data, emit_contract=True))
        data["scene_plan"]["presentation_envelope"]["supported_orientations"] = ["invented_view"]
        payload = self.assertRejected(run_validator_data(data, emit_contract=True), "INVALID_PRESENTATION_ORIENTATION")
        self.assertNotIn("prompt_contract", payload)


class ManifestInputIntegrityTests(unittest.TestCase):
    assertAccepted = ValidateFidelityManifestTests.assertAccepted
    assertRejected = ValidateFidelityManifestTests.assertRejected

    def run_raw_manifest(self, content: str, emit_contract: bool = False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(content, encoding="utf-8")
            return run_validator_path(path, emit_contract=emit_contract)

    def test_identity_region_ids_must_resolve_in_verified_and_preflight_modes(self):
        for mode, status in (("commercial_exact_product", "verified_composite"),
                             ("commercial_exact_product", "unverified_draft"),
                             ("concept_draft", "unverified_draft")):
            for field in ("visible_identity_critical_regions", "redrawn_identity_critical_regions"):
                with self.subTest(mode=mode, status=status, field=field):
                    data = valid_manifest()
                    data["mode"] = mode
                    data["delivery_status"] = status
                    data["scene_plan"][field] = ["misspelled-topology"]
                    for emit_contract in (False, True):
                        result = run_validator_data(data, emit_contract=emit_contract)
                        payload = self.assertRejected(result, "UNKNOWN_IDENTITY_REGION_ID")
                        self.assertEqual([error["code"] for error in payload["errors"]], ["UNKNOWN_IDENTITY_REGION_ID"])
                        self.assertNotIn("prompt_contract", payload)

    def test_unknown_topology_cannot_be_hidden_by_renaming_visible_and_qa_ids(self):
        data = valid_manifest()
        data["topology"][0]["status"] = "unknown"
        data["prompt_claims"] = []
        data["scene_plan"]["presentation_envelope"]["visible_attachment_points"] = []
        data["scene_plan"]["visible_identity_critical_regions"][-1] = "renamed-chain"
        data["qa"]["landmark_records"][-1]["landmark_id"] = "renamed-chain"
        for emit_contract in (False, True):
            payload = self.assertRejected(run_validator_data(data, emit_contract=emit_contract), "UNKNOWN_IDENTITY_REGION_ID")
            self.assertNotIn("prompt_contract", payload)

    def test_duplicate_protected_pixel_verdict_keys_reject_in_both_orders(self):
        for first, second in (("drift", "pass"), ("pass", "drift")):
            raw = json.dumps(valid_manifest())
            original = '"protected_pixels": {"verdict": "pass",'
            self.assertIn(original, raw)
            raw = raw.replace(original, '"protected_pixels": {"verdict": "' + first + '", "verdict": "' + second + '",')
            for emit_contract in (False, True):
                with self.subTest(first=first, second=second, emit=emit_contract):
                    result = self.run_raw_manifest(raw, emit_contract)
                    payload = self.assertRejected(result, "DUPLICATE_JSON_KEY")
                    self.assertNotIn("prompt_contract", payload)
                    self.assertEqual(result.stderr, "")

    def test_nested_duplicate_json_keys_reject_even_outside_qa(self):
        raw = json.dumps(valid_manifest())[:-1] + ', "metadata": {"nested": {"id": "one", "id": "two"}}}'
        for emit_contract in (False, True):
            payload = self.assertRejected(self.run_raw_manifest(raw, emit_contract), "DUPLICATE_JSON_KEY")
            self.assertNotIn("prompt_contract", payload)

    def test_deep_json_returns_structured_error_without_traceback_or_contract(self):
        raw = '{"nested":' * 2000 + '0' + '}' * 2000
        for emit_contract in (False, True):
            result = self.run_raw_manifest(raw, emit_contract)
            self.assertEqual(result.stderr, "")
            payload = self.assertRejected(result, "JSON_NESTING_TOO_DEEP")
            self.assertNotIn("prompt_contract", payload)


class FidelityDocumentationContractTests(unittest.TestCase):
    """Keep operational safety rules in the documents agents actually load."""

    def document(self, relative_path: str) -> str:
        path = TESTS.parent / relative_path
        self.assertTrue(path.is_file(), f"Required workflow reference missing: {relative_path}")
        return path.read_text(encoding="utf-8")

    def require_rule(self, document: str, pattern: str, message: str) -> None:
        self.assertTrue(re.search(pattern, document, re.MULTILINE), message)

    def test_entrypoint_requires_preflight_before_first_commercial_candidate(self):
        skill = self.document("SKILL.md")
        self.require_rule(skill, r"结构化 JSON manifest", "Require persisted structured evidence.")
        self.require_rule(
            skill, r"首张商业候选.*之前.*运行.*scripts/validate_fidelity_manifest\.py",
            "Run the actual validator before the first commercial candidate.",
        )
        self.require_rule(skill, r"验证失败.*停止", "Preflight errors must stop execution.")

    def test_entrypoint_requires_fresh_predelivery_validation(self):
        self.require_rule(
            self.document("SKILL.md"),
            r"交付前.*再次运行.*scripts/validate_fidelity_manifest\.py.*verified_composite",
            "Revalidate the updated manifest and verified status before delivery.",
        )

    def test_case_is_optional_exact_sku_retrospective_and_not_general_bag_routing(self):
        skill = self.document("SKILL.md")
        case_routes = [line for line in skill.splitlines() if "black-bag-case-study.md" in line]
        self.assertEqual(len(case_routes), 1, "Use one unambiguous retrospective route.")
        self.require_rule(case_routes[0], r"仅.*该历史 SKU.*可选.*复盘", "Scope case reading to its historical SKU.")
        self.require_rule(case_routes[0], r"不得.*包袋.*默认", "Explicitly forbid category-wide routing.")
        self.assertNotIn("涉及包袋、带子、链条、闭合结构", skill)

    def test_historical_facts_have_opening_nontransfer_warning(self):
        opening = self.document("references/black-bag-case-study.md").split("##", 1)[0]
        self.require_rule(opening, r"所有.*事实.*仅.*历史.*SKU", "Warn before any SKU facts are read.")
        self.require_rule(opening, r"不得.*复制.*其他商品.*事实表.*提示词", "Prohibit cross-SKU fact and prompt transfer.")

    def test_entrypoint_and_protocol_adapt_model_pose_to_supported_envelope(self):
        for path in ("SKILL.md", "references/product-truth-protocol.md"):
            with self.subTest(document=path):
                document = self.document(path)
                self.require_rule(document, r"presentation_envelope", "Name the persisted envelope.")
                self.require_rule(document, r"视图不完整.*调整模特姿势.*手.*裁切.*商品位置", "Adapt the scene to incomplete views.")
                self.require_rule(document, r"仅展示来源支持的角度.*表面.*未知.*隐藏", "Keep unsupported surfaces hidden.")

    def test_generic_preview_and_packaging_approval_cannot_confirm_facts(self):
        protocol = self.document("references/product-truth-protocol.md")
        self.require_rule(protocol, r"泛泛的.*确认.*预览.*包装.*不能.*未知结构", "Generic approval never resolves structure.")
        self.require_rule(protocol, r"confirmed_fact_ids.*事实.*拓扑.*ID", "Bind explicit approval to support IDs.")

    def test_full_redraw_has_draft_ceiling_even_after_visual_approval(self):
        for path in ("SKILL.md", "references/product-truth-protocol.md"):
            with self.subTest(document=path):
                self.require_rule(
                    self.document(path), r"full_generative_redraw.*最高.*unverified_draft.*不得.*verified_composite",
                    "Full redraw can never reach commercial verified status.",
                )

    def test_only_validated_verified_composite_may_claim_exact_faithful_commercial(self):
        for path in ("SKILL.md", "references/product-truth-protocol.md"):
            with self.subTest(document=path):
                self.require_rule(
                    self.document(path), r"只有.*验证.*verified_composite.*exact.*faithful.*commercial-ready",
                    "All exactness and commercial readiness claims require verified validation.",
                )

    def test_documents_define_evidence_constrained_generation_for_natural_model_interaction(self):
        for path in ("SKILL.md", "references/product-truth-protocol.md"):
            with self.subTest(document=path):
                document = self.document(path)
                self.require_rule(
                    document,
                    r"evidence_constrained_generation",
                    "Name the evidence-constrained generative method.",
                )
                self.require_rule(
                    document,
                    r"模特.*手持|手持.*模特|穿戴.*商品",
                    "Route model-held products away from flat pasted cutouts.",
                )
                self.require_rule(
                    document,
                    r"视角.*证据.*模特姿势|产品证据.*角度.*模特姿势",
                    "Choose the evidenced product angle before adapting the model pose.",
                )

    def test_documents_make_material_fidelity_a_blocking_identity_requirement(self):
        for path in (
            "SKILL.md",
            "references/product-truth-protocol.md",
            "references/fidelity-manifest.md",
        ):
            with self.subTest(document=path):
                document = self.document(path)
                self.require_rule(document, r"material_identity_fact_ids", "Persist material identity facts.")
                self.require_rule(document, r"material_comparison", "Require material comparison QA.")
                self.require_rule(
                    document,
                    r"纹理|grain",
                    "Treat texture or grain as evidence-backed product identity.",
                )

    def test_documents_distinguish_reference_match_from_exact_pixel_composite(self):
        for path in ("SKILL.md", "references/fidelity-manifest.md"):
            with self.subTest(document=path):
                document = self.document(path)
                self.require_rule(document, r"verified_reference_match", "Document the generative verified state.")
                self.require_rule(
                    document,
                    r"verified_reference_match.*不.*像素|不.*像素.*verified_reference_match",
                    "Forbid pixel-exact claims for a generated reference match.",
                )

    def test_reference_limit_requires_provenance_atlas_or_blocking(self):
        self.require_rule(
            self.document("references/product-truth-protocol.md"),
            r"参考图上限.*不.*丢弃证据.*确定性.*atlas.*停止",
            "A reference budget cannot silently discard required evidence.",
        )

    def test_manifest_reference_documents_real_cli_and_its_evidence_limit(self):
        reference = self.document("references/fidelity-manifest.md")
        self.require_rule(reference, r"默认.*接受一个.*JSON.*路径", "Preserve the normal one-argument CLI.")
        self.require_rule(reference, r"检查工作流证据.*不.*视觉相似度", "Do not overstate the validator.")
        self.require_rule(reference, r"--emit-prompt-contract.*MANIFEST", "Require the executable prompt-contract mode.")
        self.require_rule(reference, r"验证失败.*不.*prompt_contract", "Invalid input must never emit a contract.")
        self.require_rule(reference, r"不会.*读取.*图像.*计算.*SHA-256", "Separate recorded hashes from file verification.")
        self.require_rule(reference, r"原始分辨率.*landmark_records.*protected_pixels", "Require both landmark and pixel QA.")
        self.assertIn("tests/fixtures/valid-deterministic-composite.json", reference)

    def test_manifest_reference_top_level_count_matches_contract(self):
        reference = self.document("references/fidelity-manifest.md")
        declared_count = re.search(r"以下 (\d+) 个顶层字段必须存在", reference)
        self.assertIsNotNone(declared_count)
        self.assertEqual(int(declared_count.group(1)), len(valid_manifest()))

    def test_commercial_identity_lists_and_verified_landmark_minimum_are_documented(self):
        reference = self.document("references/fidelity-manifest.md")
        self.require_rule(
            reference,
            r"商业模式.*visible_identity_critical_regions.*redrawn_identity_critical_regions.*都必须存在",
            "Both identity lists are mandatory in commercial manifests.",
        )
        self.require_rule(
            reference, r"redrawn_identity_critical_regions.*没有重绘.*\[\]",
            "An empty redrawn list is valid when nothing is redrawn.",
        )
        self.require_rule(
            reference, r"verified_composite.*两个列表的并集.*至少一个.*身份.*ID",
            "Verified delivery requires at least one declared identity landmark.",
        )
        self.assertNotIn("可选 `redrawn_identity_critical_regions`", reference)

    def test_visible_attachment_supporting_topology_must_be_declared_for_landmark_qa(self):
        reference = self.document("references/fidelity-manifest.md")
        self.require_rule(
            reference,
            r"每条.*visible_attachment_points.*拓扑记录.*必须.*visible_identity_critical_regions.*redrawn_identity_critical_regions",
            "Every topology record proving a visible attachment must enter an identity list.",
        )
        self.require_rule(
            reference,
            r"连接点.*拓扑.*verified_composite.*landmark.*QA",
            "The declaration must require landmark QA before verified delivery.",
        )


if __name__ == "__main__":
    unittest.main()

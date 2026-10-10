#!/usr/bin/env python3
"""Validate product-fidelity evidence and optionally emit a bounded prompt contract."""

import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Optional


REQUIRED_TOP_LEVEL_FIELDS = (
    "mode",
    "sources",
    "facts",
    "topology",
    "prompt_claims",
    "reference_plan",
    "scene_plan",
    "method",
    "approval",
    "qa",
    "delivery_status",
)

SUPPORT_SECTIONS = ("facts", "topology", "prompt_claims", "forbidden_mutations")
FACT_AND_TOPOLOGY_STATUSES = {"observed", "user_confirmed", "unknown", "conflict"}
COMMERCIAL_IMPORTANCE_LEVELS = {"high", "medium", "low"}
SOURCE_ROLES = {"product_truth", "detail_truth", "target_scene"}
PRODUCT_EVIDENCE_ROLES = {"product_truth", "detail_truth"}
VALID_MODES = {"commercial_exact_product", "concept_draft"}
VALID_DELIVERY_STATUSES = {
    "blocked",
    "unverified_draft",
    "verified_composite",
    "verified_reference_match",
    "rejected",
}
VALID_METHOD_TYPES = {
    "deterministic_composite",
    "evidence_constrained_generation",
    "masked_generative_contact",
    "full_generative_redraw",
}
LANDMARK_QA_VERDICTS = {"pass", "fail", "mismatch"}
PROTECTED_PIXEL_QA_VERDICTS = {"pass", "drift"}
ALLOWED_CONTACT_EDIT_MASK_ROLES = {
    "contact",
    "occlusion",
    "shadow",
    "hand_contact",
    "hand_occlusion",
    "contact_shadow",
}
CANONICAL_PRESENTATION_SURFACES = {
    "front",
    "left_side",
    "right_side",
    "back",
    "top",
    "bottom",
    "opening",
    "interior",
}
PERMITTED_SCENE_ADJUSTMENTS = {
    "model_pose",
    "hand_placement",
    "crop",
    "product_position",
}
# This deliberately narrow mapping is the only way a source's declared view
# can establish support for a visible product surface.  It avoids treating a
# category label or a mirrored image as evidence of an unphotographed side.
ORIENTATION_SURFACES = {
    "front": {"front"},
    "front_left_three_quarter": {"front", "left_side"},
    "front_right_three_quarter": {"front", "right_side"},
    "left_side": {"left_side"},
    "right_side": {"right_side"},
    "back": {"back"},
    "back_left_three_quarter": {"back", "left_side"},
    "back_right_three_quarter": {"back", "right_side"},
    "top": {"top"},
    "bottom": {"bottom"},
}
SOURCE_VIEW_SURFACES = ORIENTATION_SURFACES


def error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def is_sha256(value: Any) -> bool:
    """Return whether value is a canonical SHA-256 hex digest."""
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


class DuplicateJSONKeyError(ValueError):
    """A JSON object contains an ambiguous repeated property."""


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Called for every parsed object, including objects nested in arrays."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"Duplicate JSON key: {key!r}.")
        result[key] = value
    return result


def load_manifest(path: Path) -> Any:
    """Load one manifest file; I/O and JSON errors are handled by ``main``."""
    with path.open(encoding="utf-8") as manifest_file:
        return json.load(manifest_file, object_pairs_hook=unique_json_object)


def is_valid_evidence_region(evidence: Any, source_ids: set[str]) -> bool:
    """Return whether one evidence item names a known source and a region."""
    if not isinstance(evidence, dict):
        return False
    source_id = evidence.get("source_id")
    if not isinstance(source_id, str) or not source_id or source_id not in source_ids:
        return False
    return is_valid_normalized_region(evidence.get("normalized_region"))


def is_valid_normalized_region(region: Any) -> bool:
    """Return whether a source or atlas region is a finite normalized rectangle."""
    if not isinstance(region, list) or len(region) != 4:
        return False
    if not all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (isinstance(value, int) or math.isfinite(value))
        for value in region
    ):
        return False
    if any(
        isinstance(value, int)
        and not isinstance(value, bool)
        and value.bit_length() >= 1024
        for value in region
    ):
        return False

    x, y, width, height = region
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return False
    if x > 1 or y > 1 or width > 1 or height > 1:
        return False
    return (
        x + width <= 1
        and y + height <= 1
    )


def has_oversized_evidence_integer(item: Any) -> bool:
    """Detect integers too large for a normalized evidence coordinate."""
    if not isinstance(item, dict) or not isinstance(item.get("evidence"), list):
        return False
    for evidence in item["evidence"]:
        region = evidence.get("normalized_region") if isinstance(evidence, dict) else None
        if isinstance(region, list) and any(
            isinstance(value, int)
            and not isinstance(value, bool)
            and value.bit_length() >= 1024
            for value in region
        ):
            return True
    return False


def evidence_error_code(item: Any, source_ids: set[str]) -> Optional[str]:
    """Return the stable error code when an item lacks usable evidence."""
    if has_source_backed_evidence(item, source_ids):
        return None
    if has_oversized_evidence_integer(item):
        return "INVALID_EVIDENCE_REGION"
    return "MISSING_FACT_EVIDENCE"


def has_source_backed_evidence(item: Any, source_ids: set[str]) -> bool:
    """Return whether an item has at least one usable, source-linked region."""
    if not isinstance(item, dict):
        return False
    evidence_items = item.get("evidence")
    return isinstance(evidence_items, list) and any(
        is_valid_evidence_region(evidence, source_ids) for evidence in evidence_items
    )


def has_disallowed_product_evidence(
    item: Any, source_ids: set[str], product_evidence_source_ids: set[str]
) -> bool:
    """Return whether a fact/topology record tries to use a non-product source."""
    if not isinstance(item, dict) or not isinstance(item.get("evidence"), list):
        return False
    return any(
        isinstance(evidence, dict)
        and isinstance(evidence.get("source_id"), str)
        and evidence["source_id"] in source_ids
        and evidence["source_id"] not in product_evidence_source_ids
        for evidence in item["evidence"]
    )


def string_ids(value: Any) -> set[str]:
    """Return the string IDs in a manifest list without trusting its shape."""
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def final_region_ids(data: dict[str, Any]) -> set[str]:
    """Collect IDs declared visible or redrawn in the final presentation."""
    scene_plan = data.get("scene_plan")
    if not isinstance(scene_plan, dict):
        return set()

    return set(scene_plan.get("visible_identity_critical_regions", [])) | set(
        scene_plan.get("redrawn_identity_critical_regions", [])
    )


def validate_scene_plan_shape(data: dict[str, Any]) -> list[dict[str, str]]:
    """Validate final-region declarations before they drive high-risk gating."""
    scene_plan = data["scene_plan"]
    if not isinstance(scene_plan, dict):
        return [error("INVALID_FIELD_TYPE", "Field scene_plan must be an object.")]

    errors: list[dict[str, str]] = []
    for field in (
        "visible_identity_critical_regions",
        "redrawn_identity_critical_regions",
    ):
        if field not in scene_plan:
            if data.get("mode") == "commercial_exact_product":
                errors.append(
                    error(
                        "MISSING_IDENTITY_REGION_LIST",
                        f"commercial_exact_product requires scene_plan.{field}.",
                    )
                )
            continue
        region_ids = scene_plan[field]
        if not isinstance(region_ids, list):
            errors.append(
                error("INVALID_SECTION_TYPE", f"Field scene_plan.{field} must be an array.")
            )
            continue
        for index, region_id in enumerate(region_ids):
            if not isinstance(region_id, str) or not region_id.strip():
                errors.append(
                    error(
                        "INVALID_REGION_ID",
                        f"Field scene_plan.{field} item {index} must be a non-empty string.",
                    )
                )
    return errors


def validate_verified_identity_declaration(data: dict[str, Any]) -> list[dict[str, str]]:
    """Verified commercial delivery must name at least one QA-tracked identity record."""
    if (
        data.get("mode") == "commercial_exact_product"
        and data.get("delivery_status") in {"verified_composite", "verified_reference_match"}
        and not final_region_ids(data)
    ):
        return [
            error(
                "MISSING_IDENTITY_LANDMARK_DECLARATION",
                "Verified delivery requires at least one visible or redrawn identity landmark.",
            )
        ]
    return []


def is_nonempty_string_list(value: Any) -> bool:
    """Return whether value is a nonempty list of nonempty strings."""
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def is_string_list(value: Any) -> bool:
    """Return whether value is a list whose members are nonempty strings."""
    return isinstance(value, list) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def validate_presentation_envelope(
    data: dict[str, Any], source_roles: dict[str, str]
) -> list[dict[str, str]]:
    """Enforce commercial scenes never reveal product views missing from evidence."""
    if data.get("mode") != "commercial_exact_product":
        return []

    scene_plan = data.get("scene_plan")
    if not isinstance(scene_plan, dict):
        return []

    errors: list[dict[str, str]] = []
    envelope = scene_plan.get("presentation_envelope")
    if not isinstance(envelope, dict):
        return [
            error(
                "INVALID_PRESENTATION_ENVELOPE",
                "commercial_exact_product requires scene_plan.presentation_envelope to be an object.",
            )
        ]

    envelope_fields = (
        "supported_orientations",
        "visible_surfaces",
        "must_remain_hidden",
    )
    for field in envelope_fields:
        if not is_nonempty_string_list(envelope.get(field)):
            errors.append(
                error(
                    "INVALID_PRESENTATION_ENVELOPE_FIELD",
                    f"presentation_envelope.{field} must be a nonempty array of non-empty strings.",
                )
            )

    surface_evidence = envelope.get("surface_evidence")
    if not isinstance(surface_evidence, dict):
        errors.append(
            error(
                "INVALID_SURFACE_EVIDENCE",
                "presentation_envelope.surface_evidence must be an object.",
            )
        )
    else:
        for surface, evidence_source_ids in surface_evidence.items():
            if not isinstance(surface, str) or not surface.strip():
                errors.append(
                    error(
                        "INVALID_SURFACE_EVIDENCE_SURFACE",
                        "surface_evidence keys must be non-empty surface strings.",
                    )
                )
            if not is_nonempty_string_list(evidence_source_ids):
                errors.append(
                    error(
                        "INVALID_SURFACE_EVIDENCE_SOURCES",
                        "Each surface_evidence value must be a nonempty array of source IDs.",
                    )
                )

    final_orientation = scene_plan.get("final_orientation")
    if not isinstance(final_orientation, str) or not final_orientation.strip():
        errors.append(
            error(
                "INVALID_FINAL_PRESENTATION_FIELD",
                "scene_plan.final_orientation must be a non-empty string.",
            )
        )
    final_visible_surfaces = scene_plan.get("final_visible_surfaces")
    if not is_nonempty_string_list(final_visible_surfaces):
        errors.append(
            error(
                "INVALID_FINAL_PRESENTATION_FIELD",
                "scene_plan.final_visible_surfaces must be a nonempty array of non-empty strings.",
            )
        )

    if not isinstance(scene_plan.get("mirrored_product_view"), bool):
        errors.append(
            error(
                "INVALID_MIRRORED_PRODUCT_VIEW",
                "scene_plan.mirrored_product_view must be boolean.",
            )
        )

    forbidden_regions = scene_plan.get("forbidden_invented_regions")
    if not is_nonempty_string_list(forbidden_regions):
        errors.append(
            error(
                "INVALID_FORBIDDEN_INVENTED_REGIONS",
                "scene_plan.forbidden_invented_regions must be a nonempty array of non-empty strings.",
            )
        )

    permitted_adjustments = scene_plan.get("permitted_scene_adjustments")
    if not is_nonempty_string_list(permitted_adjustments):
        errors.append(
            error(
                "INVALID_PERMITTED_SCENE_ADJUSTMENTS",
                "scene_plan.permitted_scene_adjustments must be a nonempty array of non-empty strings.",
            )
        )
    applied_adjustments = scene_plan.get("applied_scene_adjustments")
    if not is_string_list(applied_adjustments):
        errors.append(
            error(
                "INVALID_APPLIED_SCENE_ADJUSTMENTS",
                "scene_plan.applied_scene_adjustments must be an array of non-empty strings.",
            )
        )

    if is_nonempty_string_list(envelope.get("supported_orientations")):
        for orientation in envelope["supported_orientations"]:
            if orientation not in ORIENTATION_SURFACES:
                errors.append(
                    error(
                        "INVALID_PRESENTATION_ORIENTATION",
                        f"Unsupported presentation orientation {orientation}.",
                    )
                )
    if isinstance(final_orientation, str) and final_orientation.strip():
        if final_orientation not in ORIENTATION_SURFACES:
            errors.append(
                error(
                    "INVALID_PRESENTATION_ORIENTATION",
                    f"Unsupported final presentation orientation {final_orientation}.",
                )
            )

    if errors:
        return errors

    product_views: set[str] = set()
    sources_by_id: dict[str, dict[str, Any]] = {}
    for source in data["sources"]:
        if not isinstance(source, dict):
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str):
            continue
        sources_by_id[source_id] = source
        if source_roles.get(source_id) not in PRODUCT_EVIDENCE_ROLES:
            continue
        view = source.get("view")
        if not isinstance(view, str) or not view.strip():
            errors.append(
                error(
                    "INVALID_PRODUCT_SOURCE_VIEW",
                    f"Product evidence source {source_id} requires a non-empty view string.",
                )
            )
        elif view not in ORIENTATION_SURFACES:
            errors.append(
                error(
                    "INVALID_PRODUCT_SOURCE_VIEW",
                    f"Product evidence source {source_id} has unsupported view {view}.",
                )
            )
        else:
            product_views.add(view)

    supported_orientations = set(envelope["supported_orientations"])
    visible_surfaces = set(envelope["visible_surfaces"])
    hidden_surfaces = set(envelope["must_remain_hidden"])
    final_surfaces = set(final_visible_surfaces)
    forbidden_surface_set = set(forbidden_regions)

    compatible_envelope_surfaces: set[str] = set()
    for orientation in supported_orientations:
        compatible_envelope_surfaces.update(ORIENTATION_SURFACES[orientation])
    for surface in sorted(visible_surfaces - compatible_envelope_surfaces):
        errors.append(
            error(
                "INCOMPATIBLE_ENVELOPE_ORIENTATION_SURFACE",
                f"Visible surface {surface} is incompatible with every supported orientation.",
            )
        )

    for surface in sorted(visible_surfaces):
        if surface not in surface_evidence:
            errors.append(
                error(
                    "MISSING_SURFACE_EVIDENCE",
                    f"Visible surface {surface} lacks source-backed surface_evidence.",
                )
            )
    for surface in sorted(surface_evidence):
        if surface not in visible_surfaces:
            errors.append(
                error(
                    "UNDECLARED_SURFACE_EVIDENCE",
                    f"surface_evidence for {surface} is not an allowed visible surface.",
                )
            )
            continue
        for source_id in surface_evidence[surface]:
            source = sources_by_id.get(source_id)
            if source is None:
                errors.append(
                    error(
                        "UNKNOWN_SURFACE_EVIDENCE_SOURCE",
                        f"Surface {surface} cites unknown source {source_id}.",
                    )
                )
                continue
            if source_roles.get(source_id) not in PRODUCT_EVIDENCE_ROLES:
                errors.append(
                    error(
                        "INVALID_SURFACE_EVIDENCE_SOURCE_ROLE",
                        f"Surface {surface} source {source_id} is not product evidence.",
                    )
                )
                continue
            source_view = source.get("view")
            supported_source_surfaces = (
                SOURCE_VIEW_SURFACES.get(source_view, set())
                if isinstance(source_view, str)
                else set()
            )
            if surface not in supported_source_surfaces:
                errors.append(
                    error(
                        "UNSUPPORTED_SURFACE_EVIDENCE_VIEW",
                        f"Source {source_id} view {source_view!r} cannot support surface {surface}.",
                    )
                )

    for orientation in sorted(supported_orientations - product_views):
        errors.append(
            error(
                "UNSUPPORTED_ENVELOPE_ORIENTATION",
                f"Presentation orientation {orientation} lacks PRODUCT_TRUTH or DETAIL_TRUTH source-view evidence.",
            )
        )
    if final_orientation not in supported_orientations:
        errors.append(
            error(
                "UNSUPPORTED_FINAL_ORIENTATION",
                f"Final orientation {final_orientation} is outside the source-supported presentation envelope.",
            )
        )
    elif final_orientation in ORIENTATION_SURFACES:
        for surface in sorted(final_surfaces - ORIENTATION_SURFACES[final_orientation]):
            errors.append(
                error(
                    "INCOMPATIBLE_FINAL_ORIENTATION_SURFACE",
                    f"Final surface {surface} is incompatible with orientation {final_orientation}.",
                )
            )
    for surface in sorted(final_surfaces - visible_surfaces):
        errors.append(
            error(
                "UNSUPPORTED_VISIBLE_SURFACE",
                f"Final visible surface {surface} is outside the presentation envelope.",
            )
        )
    for surface in sorted(final_surfaces - set(surface_evidence)):
        errors.append(
            error(
                "UNSUPPORTED_FINAL_VISIBLE_SURFACE_EVIDENCE",
                f"Final visible surface {surface} lacks source-backed surface evidence.",
            )
        )
    for surface in sorted(final_surfaces & hidden_surfaces):
        errors.append(
            error(
                "VISIBLE_MUST_REMAIN_HIDDEN",
                f"Final visible surface {surface} is declared must_remain_hidden.",
            )
        )
    for surface in sorted(final_surfaces & forbidden_surface_set):
        errors.append(
            error(
                "VISIBLE_FORBIDDEN_REGION",
                f"Final visible surface {surface} is a forbidden invented region.",
            )
        )
    for surface in sorted(forbidden_surface_set - hidden_surfaces):
        errors.append(
            error(
                "UNHIDDEN_FORBIDDEN_REGION",
                f"Forbidden invented region {surface} must be listed in must_remain_hidden.",
            )
        )

    if scene_plan["mirrored_product_view"] is True:
        errors.append(
            error(
                "MIRRORED_PRODUCT_VIEW_UNSUPPORTED",
                "commercial_exact_product requires independently sourced, unmirrored product views.",
            )
        )
        mirrored_unsupported = final_surfaces - product_views
        for surface in sorted(mirrored_unsupported):
            errors.append(
                error(
                    "UNSUPPORTED_MIRRORED_PRODUCT_VIEW",
                    f"Mirroring cannot substitute for unphotographed product surface {surface}.",
                )
            )

    permitted_set = set(permitted_adjustments)
    for adjustment in sorted(permitted_set - PERMITTED_SCENE_ADJUSTMENTS):
        errors.append(
            error(
                "UNSUPPORTED_SCENE_ADJUSTMENT",
                f"Scene adjustment {adjustment} would alter the product envelope.",
            )
        )
    for adjustment in sorted(set(applied_adjustments) - permitted_set):
        errors.append(
            error(
                "UNPERMITTED_SCENE_ADJUSTMENT",
                f"Applied scene adjustment {adjustment} is not permitted by the scene plan.",
            )
        )

    surface_label_collections = (
        envelope["visible_surfaces"],
        envelope["must_remain_hidden"],
        final_visible_surfaces,
        forbidden_regions,
    )
    for collection in surface_label_collections:
        for surface in collection:
            if surface not in CANONICAL_PRESENTATION_SURFACES:
                errors.append(
                    error(
                        "UNKNOWN_SURFACE_LABEL",
                        f"Unknown canonical presentation surface {surface}.",
                    )
                )
    for surface in surface_evidence:
        if surface not in CANONICAL_PRESENTATION_SURFACES:
            errors.append(
                error(
                    "UNKNOWN_SURFACE_LABEL",
                    f"Unknown canonical presentation surface {surface}.",
                )
            )
    if visible_surfaces & hidden_surfaces:
        errors.append(
            error(
                "OVERLAPPING_CANONICAL_SURFACE_ENVELOPE",
                "visible_surfaces and must_remain_hidden must be disjoint.",
            )
        )
    if visible_surfaces | hidden_surfaces != CANONICAL_PRESENTATION_SURFACES:
        errors.append(
            error(
                "INCOMPLETE_CANONICAL_SURFACE_ENVELOPE",
                "visible_surfaces and must_remain_hidden must account for every canonical surface.",
            )
        )
    return errors


def resolved_support_record(record: dict[str, Any], data: dict[str, Any]) -> bool:
    """Share evidence/approval resolution across attachment checks and export."""
    product_ids = {
        source["id"] for source in data["sources"]
        if source["role"] in PRODUCT_EVIDENCE_ROLES
    }
    all_ids = {source["id"] for source in data["sources"]}
    approval = data.get("approval")
    confirmed_ids = string_ids(
        approval.get("confirmed_fact_ids") if isinstance(approval, dict) else None
    )
    return (
        (record.get("status") == "observed" or (
            record.get("status") == "user_confirmed" and record["id"] in confirmed_ids
        ))
        and has_source_backed_evidence(record, product_ids)
        and not has_disallowed_product_evidence(record, all_ids, product_ids)
    )


def validate_visible_attachment_points(data: dict[str, Any]) -> list[dict[str, str]]:
    """Visible attachment labels require explicit resolved topology endpoints."""
    if data["mode"] != "commercial_exact_product":
        return []
    envelope = data["scene_plan"].get("presentation_envelope")
    if not isinstance(envelope, dict):
        return []  # The envelope validator reports the malformed parent.
    points = envelope.get("visible_attachment_points")
    if not is_string_list(points) or len(points) != len(set(points)):
        return [error(
            "INVALID_VISIBLE_ATTACHMENT_POINTS",
            "visible_attachment_points must be an array of unique nonempty strings (empty allowed).",
        )]
    endpoints: set[str] = set()
    errors: list[dict[str, str]] = []
    identity_ids = final_region_ids(data)
    for component in data["topology"]:
        if resolved_support_record(component, data) and is_string_list(component.get("endpoints")):
            endpoints.update(component["endpoints"])
            if set(component["endpoints"]) & set(points) and component["id"] not in identity_ids:
                errors.append(error(
                    "ATTACHMENT_TOPOLOGY_NOT_IDENTITY_TRACKED",
                    f"Visible attachment topology {component['id']} must be declared identity-critical for landmark QA.",
                ))
    errors.extend(error(
        "UNSUPPORTED_VISIBLE_ATTACHMENT_POINT",
        f"Visible attachment point {point} has no resolved source-backed topology endpoint.",
    ) for point in points if point not in endpoints)
    return errors


def validate_support_record_shapes(data: dict[str, Any]) -> list[dict[str, str]]:
    """Reject malformed support sections before resolution can skip their records."""
    errors: list[dict[str, str]] = []
    for section in SUPPORT_SECTIONS:
        records = data.get(section, [])
        if not isinstance(records, list):
            errors.append(
                error("INVALID_SECTION_TYPE", f"Section {section} must be an array.")
            )
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(
                    error(
                        "INVALID_RECORD_TYPE",
                        f"Section {section} record {index} must be an object.",
                    )
                )
                continue
            record_id = record.get("id")
            if not isinstance(record_id, str) or not record_id.strip():
                errors.append(
                    error(
                        "MISSING_RECORD_ID",
                        f"Section {section} record {index} requires a non-empty string id.",
                    )
                )
            if (
                section in ("facts", "topology")
                and (
                    not isinstance(record.get("status"), str)
                    or record["status"] not in FACT_AND_TOPOLOGY_STATUSES
                )
            ):
                errors.append(
                    error(
                        "INVALID_STATUS",
                        f"Section {section} record {index} has an invalid status.",
                    )
                )
            if section == "facts":
                if "commercial_importance" not in record:
                    errors.append(
                        error(
                            "MISSING_COMMERCIAL_IMPORTANCE",
                            f"Fact record {index} requires commercial_importance.",
                        )
                    )
                elif (
                    not isinstance(record["commercial_importance"], str)
                    or record["commercial_importance"]
                    not in COMMERCIAL_IMPORTANCE_LEVELS
                ):
                    errors.append(
                        error(
                            "INVALID_COMMERCIAL_IMPORTANCE",
                            f"Fact record {index} commercial_importance must be high, medium, or low.",
                        )
                    )
    return errors


def validate_support_id_uniqueness(data: dict[str, Any]) -> list[dict[str, str]]:
    """Ensure facts and topology have one unambiguous claim-support namespace."""
    errors: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for section in ("facts", "topology"):
        for record in data[section]:
            record_id = record["id"]
            if record_id in seen_ids:
                errors.append(
                    error(
                        "DUPLICATE_SUPPORT_ID",
                        f"Support id {record_id} is duplicated in facts or topology.",
                    )
                )
            else:
                seen_ids.add(record_id)
    return errors


def validate_identity_region_references(data: dict[str, Any]) -> list[dict[str, str]]:
    """Resolve scene identity IDs before they can control QA or uncertainty gates."""
    support_ids = {
        record["id"] for section in ("facts", "topology") for record in data[section]
    }
    return [error(
        "UNKNOWN_IDENTITY_REGION_ID",
        f"Identity region {region_id} does not resolve to a fact or topology ID.",
    ) for region_id in sorted(final_region_ids(data) - support_ids)]


def validate_source_shapes(data: dict[str, Any]) -> list[dict[str, str]]:
    """Require sources to be explicit before reference coverage is calculated."""
    sources = data["sources"]
    if not isinstance(sources, list):
        return [error("INVALID_SOURCES_COLLECTION", "Field sources must be an array.")]

    errors: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(error("INVALID_SOURCE_RECORD", f"Source {index} must be an object."))
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            errors.append(
                error("INVALID_SOURCE_ID", f"Source {index} requires a non-empty string id.")
            )
            continue
        if source_id in seen_ids:
            errors.append(error("DUPLICATE_SOURCE_ID", f"Source id {source_id} is ambiguous."))
        else:
            seen_ids.add(source_id)
        if not isinstance(source.get("required"), bool):
            errors.append(
                error("INVALID_SOURCE_REQUIRED_FLAG", f"Source {source_id} required must be boolean.")
            )
        source_hash = source.get("sha256")
        if source_hash is None:
            errors.append(error("MISSING_SOURCE_HASH", f"Source {source_id} requires sha256."))
        elif not is_sha256(source_hash):
            errors.append(
                error("INVALID_SOURCE_HASH", f"Source {source_id} sha256 must be 64 hex characters.")
            )
        source_role = source.get("role")
        if not isinstance(source_role, str) or source_role not in SOURCE_ROLES:
            errors.append(
                error("INVALID_SOURCE_ROLE", f"Source {source_id} has an unsupported role.")
            )
    return errors


def validate_reference_plan(
    reference_plan: Any,
    source_ids: set[str],
    required_source_ids: set[str],
    source_roles: dict[str, str],
) -> list[dict[str, str]]:
    """Fail closed when a limited reference plan loses product-source provenance."""
    if not isinstance(reference_plan, dict):
        return [error("INVALID_REFERENCE_PLAN", "Field reference_plan must be an object.")]

    selected_source_ids = reference_plan.get("selected_source_ids")
    atlases = reference_plan.get("deterministic_atlases")
    reference_limit = reference_plan.get("tool_reference_limit")
    if (
        not isinstance(selected_source_ids, list)
        or not isinstance(atlases, list)
        or not isinstance(reference_limit, int)
        or isinstance(reference_limit, bool)
        or reference_limit < 1
    ):
        return [
            error(
                "INVALID_REFERENCE_PLAN",
                "reference_plan requires an integer tool_reference_limit and reference arrays.",
            )
        ]

    errors: list[dict[str, str]] = []
    atlas_by_id: dict[str, dict[str, Any]] = {}
    for index, atlas in enumerate(atlases):
        if not isinstance(atlas, dict):
            errors.append(
                error("INVALID_ATLAS_RECORD", f"Atlas {index} must be an object.")
            )
            continue

        atlas_id = atlas.get("id")
        if not isinstance(atlas_id, str) or not atlas_id.strip():
            errors.append(error("MISSING_ATLAS_ID", f"Atlas {index} requires a non-empty id."))
            continue
        if atlas_id in atlas_by_id:
            errors.append(
                error("DUPLICATE_ATLAS_ID", f"Atlas id {atlas_id} is ambiguous.")
            )
            continue
        atlas_by_id[atlas_id] = atlas

        if atlas.get("deterministic") is not True:
            errors.append(
                error("NONDETERMINISTIC_ATLAS", f"Atlas {atlas_id} must be deterministic."))
        atlas_hash = atlas.get("sha256")
        if atlas_hash is None:
            errors.append(
                error("MISSING_ATLAS_SOURCE_HASH", f"Atlas {atlas_id} requires its sha256."))
        elif not is_sha256(atlas_hash):
            errors.append(
                error(
                    "INVALID_ATLAS_SOURCE_HASH",
                    f"Atlas {atlas_id} sha256 must be 64 hex characters.",
                )
            )

        parent_source_ids = atlas.get("parent_source_ids")
        if (
            not isinstance(parent_source_ids, list)
            or not parent_source_ids
            or any(
                not isinstance(parent_id, str) or not parent_id.strip()
                for parent_id in parent_source_ids
            )
            or len(set(parent_source_ids)) != len(parent_source_ids)
        ):
            errors.append(
                error(
                    "INVALID_ATLAS_PARENT_SOURCE_IDS",
                    f"Atlas {atlas_id} requires unique non-empty parent_source_ids.",
                )
            )
            parent_source_ids = []
        else:
            for parent_id in parent_source_ids:
                if parent_id not in source_ids:
                    errors.append(
                        error(
                            "UNKNOWN_ATLAS_PARENT_SOURCE",
                            f"Atlas {atlas_id} names unknown parent source {parent_id}.",
                        )
                    )
                elif source_roles[parent_id] not in PRODUCT_EVIDENCE_ROLES:
                    errors.append(
                        error(
                            "INVALID_ATLAS_PARENT_SOURCE_ROLE",
                            f"Atlas {atlas_id} parent {parent_id} is not product evidence.",
                        )
                    )

        crop_mappings = atlas.get("crop_mappings")
        if not isinstance(crop_mappings, list):
            errors.append(
                error(
                    "INVALID_ATLAS_CROP_MAPPINGS",
                    f"Atlas {atlas_id} crop_mappings must be an array.",
                )
            )
            continue

        mapped_parent_ids: set[str] = set()
        prior_mappings: list[dict[str, Any]] = []
        output_regions: list[tuple[str, list[int | float]]] = []
        for mapping_index, crop_mapping in enumerate(crop_mappings):
            if not isinstance(crop_mapping, dict):
                errors.append(
                    error(
                        "INVALID_ATLAS_CROP_MAPPING",
                        f"Atlas {atlas_id} crop mapping {mapping_index} must be an object.",
                    )
                )
                continue
            if any(crop_mapping == prior_mapping for prior_mapping in prior_mappings):
                errors.append(
                    error(
                        "DUPLICATE_ATLAS_CROP_MAPPING",
                        f"Atlas {atlas_id} crop mapping {mapping_index} duplicates another mapping.",
                    )
                )
            prior_mappings.append(crop_mapping)
            parent_id = crop_mapping.get("parent_source_id")
            if not isinstance(parent_id, str) or parent_id not in parent_source_ids:
                errors.append(
                    error(
                        "INVALID_ATLAS_CROP_MAPPING",
                        f"Atlas {atlas_id} crop mapping {mapping_index} must name a declared parent.",
                    )
                )
            else:
                mapped_parent_ids.add(parent_id)
            if not is_valid_normalized_region(crop_mapping.get("source_normalized_region")):
                errors.append(
                    error(
                        "INVALID_ATLAS_CROP_MAPPING",
                        f"Atlas {atlas_id} crop mapping {mapping_index} has an invalid source region.",
                    )
                )
            atlas_region = crop_mapping.get("atlas_normalized_region")
            if not is_valid_normalized_region(atlas_region):
                errors.append(
                    error(
                        "INVALID_ATLAS_CROP_MAPPING",
                        f"Atlas {atlas_id} crop mapping {mapping_index} has an invalid atlas region.",
                    )
                )
            elif isinstance(parent_id, str):
                for other_parent_id, other_region in output_regions:
                    if (
                        parent_id != other_parent_id
                        and normalized_regions_overlap(atlas_region, other_region)
                    ):
                        errors.append(
                            error(
                                "OVERLAPPING_ATLAS_OUTPUT_REGION",
                                f"Atlas {atlas_id} crop mapping {mapping_index} overlaps another parent output.",
                            )
                        )
                        break
                output_regions.append((parent_id, atlas_region))
            if (
                "identity_landmarks_readable" in crop_mapping
                and not isinstance(crop_mapping["identity_landmarks_readable"], bool)
            ):
                errors.append(
                    error(
                        "INVALID_ATLAS_IDENTITY_LANDMARKS_READABLE",
                        f"Atlas {atlas_id} crop mapping {mapping_index} readability must be boolean.",
                    )
                )
            elif crop_mapping.get("identity_landmarks_readable") is False:
                errors.append(
                    error(
                        "UNREADABLE_IDENTITY_CRITICAL_ATLAS_CROP",
                        f"Atlas {atlas_id} crop mapping {mapping_index} marks identity landmarks unreadable.",
                    )
                )
        for parent_id in parent_source_ids:
            if parent_id not in mapped_parent_ids:
                errors.append(
                    error(
                        "MISSING_ATLAS_CROP_MAPPING",
                        f"Atlas {atlas_id} lacks a crop mapping for parent {parent_id}.",
                    )
                )

    if len(selected_source_ids) > reference_limit:
        errors.append(
            error(
                "REFERENCE_LIMIT_EXCEEDED",
                f"Selected {len(selected_source_ids)} references exceed limit {reference_limit}.",
            )
        )

    selected_ids: set[str] = set()
    seen_selected_reference_ids: set[str] = set()
    for index, selected_id in enumerate(selected_source_ids):
        if not isinstance(selected_id, str) or not selected_id.strip():
            errors.append(
                error(
                    "INVALID_SELECTED_REFERENCE",
                    f"Selected reference {index} must be a non-empty string.",
                )
            )
            continue
        if selected_id in seen_selected_reference_ids:
            errors.append(
                error(
                    "DUPLICATE_SELECTED_REFERENCE",
                    f"Selected reference {selected_id} appears more than once.",
                )
            )
            continue
        seen_selected_reference_ids.add(selected_id)
        if selected_id not in source_ids and selected_id not in atlas_by_id:
            errors.append(
                error(
                    "UNKNOWN_SELECTED_REFERENCE",
                    f"Selected reference {selected_id} is neither a source nor an atlas.",
                )
            )
            continue
        if selected_id in source_ids and selected_id in atlas_by_id:
            errors.append(
                error(
                    "AMBIGUOUS_REFERENCE_ID",
                    f"Selected reference {selected_id} names both a source and an atlas.",
                )
            )
            continue
        selected_ids.add(selected_id)

    coverage = selected_ids & source_ids
    for atlas_id in selected_ids & set(atlas_by_id):
        parent_source_ids = atlas_by_id[atlas_id].get("parent_source_ids")
        if isinstance(parent_source_ids, list):
            coverage.update(
                parent_id for parent_id in parent_source_ids if isinstance(parent_id, str)
            )
    for source_id in sorted(required_source_ids - coverage):
        errors.append(
            error(
                "UNCOVERED_REQUIRED_SOURCE",
                f"Required source {source_id} is absent from selected references and atlases.",
            )
        )
    return errors


def normalized_regions_overlap(
    first_region: list[Any], second_region: list[Any]
) -> bool:
    """Return whether normalized rectangles share positive area, not just an edge."""
    first_x, first_y, first_width, first_height = first_region
    second_x, second_y, second_width, second_height = second_region
    return (
        max(first_x, second_x) < min(first_x + first_width, second_x + second_width)
        and max(first_y, second_y) < min(first_y + first_height, second_y + second_height)
    )


def validate_protected_product_regions(
    protected_regions: Any,
    source_ids: set[str],
    source_roles: dict[str, str],
) -> list[dict[str, str]]:
    """Require traceable product regions that downstream QA can compare."""
    if not isinstance(protected_regions, list) or not protected_regions:
        return [
            error(
                "MISSING_PROTECTED_PRODUCT_REGION",
                "Method requires at least one protected, source-backed product region.",
            )
        ]

    errors: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, region in enumerate(protected_regions):
        if not isinstance(region, dict):
            errors.append(
                error(
                    "INVALID_PROTECTED_PRODUCT_REGION",
                    f"Protected region {index} must be an object.",
                )
            )
            continue
        region_id = region.get("id")
        if not isinstance(region_id, str) or not region_id.strip():
            errors.append(
                error(
                    "INVALID_PROTECTED_PRODUCT_REGION",
                    f"Protected region {index} requires a non-empty id.",
                )
            )
        elif region_id in seen_ids:
            errors.append(
                error(
                    "INVALID_PROTECTED_PRODUCT_REGION",
                    f"Protected region id {region_id} is ambiguous.",
                )
            )
        else:
            seen_ids.add(region_id)

        source_id = region.get("source_id")
        if not isinstance(source_id, str) or source_id not in source_ids:
            errors.append(
                error(
                    "INVALID_PROTECTED_PRODUCT_REGION",
                    f"Protected region {index} must name a known source_id.",
                )
            )
        elif source_roles.get(source_id) not in PRODUCT_EVIDENCE_ROLES:
            errors.append(
                error(
                    "INVALID_PROTECTED_PRODUCT_REGION",
                    f"Protected region {index} must use a product-evidence source.",
                )
            )
        if not is_valid_normalized_region(region.get("normalized_region")):
            errors.append(
                error(
                    "INVALID_PROTECTED_PRODUCT_REGION",
                    f"Protected region {index} requires a finite normalized rectangle.",
                )
            )
    return errors


def validate_allowed_contact_edit_mask(allowed_edit_mask: Any) -> list[dict[str, str]]:
    """Allow generative edits only where product contact, occlusion, or shadow needs it."""
    if not isinstance(allowed_edit_mask, dict):
        return [
            error(
                "INVALID_ALLOWED_EDIT_MASK",
                "masked_generative_contact requires an allowed_edit_mask object.",
            )
        ]
    regions = allowed_edit_mask.get("regions")
    if (
        not isinstance(regions, list)
        or not regions
        or any(
            not isinstance(role, str)
            or not role.strip()
            or role not in ALLOWED_CONTACT_EDIT_MASK_ROLES
            for role in regions
        )
    ):
        return [
            error(
                "INVALID_ALLOWED_EDIT_MASK",
                "allowed_edit_mask.regions must be nonempty contact, occlusion, or shadow roles.",
            )
        ]
    return []


def validate_method(
    method: Any,
    source_ids: set[str],
    source_roles: dict[str, str],
) -> list[dict[str, str]]:
    """Validate the bounded production method and its product-protection proof."""
    if not isinstance(method, dict):
        return [error("INVALID_METHOD", "Field method must be an object.")]

    method_type = method.get("type")
    if not isinstance(method_type, str) or method_type not in VALID_METHOD_TYPES:
        return [
            error(
                "INVALID_METHOD_TYPE",
                "method.type must be deterministic_composite, evidence_constrained_generation, masked_generative_contact, or full_generative_redraw.",
            )
        ]

    errors: list[dict[str, str]] = []
    capabilities = method.get("tool_capabilities")
    if capabilities is not None and not isinstance(capabilities, dict):
        errors.append(
            error("INVALID_TOOL_CAPABILITIES", "tool_capabilities must be an object.")
        )
        capabilities = None

    if method_type in {"deterministic_composite", "masked_generative_contact"}:
        if method.get("product_pixels_preserved") is not True:
            errors.append(
                error(
                    "PRODUCT_PIXELS_NOT_PRESERVED",
                    f"{method_type} requires product_pixels_preserved to be literal true.",
                )
            )
        errors.extend(
            validate_protected_product_regions(
                method.get("protected_regions"), source_ids, source_roles
            )
        )

    if method_type == "masked_generative_contact":
        if not isinstance(capabilities, dict) or (
            capabilities.get("supports_mask") is not True
            or capabilities.get("supports_layer_lock") is not True
        ):
            errors.append(
                error(
                    "MISSING_PROTECTIVE_TOOL_CAPABILITY",
                    "masked_generative_contact requires literal true supports_mask and supports_layer_lock.",
                )
            )
        errors.extend(validate_allowed_contact_edit_mask(method.get("allowed_edit_mask")))

    return errors


def selected_reference_coverage(reference_plan: Any) -> set[str]:
    """Return source IDs carried directly or by a declared deterministic atlas."""
    if not isinstance(reference_plan, dict):
        return set()
    selected = reference_plan.get("selected_source_ids")
    atlases = reference_plan.get("deterministic_atlases")
    if not isinstance(selected, list) or not isinstance(atlases, list):
        return set()
    selected_ids = {item for item in selected if isinstance(item, str)}
    coverage = set(selected_ids)
    for atlas in atlases:
        if not isinstance(atlas, dict) or atlas.get("id") not in selected_ids:
            continue
        parents = atlas.get("parent_source_ids")
        if isinstance(parents, list):
            coverage.update(item for item in parents if isinstance(item, str))
    return coverage


def validate_evidence_constrained_generation(
    data: dict[str, Any], source_roles: dict[str, str]
) -> list[dict[str, str]]:
    """Gate generative product rendering by source views, identity, and material facts."""
    method = data.get("method")
    if not isinstance(method, dict) or method.get("type") != "evidence_constrained_generation":
        return []

    errors: list[dict[str, str]] = []
    if method.get("product_pixels_preserved") is not False:
        errors.append(error(
            "INVALID_GENERATIVE_PIXEL_PRESERVATION",
            "evidence_constrained_generation requires product_pixels_preserved to be literal false.",
        ))
    if method.get("material_fidelity_required") is not True:
        errors.append(error(
            "MATERIAL_FIDELITY_NOT_REQUIRED",
            "evidence_constrained_generation requires literal true material_fidelity_required.",
        ))
    if method.get("protected_regions"):
        errors.append(error(
            "INVALID_GENERATIVE_PROTECTED_PIXEL_CLAIM",
            "Generated product pixels cannot be declared protected source pixels.",
        ))

    anchors = method.get("view_anchor_source_ids")
    if not is_nonempty_string_list(anchors) or len(anchors) != len(set(anchors or [])):
        errors.append(error(
            "MISSING_VIEW_ANCHOR",
            "evidence_constrained_generation requires unique product view_anchor_source_ids.",
        ))
        anchors = []

    sources_by_id = {
        source["id"]: source
        for source in data.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    coverage = selected_reference_coverage(data.get("reference_plan"))
    anchor_surfaces: set[str] = set()
    anchor_views: set[str] = set()
    for anchor_id in anchors:
        source = sources_by_id.get(anchor_id)
        if source is None or source_roles.get(anchor_id) not in PRODUCT_EVIDENCE_ROLES:
            errors.append(error(
                "INVALID_VIEW_ANCHOR_SOURCE",
                f"View anchor {anchor_id} must name PRODUCT_TRUTH or DETAIL_TRUTH.",
            ))
            continue
        if anchor_id not in coverage:
            errors.append(error(
                "UNSELECTED_VIEW_ANCHOR",
                f"View anchor {anchor_id} is not carried by the selected reference plan.",
            ))
        view = source.get("view")
        if isinstance(view, str) and view in SOURCE_VIEW_SURFACES:
            anchor_views.add(view)
            anchor_surfaces.update(SOURCE_VIEW_SURFACES[view])

    scene = data.get("scene_plan")
    if isinstance(scene, dict):
        final_orientation = scene.get("final_orientation")
        final_surfaces = scene.get("final_visible_surfaces")
        if anchors and final_orientation not in anchor_views:
            errors.append(error(
                "UNSUPPORTED_GENERATED_ORIENTATION",
                "Final generated orientation requires an anchor photographed in that orientation.",
            ))
        if isinstance(final_surfaces, list):
            unsupported = set(final_surfaces) - anchor_surfaces
            if unsupported:
                errors.append(error(
                    "UNSUPPORTED_GENERATED_SURFACE",
                    "Generated visible surfaces lack view-anchor evidence: "
                    + ", ".join(sorted(unsupported)) + ".",
                ))

        visible_ids = string_ids(scene.get("visible_identity_critical_regions"))
        redrawn_ids = string_ids(scene.get("redrawn_identity_critical_regions"))
        if visible_ids - redrawn_ids:
            errors.append(error(
                "GENERATED_IDENTITY_NOT_MARKED_REDRAWN",
                "Every identity region in a generated product must be listed as redrawn.",
            ))

        material_ids = scene.get("material_identity_fact_ids")
        if not is_nonempty_string_list(material_ids) or len(material_ids) != len(set(material_ids or [])):
            errors.append(error(
                "MISSING_MATERIAL_FACT",
                "evidence_constrained_generation requires material_identity_fact_ids.",
            ))
            material_ids = []
        facts_by_id = {
            fact["id"]: fact
            for fact in data.get("facts", [])
            if isinstance(fact, dict) and isinstance(fact.get("id"), str)
        }
        for fact_id in material_ids:
            fact = facts_by_id.get(fact_id)
            component = fact.get("component") if isinstance(fact, dict) else None
            if (
                fact is None
                or not isinstance(component, str)
                or "material" not in component.lower()
                or fact.get("commercial_importance") != "high"
                or not resolved_support_record(fact, data)
                or fact_id not in redrawn_ids
            ):
                errors.append(error(
                    "INVALID_MATERIAL_FACT",
                    f"Material identity fact {fact_id} must be resolved, high-importance, product-backed, and redrawn.",
                ))
    return errors


def validate_delivery_ceiling(data: dict[str, Any]) -> list[dict[str, str]]:
    """Prevent a draft or full redraw from being represented as a verified composite."""
    method = data.get("method")
    method_type = method.get("type") if isinstance(method, dict) else None
    requested_status = data.get("delivery_status")
    if (
        method_type == "full_generative_redraw"
        and requested_status in {"verified_composite", "verified_reference_match"}
    ):
        return [
            error(
                "UNSAFE_COMMERCIAL_METHOD",
                "full_generative_redraw cannot be delivered as a verified product result.",
            )
        ]
    if (
        method_type == "evidence_constrained_generation"
        and requested_status == "verified_composite"
    ):
        return [error(
            "WRONG_VERIFIED_STATUS_FOR_METHOD",
            "evidence_constrained_generation may use verified_reference_match, not verified_composite.",
        )]
    if (
        method_type != "evidence_constrained_generation"
        and requested_status == "verified_reference_match"
    ):
        return [error(
            "WRONG_VERIFIED_STATUS_FOR_METHOD",
            "verified_reference_match requires evidence_constrained_generation.",
        )]
    if data.get("mode") == "concept_draft" and requested_status in {
        "verified_composite", "verified_reference_match"
    }:
        return [
            error(
                "UNVERIFIED_DRAFT_REQUIRED",
                "concept_draft cannot be delivered as verified_composite.",
            )
        ]
    return []


def required_landmark_ids(data: dict[str, Any]) -> set[str]:
    """Return visible/redrawn identity records that need an individual QA crop."""
    visible_or_redrawn = final_region_ids(data)
    return visible_or_redrawn | {
        record["id"]
        for record in data["facts"]
        if isinstance(record, dict)
        and isinstance(record.get("id"), str)
        and record["id"] in visible_or_redrawn
        and record.get("commercial_importance") == "high"
    } | {
        record["id"]
        for record in data["topology"]
        if isinstance(record, dict)
        and isinstance(record.get("id"), str)
        and record["id"] in visible_or_redrawn
    }


def protected_region_ids(method: Any) -> set[str]:
    """Return declared protected-region IDs after method shape validation."""
    if not isinstance(method, dict) or not isinstance(method.get("protected_regions"), list):
        return set()
    return {
        region["id"]
        for region in method["protected_regions"]
        if isinstance(region, dict)
        and isinstance(region.get("id"), str)
        and region["id"].strip()
    }


def explicit_qa_failure_errors(qa: Any) -> list[dict[str, str]]:
    """Preserve literal recorded QA failures even while delivery QA is incomplete."""
    if not isinstance(qa, dict):
        return []

    errors: list[dict[str, str]] = []
    landmark_records = qa.get("landmark_records")
    if isinstance(landmark_records, list):
        for index, record in enumerate(landmark_records):
            if not isinstance(record, dict):
                continue
            verdict = record.get("verdict")
            if isinstance(verdict, str) and verdict in {"fail", "mismatch"}:
                landmark_id = record.get("landmark_id")
                label = landmark_id if isinstance(landmark_id, str) else str(index)
                errors.append(
                    error(
                        "IDENTITY_LANDMARK_QA_FAILED",
                        f"Identity landmark {label} did not pass original-resolution QA.",
                    )
                )
    protected_pixels = qa.get("protected_pixels")
    if isinstance(protected_pixels, dict) and protected_pixels.get("verdict") == "drift":
        errors.append(
            error(
                "PROTECTED_PRODUCT_PIXEL_DRIFT",
                "Protected product-pixel comparison reports drift.",
            )
        )
    material_comparison = qa.get("material_comparison")
    if isinstance(material_comparison, dict) and material_comparison.get("verdict") == "fail":
        errors.append(error(
            "MATERIAL_QA_FAILED",
            "Material comparison reports a mismatch against product evidence.",
        ))
    return errors


def validate_delivery_qa(
    data: dict[str, Any], source_roles: dict[str, str]
) -> list[dict[str, str]]:
    """Require source-backed original-resolution QA before verified delivery."""
    qa = data.get("qa")
    explicit_failure_errors = explicit_qa_failure_errors(qa)
    verified_statuses = {"verified_composite", "verified_reference_match"}
    if data.get("delivery_status") not in verified_statuses:
        return explicit_failure_errors
    if not isinstance(qa, dict):
        return explicit_failure_errors + [error(
            "INVALID_QA", "Verified delivery requires qa to be an object."
        )]

    errors = explicit_failure_errors
    if qa.get("original_resolution_comparison") is not True:
        errors.append(
            error(
                "MISSING_ORIGINAL_RESOLUTION_COMPARISON",
                "Verified delivery requires literal true qa.original_resolution_comparison.",
            )
        )
    if qa.get("overall_verdict") != "pass":
        errors.append(
            error(
                "QA_OVERALL_VERDICT_NOT_PASS",
                "Verified delivery requires qa.overall_verdict to be pass.",
            )
        )

    landmark_records = qa.get("landmark_records")
    if not isinstance(landmark_records, list):
        errors.append(
            error(
                "INVALID_LANDMARK_QA",
                "qa.landmark_records must be an array of landmark QA records.",
            )
        )
        landmark_records = []

    required_ids = required_landmark_ids(data)
    seen_ids: set[str] = set()
    covered_ids: set[str] = set()
    for index, record in enumerate(landmark_records):
        if not isinstance(record, dict):
            errors.append(
                error(
                    "INVALID_LANDMARK_QA",
                    f"Landmark QA record {index} must be an object.",
                )
            )
            continue
        landmark_id = record.get("landmark_id")
        if not isinstance(landmark_id, str) or not landmark_id.strip():
            errors.append(
                error(
                    "INVALID_LANDMARK_QA",
                    f"Landmark QA record {index} requires a non-empty landmark_id.",
                )
            )
            continue
        if landmark_id in seen_ids:
            errors.append(
                error(
                    "DUPLICATE_LANDMARK_QA",
                    f"Landmark QA record {landmark_id} is duplicated.",
                )
            )
        else:
            seen_ids.add(landmark_id)
        verdict = record.get("verdict")
        verdict_is_valid = (
            isinstance(verdict, str) and verdict in LANDMARK_QA_VERDICTS
        )
        if not verdict_is_valid:
            errors.append(
                error(
                    "INVALID_LANDMARK_QA_VERDICT",
                    f"Landmark QA record {landmark_id} verdict must be pass, fail, or mismatch.",
                )
            )
        source_id = record.get("source_id")
        source_is_valid = (
            isinstance(source_id, str)
            and source_roles.get(source_id) in PRODUCT_EVIDENCE_ROLES
        )
        if not source_is_valid:
            errors.append(
                error(
                    "INVALID_LANDMARK_QA_SOURCE",
                    f"Landmark QA record {landmark_id} must cite a PRODUCT_TRUTH or DETAIL_TRUTH source.",
                )
            )
        region_is_valid = is_valid_normalized_region(record.get("normalized_region"))
        if not region_is_valid:
            errors.append(
                error(
                    "INVALID_LANDMARK_QA_REGION",
                    f"Landmark QA record {landmark_id} requires a finite normalized region.",
                )
            )
        if source_is_valid and region_is_valid and verdict_is_valid:
            covered_ids.add(landmark_id)

    missing_landmark_ids = required_ids - covered_ids
    if missing_landmark_ids:
        errors.append(
            error(
                "MISSING_LANDMARK_QA",
                "Missing well-formed landmark QA for: "
                + ", ".join(sorted(missing_landmark_ids))
                + ".",
            )
        )

    required_protected_region_ids = protected_region_ids(data.get("method"))
    if required_protected_region_ids:
        protected_pixels = qa.get("protected_pixels")
        if not isinstance(protected_pixels, dict):
            errors.append(
                error(
                    "MISSING_LANDMARK_QA",
                    "Protected product pixels require a protected_pixels QA comparison record.",
                )
            )
        else:
            compared_region_ids = protected_pixels.get("compared_region_ids")
            if not is_string_list(compared_region_ids):
                errors.append(
                    error(
                        "MISSING_LANDMARK_QA",
                        "protected_pixels.compared_region_ids must be an array of region IDs.",
                    )
                )
            elif not required_protected_region_ids.issubset(set(compared_region_ids)):
                errors.append(
                    error(
                        "MISSING_LANDMARK_QA",
                        "protected_pixels.compared_region_ids must cover every protected product region.",
                    )
                )
            verdict = protected_pixels.get("verdict")
            if (
                not isinstance(verdict, str)
                or verdict not in PROTECTED_PIXEL_QA_VERDICTS
            ):
                errors.append(
                    error(
                        "INVALID_PROTECTED_PIXEL_QA",
                        "protected_pixels.verdict must be pass or drift.",
                    )
                )
    if data.get("delivery_status") == "verified_reference_match":
        material_ids = string_ids(
            data.get("scene_plan", {}).get("material_identity_fact_ids")
            if isinstance(data.get("scene_plan"), dict)
            else None
        )
        material_comparison = qa.get("material_comparison")
        if not isinstance(material_comparison, dict):
            errors.append(error(
                "MISSING_MATERIAL_QA",
                "verified_reference_match requires qa.material_comparison.",
            ))
        else:
            if material_comparison.get("original_resolution") is not True:
                errors.append(error(
                    "MISSING_MATERIAL_QA",
                    "Material QA requires literal true original_resolution.",
                ))
            compared_fact_ids = material_comparison.get("fact_ids")
            if not is_nonempty_string_list(compared_fact_ids) or not material_ids.issubset(set(compared_fact_ids or [])):
                errors.append(error(
                    "MISSING_MATERIAL_QA",
                    "Material QA must cover every material_identity_fact_id.",
                ))
            verdict = material_comparison.get("verdict")
            if verdict == "fail" and not any(
                item["code"] == "MATERIAL_QA_FAILED" for item in errors
            ):
                errors.append(error(
                    "MATERIAL_QA_FAILED",
                    "Material comparison reports a mismatch against product evidence.",
                ))
            elif verdict not in {"pass", "fail"}:
                errors.append(error(
                    "MISSING_MATERIAL_QA",
                    "Material QA verdict must be pass or fail.",
                ))
    return errors


def validate_manifest(data: Any) -> list[dict[str, str]]:
    """Validate top-level shape plus fact, approval, and claim evidence gates."""
    if not isinstance(data, dict):
        return [error("INVALID_MANIFEST", "Manifest root must be a JSON object.")]

    errors = [
        error("MISSING_TOP_LEVEL_FIELD", f"Missing top-level field: {field}.")
        for field in REQUIRED_TOP_LEVEL_FIELDS
        if field not in data
    ]
    if "mode" in data and (
        not isinstance(data["mode"], str) or data["mode"] not in VALID_MODES
    ):
        errors.append(
            error(
                "INVALID_MODE",
                "Field mode must be commercial_exact_product or concept_draft.",
            )
        )
    if "delivery_status" in data and not isinstance(data["delivery_status"], str):
        errors.append(
            error("INVALID_FIELD_TYPE", "Field delivery_status must be a string.")
        )
    elif (
        "delivery_status" in data
        and data["delivery_status"] not in VALID_DELIVERY_STATUSES
    ):
        errors.append(
            error(
                "INVALID_DELIVERY_STATUS",
                "Field delivery_status must be blocked, unverified_draft, verified_composite, verified_reference_match, or rejected.",
            )
        )
    if errors:
        return errors

    errors.extend(validate_support_record_shapes(data))
    if errors:
        return errors
    errors.extend(validate_scene_plan_shape(data))
    if errors:
        return errors
    errors.extend(validate_support_id_uniqueness(data))
    if errors:
        return errors
    errors.extend(validate_identity_region_references(data))
    if errors:
        return errors
    errors.extend(validate_source_shapes(data))
    if errors:
        return errors

    sources = data.get("sources")
    source_ids = (
        {
            source["id"]
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("id"), str)
        }
        if isinstance(sources, list)
        else set()
    )
    required_source_ids = (
        {
            source["id"]
            for source in sources
            if isinstance(source, dict)
            and isinstance(source.get("id"), str)
            and source.get("required") is True
        }
        if isinstance(sources, list)
        else set()
    )
    source_roles = {
        source["id"]: source["role"]
        for source in sources
        if isinstance(source, dict)
        and isinstance(source.get("id"), str)
        and isinstance(source.get("role"), str)
    }
    product_evidence_source_ids = {
        source_id
        for source_id, source_role in source_roles.items()
        if source_role in PRODUCT_EVIDENCE_ROLES
    }
    errors.extend(
        validate_reference_plan(
            data.get("reference_plan"),
            source_ids,
            required_source_ids,
            source_roles,
        )
    )
    if errors:
        return errors
    errors.extend(validate_verified_identity_declaration(data))
    errors.extend(validate_presentation_envelope(data, source_roles))
    errors.extend(validate_visible_attachment_points(data))
    errors.extend(validate_method(data.get("method"), source_ids, source_roles))
    errors.extend(validate_evidence_constrained_generation(data, source_roles))
    errors.extend(validate_delivery_ceiling(data))
    errors.extend(validate_delivery_qa(data, source_roles))

    approval = data.get("approval")
    confirmed_fact_ids = string_ids(
        approval.get("confirmed_fact_ids") if isinstance(approval, dict) else None
    )
    visible_or_redrawn_ids = final_region_ids(data)

    fact_items = data["facts"]
    topology_items = data["topology"]

    fact_resolution: dict[str, bool] = {}
    topology_resolution: dict[str, bool] = {}

    for fact in fact_items:
        fact_id = fact.get("id")
        if not isinstance(fact_id, str):
            continue

        status = fact.get("status")
        has_invalid_evidence_role = has_disallowed_product_evidence(
            fact, source_ids, product_evidence_source_ids
        )
        fact_evidence_error = (
            "INVALID_PRODUCT_EVIDENCE_SOURCE_ROLE"
            if has_invalid_evidence_role
            else evidence_error_code(fact, product_evidence_source_ids)
        )
        evidence_backed = fact_evidence_error is None
        is_confirmed = status == "user_confirmed" and fact_id in confirmed_fact_ids
        is_observed = status == "observed"
        is_resolved = (is_observed or is_confirmed) and evidence_backed
        fact_resolution[fact_id] = is_resolved

        if status == "user_confirmed" and fact_id not in confirmed_fact_ids:
            errors.append(
                error(
                    "UNCONFIRMED_USER_FACT",
                    f"User-confirmed fact {fact_id} is absent from approval.confirmed_fact_ids.",
                )
            )
        if has_invalid_evidence_role:
            errors.append(
                error(
                    "INVALID_PRODUCT_EVIDENCE_SOURCE_ROLE",
                    f"Fact {fact_id} cites a source that cannot prove product truth.",
                )
            )
        elif (is_observed or is_confirmed) and not evidence_backed:
            errors.append(
                error(
                    fact_evidence_error,
                    f"Fact {fact_id} requires an evidence region linked to an existing source.",
                )
            )
        if (
            fact.get("commercial_importance") == "high"
            and fact_id in visible_or_redrawn_ids
            and status in ("unknown", "conflict")
        ):
            errors.append(
                error(
                    "UNRESOLVED_HIGH_RISK_FACT",
                    f"Visible or redrawn high-importance fact {fact_id} has unresolved status {status}.",
                )
            )

    for component in topology_items:
        component_id = component.get("id")
        if not isinstance(component_id, str):
            continue
        has_invalid_evidence_role = has_disallowed_product_evidence(
            component, source_ids, product_evidence_source_ids
        )
        topology_evidence_error = (
            "INVALID_PRODUCT_EVIDENCE_SOURCE_ROLE"
            if has_invalid_evidence_role
            else evidence_error_code(component, product_evidence_source_ids)
        )
        evidence_backed = topology_evidence_error is None
        status = component.get("status")
        is_confirmed = (
            status == "user_confirmed" and component_id in confirmed_fact_ids
        )
        topology_resolution[component_id] = (
            (status == "observed" or is_confirmed) and evidence_backed
        )
        if component_id in visible_or_redrawn_ids and not topology_resolution[component_id]:
            errors.append(error(
                "UNRESOLVED_HIGH_RISK_TOPOLOGY",
                f"Visible or redrawn topology {component_id} requires resolved product evidence and explicit approval when user-confirmed.",
            ))
        if status == "user_confirmed" and component_id not in confirmed_fact_ids:
            errors.append(
                error(
                    "UNCONFIRMED_USER_FACT",
                    f"User-confirmed topology {component_id} is absent from approval.confirmed_fact_ids.",
                )
            )
        if has_invalid_evidence_role:
            errors.append(
                error(
                    "INVALID_PRODUCT_EVIDENCE_SOURCE_ROLE",
                    f"Topology {component_id} cites a source that cannot prove product truth.",
                )
            )
        elif (status == "observed" or is_confirmed) and not evidence_backed:
            errors.append(
                error(
                    topology_evidence_error,
                    f"Topology {component_id} requires an evidence region linked to an existing source.",
                )
            )

    for claim in data["prompt_claims"] + data.get("forbidden_mutations", []):
        claim_id = claim["id"]
        support_ids = claim.get("supporting_ids")
        supported = isinstance(support_ids, list) and bool(support_ids)
        if supported:
            for support_id in support_ids:
                if not isinstance(support_id, str):
                    supported = False
                    break
                if support_id in fact_resolution:
                    if not fact_resolution[support_id]:
                        supported = False
                        break
                elif support_id in topology_resolution:
                    if not topology_resolution[support_id]:
                        supported = False
                        break
                else:
                    supported = False
                    break
        if not supported:
            errors.append(
                error(
                    "UNSUPPORTED_PROMPT_CLAIM",
                    f"Prompt claim {claim_id} lacks resolved, source-backed fact or topology support.",
                )
            )
    return errors


def effective_delivery_status(data: Any, errors: list[dict[str, str]]) -> str:
    """Return the safe ceiling when a rejected verified delivery is only a draft."""
    if errors:
        if any(
            item["code"] in {
                "IDENTITY_LANDMARK_QA_FAILED",
                "MATERIAL_QA_FAILED",
                "PROTECTED_PRODUCT_PIXEL_DRIFT",
            }
            for item in errors
        ):
            return "rejected"
        if len(errors) == 1 and errors[0]["code"] in {
            "UNSAFE_COMMERCIAL_METHOD",
            "UNVERIFIED_DRAFT_REQUIRED",
        }:
            return "unverified_draft"
        return "blocked"
    return data["delivery_status"]


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True))


def validate_prompt_contract_content(data: dict[str, Any]) -> list[dict[str, str]]:
    """Export requires bounded typed content, including for concept drafts."""
    errors: list[dict[str, str]] = []
    if data["mode"] == "concept_draft":
        commercial_view = dict(data, mode="commercial_exact_product")
        roles = {source["id"]: source["role"] for source in data["sources"]}
        errors.extend(validate_presentation_envelope(commercial_view, roles))
        errors.extend(validate_visible_attachment_points(commercial_view))
    for section, fields in (
        ("facts", ("component", "assertion")),
        ("topology", ("component", "path", "connection_type", "purpose")),
    ):
        for record in data[section]:
            if not resolved_support_record(record, data):
                continue
            for field in fields:
                if field in record and (
                    not isinstance(record[field], str) or not record[field].strip()
                ):
                    errors.append(error("INVALID_PROMPT_CONTRACT_CONTENT", f"{record['id']}.{field} must be nonempty text."))
            required_text = "assertion" if section == "facts" else "path"
            if required_text not in record:
                errors.append(error("INVALID_PROMPT_CONTRACT_CONTENT", f"{record['id']} requires {required_text} for export."))
            if "endpoints" in record and not is_string_list(record["endpoints"]):
                errors.append(error("INVALID_PROMPT_CONTRACT_CONTENT", f"{record['id']}.endpoints must be a string array."))
            if "component_count" in record and (
                not isinstance(record["component_count"], int)
                or isinstance(record["component_count"], bool)
                or record["component_count"] < 0
            ):
                errors.append(error("INVALID_PROMPT_CONTRACT_CONTENT", f"{record['id']}.component_count must be a nonnegative integer."))
    for claim in data["prompt_claims"] + data.get("forbidden_mutations", []):
        if not isinstance(claim.get("claim"), str) or not claim["claim"].strip():
            errors.append(error("INVALID_PROMPT_CONTRACT_CONTENT", f"Claim {claim['id']} requires nonempty text."))
    if "allowed_edit_mask" in data["method"]:
        errors.extend(validate_allowed_contact_edit_mask(data["method"]["allowed_edit_mask"]))
    method = data["method"]
    if "product_pixels_preserved" in method and not isinstance(method["product_pixels_preserved"], bool):
        errors.append(error("INVALID_PROMPT_CONTRACT_CONTENT", "product_pixels_preserved must be boolean for export."))
    if method["type"] == "full_generative_redraw" and method.get("protected_regions"):
        roles = {source["id"]: source["role"] for source in data["sources"]}
        errors.extend(validate_protected_product_regions(method["protected_regions"], set(roles), roles))
    return errors


def prompt_contract(data: dict[str, Any]) -> dict[str, Any]:
    """Project validated fields only; unknown records and extra prose never export."""
    def select(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        return {field: record[field] for field in fields if field in record}

    product_ids = {source["id"] for source in data["sources"] if source["role"] in PRODUCT_EVIDENCE_ROLES}
    contract: dict[str, Any] = {
        "mode": data["mode"],
        "delivery_status": data["delivery_status"],
        "source_roles": [select(source, ("id", "role")) for source in data["sources"]],
    }
    for section, fields in (
        ("facts", ("id", "component", "assertion", "status", "commercial_importance")),
        ("topology", ("id", "component", "component_count", "endpoints", "path", "connection_type", "purpose", "status")),
    ):
        contract[section] = []
        for record in data[section]:
            if resolved_support_record(record, data):
                exported = select(record, fields)
                exported["evidence"] = [
                    select(item, ("source_id", "normalized_region"))
                    for item in record["evidence"]
                    if is_valid_evidence_region(item, product_ids)
                ]
                contract[section].append(exported)
    for section in ("prompt_claims", "forbidden_mutations"):
        contract[section] = [select(claim, ("id", "claim", "supporting_ids")) for claim in data.get(section, [])]
    scene = data["scene_plan"]
    contract["presentation_envelope"] = select(scene["presentation_envelope"], (
        "supported_orientations", "visible_surfaces", "surface_evidence",
        "visible_attachment_points", "must_remain_hidden",
    ))
    contract.update(select(scene, (
        "final_orientation", "final_visible_surfaces", "mirrored_product_view",
        "permitted_scene_adjustments", "applied_scene_adjustments", "forbidden_invented_regions",
    )))
    contract["material_identity_fact_ids"] = list(
        scene.get("material_identity_fact_ids", [])
    ) if is_string_list(scene.get("material_identity_fact_ids", [])) else []
    method = data["method"]
    contract["method"] = select(method, (
        "type", "product_pixels_preserved", "view_anchor_source_ids",
        "material_fidelity_required",
    ))
    contract["method"]["protected_regions"] = [
        select(region, ("id", "source_id", "normalized_region"))
        for region in method.get("protected_regions", [])
        if isinstance(region, dict) and is_valid_evidence_region(region, product_ids)
    ] if isinstance(method.get("protected_regions", []), list) else []
    contract["method"]["allowed_edit_mask"] = select(method.get("allowed_edit_mask", {}), ("regions",))
    return contract


def main(argv: Optional[list[str]] = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    emit_contract = len(arguments) == 2 and arguments[0] == "--emit-prompt-contract"
    if not emit_contract and (len(arguments) != 1 or arguments[0].startswith("--")):
        emit(
            {
                "valid": False,
                "effective_delivery_status": "blocked",
                "errors": [error("USAGE", "Usage: validate_fidelity_manifest.py [--emit-prompt-contract] MANIFEST.json")],
            }
        )
        return 2

    manifest_path = arguments[-1]
    try:
        data = load_manifest(Path(manifest_path))
    except FileNotFoundError:
        errors = [error("MANIFEST_NOT_FOUND", f"Manifest not found: {manifest_path}.")]
        emit({"valid": False, "effective_delivery_status": "blocked", "errors": errors})
        return 1
    except OSError as exc:
        errors = [error("MANIFEST_READ_ERROR", str(exc))]
        emit({"valid": False, "effective_delivery_status": "blocked", "errors": errors})
        return 1
    except UnicodeError as exc:
        errors = [error("INVALID_ENCODING", str(exc))]
        emit({"valid": False, "effective_delivery_status": "blocked", "errors": errors})
        return 1
    except json.JSONDecodeError as exc:
        errors = [error("INVALID_JSON", str(exc))]
        emit({"valid": False, "effective_delivery_status": "blocked", "errors": errors})
        return 1
    except DuplicateJSONKeyError as exc:
        errors = [error("DUPLICATE_JSON_KEY", str(exc))]
        emit({"valid": False, "effective_delivery_status": "blocked", "errors": errors})
        return 1
    except RecursionError:
        errors = [error("JSON_NESTING_TOO_DEEP", "Manifest JSON exceeds the parser nesting limit.")]
        emit({"valid": False, "effective_delivery_status": "blocked", "errors": errors})
        return 1

    errors = validate_manifest(data)
    if emit_contract and not errors:
        errors.extend(validate_prompt_contract_content(data))
    payload = {
        "valid": not errors,
        "effective_delivery_status": effective_delivery_status(data, errors),
        "errors": errors,
    }
    if emit_contract and not errors:
        payload["prompt_contract"] = prompt_contract(data)
    emit(payload)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

from dataclasses import replace
import base64
import io
import json
from pathlib import Path

import pytest

from workflow import runner
from workflow import gateway
from workflow.models import ProductIdentity, TemplateRecord
from workflow.projects import write_product_identity, write_web_handoff
from workflow.prompt_builder import build_direct_image_prompt
from workflow.templates import write_template_record


def _identity() -> ProductIdentity:
    return ProductIdentity(
        truth_sources=("original.png",),
        surface_graphics=("No printing",),
        physical_constraints=("The frame rests on the floor",),
        human_interaction_constraints=("No people",),
        components=("One folding frame",),
        relationships=("Legs attach at the hinge",),
        visible_connection_evidence=("Leg, hinge pin, leg",),
        functional_features=("One hinge at the upper leg",),
        required_use_states=("Standing open",),
        assembly_state_evidence=("The connected legs support the seat",),
        visible_component_instances=("hero-frame: feet to legs to hinge; floor support",),
        forbidden_inventions=("No extra hinge",),
        approved=True,
    )


def _template() -> TemplateRecord:
    return TemplateRecord(
        "neutral-01", "amazon", "detail", "1:1", "1000x1000",
        "center", "none", "studio", "neutral", [], [], ["template.png"],
    )


def _data() -> dict:
    constraints = {
        "rigidity": "rigid-straight-leg",
        "joints": "upper-hinge-only",
        "endpoints": "foot-on-floor-to-upper-hinge",
        "direction": "straight-upward-to-hinge",
        "support": "feet-contact-floor",
    }
    return {
        "version": 1,
        "checks": [{
            "instance_id": "hero-frame",
            "dimensions": {
                name: {
                    "allowed": [constraint],
                    "required": [constraint],
                    "verdict": "pass",
                    "sources": ["original.png"],
                    "evidence": f"Original photo shows {constraint}; proposed open pose preserves it.",
                    "conflicts": [],
                }
                for name, constraint in constraints.items()
            },
        }],
    }


def _prepare(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    assert runner.main([
        "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "detail",
        "--ratio", "1:1", "--product-reference", "original.png", "--request", "Show open frame",
    ]) == 0
    task = tmp_path / "projects/demo/images/01-detail"
    write_product_identity(task, _identity())
    return task


def _record(tmp_path: Path, data: dict) -> int:
    path = tmp_path / "checks.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        return runner.main([
            "record-geometry-preflight", "--project", "demo", "--image", "1",
            "--objective", "Show open frame", "--checks-file", str(path),
        ])
    except SystemExit as error:
        pytest.fail(f"Geometry preflight command is not available: {error}")


def _handoff() -> int:
    return runner.main([
        "write-web-handoff", "--project", "demo", "--image", "1", "--objective", "Show open frame",
    ])


def test_direct_prompt_blocks_absent_geometry_preflight() -> None:
    with pytest.raises(ValueError, match="几何预检"):
        build_direct_image_prompt(_template(), ["original.png"], "Show open frame", product_identity=_identity())


def test_handoff_api_blocks_absent_geometry_preflight(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="几何预检"):
        write_web_handoff(tmp_path, "cached prompt", _template(), ["original.png"], product_identity=_identity())
    assert not (tmp_path / "web-chatgpt-prompt.md").exists()


def test_codex_blocks_absent_preflight_before_gateway_configuration(tmp_path: Path, monkeypatch, capsys) -> None:
    task = _prepare(tmp_path, monkeypatch)
    (task / "direct-image-prompt.md").write_text("old prompt", encoding="utf-8")
    assert runner.main(["generate-codex", "--project", "demo", "--image", "1", "--route", "codex"]) == 1
    assert "几何预检" in capsys.readouterr().out
    assert not (task / "generated-image.png").exists()


def test_safe_geometry_records_and_unblocks_prompt(tmp_path: Path, monkeypatch) -> None:
    task = _prepare(tmp_path, monkeypatch)
    assert _record(tmp_path, _data()) == 0
    report = json.loads((task / "geometry-preflight.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["objective"] == "Show open frame"
    assert report["checks"] == _data()["checks"]
    assert _handoff() == 0
    prompt = (task / "direct-image-prompt.md").read_text(encoding="utf-8")
    assert "生图前几何可行性预检" in prompt
    assert "rigid-straight-leg" in prompt
    assert "upper-hinge-only" in prompt
    assert "原始产品图" in prompt


@pytest.mark.parametrize("dimension", ["rigidity", "joints", "endpoints", "direction", "support"])
@pytest.mark.parametrize("problem", ["fail", "unknown", "conflict", "incompatible"])
def test_unsafe_geometry_is_preserved_and_blocks_generation(
    tmp_path: Path, monkeypatch, capsys, dimension: str, problem: str
) -> None:
    task = _prepare(tmp_path, monkeypatch)
    data = _data()
    check = data["checks"][0]["dimensions"][dimension]
    if problem in {"fail", "unknown"}:
        check["verdict"] = problem
    elif problem == "conflict":
        check["conflicts"] = ["The requested arrangement contradicts the source constraint"]
    else:
        check["required"] = ["unsupported-geometry"]
    assert _record(tmp_path, data) == 0
    report = json.loads((task / "geometry-preflight.json").read_text(encoding="utf-8"))
    assert report["status"] == "blocked"
    assert report["checks"] == data["checks"]
    assert _handoff() == 1
    assert not (task / "direct-image-prompt.md").exists()
    assert runner.main(["generate-codex", "--project", "demo", "--image", "1", "--route", "codex"]) == 1
    assert "几何预检" in capsys.readouterr().out


@pytest.mark.parametrize("problem", [
    "missing-dimension", "missing-evidence", "missing-sources", "missing-allowed", "missing-required",
    "missing-conflicts", "duplicate-instance", "extra-instance", "missing-instance", "generated-source",
    "unlisted-source", "bad-version", "invalid-verdict", "string-conflicts", "blank-token",
])
def test_malformed_preflight_fails_closed(tmp_path: Path, monkeypatch, problem: str) -> None:
    task = _prepare(tmp_path, monkeypatch)
    data = _data()
    dimensions = data["checks"][0]["dimensions"]
    if problem == "missing-dimension":
        del dimensions["direction"]
    elif problem.startswith("missing-") and problem != "missing-instance":
        del dimensions["rigidity"][problem.removeprefix("missing-")]
    elif problem == "duplicate-instance":
        data["checks"].append(data["checks"][0])
    elif problem == "extra-instance":
        data["checks"][0]["instance_id"] = "other-frame"
    elif problem == "missing-instance":
        data["checks"] = []
    elif problem in {"generated-source", "unlisted-source"}:
        dimensions["rigidity"]["sources"] = ["generated-image-v1.png" if problem == "generated-source" else "template.png"]
    elif problem == "bad-version":
        data["version"] = 0
    elif problem == "invalid-verdict":
        dimensions["rigidity"]["verdict"] = "assumed"
    elif problem == "string-conflicts":
        dimensions["rigidity"]["conflicts"] = "none"
    elif problem == "blank-token":
        dimensions["rigidity"]["allowed"] = [" "]
    assert _record(tmp_path, data) == 1
    assert json.loads((task / "geometry-preflight.json").read_text(encoding="utf-8"))["status"] == "rejected"
    assert _handoff() == 1


def test_changed_identity_invalidates_preflight(tmp_path: Path, monkeypatch, capsys) -> None:
    task = _prepare(tmp_path, monkeypatch)
    assert _record(tmp_path, _data()) == 0
    write_product_identity(task, replace(_identity(), required_use_states=("Folded closed",)))
    assert _handoff() == 1
    assert "过期" in capsys.readouterr().out


def test_changed_objective_requires_new_preflight(tmp_path: Path, monkeypatch, capsys) -> None:
    _prepare(tmp_path, monkeypatch)
    assert _record(tmp_path, _data()) == 0
    assert runner.main([
        "write-web-handoff", "--project", "demo", "--image", "1", "--objective", "Fold the frame",
    ]) == 1
    assert "目标" in capsys.readouterr().out


def test_codex_rejects_edited_cached_prompt_before_gateway(tmp_path: Path, monkeypatch, capsys) -> None:
    task = _prepare(tmp_path, monkeypatch)
    assert _record(tmp_path, _data()) == 0
    assert _handoff() == 0
    (task / "direct-image-prompt.md").write_text("Bend a rigid leg around a corner", encoding="utf-8")
    assert runner.main(["generate-codex", "--project", "demo", "--image", "1", "--route", "codex"]) == 1
    assert "提示词" in capsys.readouterr().out


def test_duplicate_json_fields_cannot_hide_failed_input(tmp_path: Path, monkeypatch) -> None:
    task = _prepare(tmp_path, monkeypatch)
    content = json.dumps(_data()).replace('"verdict": "pass"', '"verdict": "fail", "verdict": "pass"', 1)
    path = tmp_path / "checks.json"
    path.write_text(content, encoding="utf-8")
    assert runner.main([
        "record-geometry-preflight", "--project", "demo", "--image", "1",
        "--objective", "Show open frame", "--checks-file", str(path),
    ]) == 1
    assert json.loads((task / "geometry-preflight.json").read_text(encoding="utf-8"))["status"] == "rejected"


@pytest.mark.parametrize("problem", ["incomplete", "invalid-json"])
def test_rejected_replacement_invalidates_previous_pass_and_preserves_attempt(
    tmp_path: Path, monkeypatch, problem: str,
) -> None:
    task = _prepare(tmp_path, monkeypatch)
    assert _record(tmp_path, _data()) == 0
    data = _data()
    dimension = data["checks"][0]["dimensions"]["direction"]
    dimension["verdict"] = "fail"
    dimension["conflicts"] = ["The rigid leg would have to bend through another solid"]
    del data["checks"][0]["dimensions"]["support"]["sources"]
    path = tmp_path / "checks.json"
    content = json.dumps(data) if problem == "incomplete" else '{"verdict":"fail",'
    path.write_text(content, encoding="utf-8")
    assert runner.main([
        "record-geometry-preflight", "--project", "demo", "--image", "1",
        "--objective", "Show open frame", "--checks-file", str(path),
    ]) == 1
    assert _handoff() == 1
    report = json.loads((task / "geometry-preflight.json").read_text(encoding="utf-8"))
    assert report["status"] == "rejected"
    assert "fail" in json.dumps(report["attempted_input"])
    assert _record(tmp_path, _data()) == 0
    assert _handoff() == 0


@pytest.mark.parametrize("tamper", ["duplicate-verdict", "fake-status", "invalid-json", "missing-version"])
def test_persisted_report_is_revalidated_before_use(tmp_path: Path, monkeypatch, tamper: str) -> None:
    task = _prepare(tmp_path, monkeypatch)
    assert _record(tmp_path, _data()) == 0
    path = task / "geometry-preflight.json"
    content = path.read_text(encoding="utf-8")
    if tamper == "duplicate-verdict":
        content = content.replace('"verdict": "pass"', '"verdict": "fail", "verdict": "pass"', 1)
    elif tamper == "fake-status":
        content = content.replace('"verdict": "pass"', '"verdict": "fail"', 1)
    elif tamper == "invalid-json":
        content = "{"
    else:
        content = content.replace('"version": 1,', "")
    path.write_text(content, encoding="utf-8")
    assert _handoff() == 1
    assert not (task / "direct-image-prompt.md").exists()


@pytest.mark.parametrize("first_attempt", ["none", "missing-preflight", "stale-prompt"])
def test_safe_geometry_reaches_real_gateway_transport_once(tmp_path: Path, monkeypatch, first_attempt: str) -> None:
    task = _prepare(tmp_path, monkeypatch)
    if first_attempt == "missing-preflight":
        assert runner.main(["generate-codex", "--project", "demo", "--image", "1", "--route", "codex"]) == 1
    assert _record(tmp_path, _data()) == 0
    assert _handoff() == 0
    if first_attempt == "stale-prompt":
        (task / "direct-image-prompt.md").write_text("Bend the rigid leg", encoding="utf-8")
        assert runner.main(["generate-codex", "--project", "demo", "--image", "1", "--route", "codex"]) == 1
        assert _handoff() == 0
    product_dir = tmp_path / "projects/demo/product-references"
    product_dir.mkdir()
    (product_dir / "original.png").write_bytes(b"original-product-photo")
    (tmp_path / "template-library/amazon/neutral-01/template.png").write_bytes(b"template-photo")
    (tmp_path / "image-env.yaml").write_text(
        "base_url: https://gateway.example/v1\napi_key: test-key\nmodel: image-model\n", encoding="utf-8",
    )
    requests = []

    def image_response(request, timeout):
        requests.append(request)
        return io.BytesIO(json.dumps({"data": [{"b64_json": base64.b64encode(b"generated-candidate").decode()}]}).encode())

    monkeypatch.setattr(gateway, "urlopen", image_response)
    assert runner.main(["generate-codex", "--project", "demo", "--image", "1", "--route", "codex"]) == 0
    assert (task / "generated-image.png").read_bytes() == b"generated-candidate"
    assert "pending_user_review" in (task / "brief.md").read_text(encoding="utf-8")
    assert len(requests) == 1
    assert "生图前几何可行性预检".encode() in requests[0].data
    assert b"original-product-photo" in requests[0].data

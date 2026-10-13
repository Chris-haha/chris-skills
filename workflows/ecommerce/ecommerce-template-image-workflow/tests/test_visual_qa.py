from pathlib import Path

import pytest

from workflow import runner
from workflow.models import ProductIdentity
from workflow.projects import write_product_identity
from workflow.visual_qa import (
    QA_DIMENSIONS,
    VisualQAError,
    load_visual_qa,
    parse_visual_qa_checks,
    validate_visual_qa,
    write_visual_qa,
)


REQUIRED = {"hero-primary-part": "端点A到端点B必须连续"}


def test_visual_qa_contract_requires_generic_framing_check() -> None:
    assert QA_DIMENSIONS == (
        "topology",
        "support",
        "clearance",
        "assembly",
        "framing",
    )


def _files(task_dir: Path) -> None:
    (task_dir / "qa").mkdir(parents=True)
    (task_dir / "generated-image-v1.png").write_bytes(b"candidate")
    (task_dir / "qa" / "hero-detail.png").write_bytes(b"detail")
    (task_dir / "qa" / "hero-context.png").write_bytes(b"context")


def _passing_check() -> str:
    return (
        "hero-primary-part|qa/hero-detail.png|qa/hero-context.png|"
        "topology=pass:端点A经连续主体和连接件到端点B|"
        "support=pass:主体由桌面形成连续承重接触|"
        "clearance=pass:整条路径与周围实体保持可见净空|"
        "assembly=pass:局部可还原为完整且互不冲突的装配状态|"
        "framing=pass:画框由真实画面填满且主体未被裁断"
    )


def test_visual_qa_round_trips_and_validates(tmp_path: Path) -> None:
    _files(tmp_path)
    checks = parse_visual_qa_checks([_passing_check()])

    path = write_visual_qa(tmp_path, "generated-image-v1.png", checks, REQUIRED)
    report = load_visual_qa(path)

    validate_visual_qa(
        tmp_path, report, REQUIRED, "generated-image-v1.png", require_pass=True
    )
    assert report.version == 3
    assert [dimension.name for dimension in report.checks[0].dimensions] == [
        "topology",
        "support",
        "clearance",
        "assembly",
        "framing",
    ]
    assert report.checks[0].result == "pass"
    assert report.status == "passed"


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ([], "缺少实例检查"),
        ([_passing_check().replace("|assembly=pass:", "", 1)], "维度集合"),
        ([_passing_check().replace("assembly=pass:", "topology=pass:", 1)], "维度重复"),
        ([_passing_check().replace("assembly=pass:", "unknown=pass:", 1)], "维度无效"),
        ([_passing_check().replace("topology=pass:", "topology=maybe:", 1)], "结果无效"),
        ([_passing_check().replace("assembly=pass:局部可还原为完整且互不冲突的装配状态", "assembly=pass:", 1)], "追踪证据不能为空"),
        (["bad-format"], "格式无效"),
        (
            [
                _passing_check(),
                _passing_check().replace("hero-primary-part", "hero-primary-part", 1),
            ],
            "ID 重复",
        ),
    ],
)
def test_parse_visual_qa_checks_rejects_invalid_contracts(
    values: list[str], message: str
) -> None:
    with pytest.raises(VisualQAError, match=message):
        parse_visual_qa_checks(values)


def test_parse_visual_qa_checks_rejects_extra_dimension_field() -> None:
    value = (
        "hero-primary-part|qa/hero-detail.png|qa/hero-context.png|"
        "topology=pass:t|support=pass:t|clearance=pass:t|"
        "assembly=pass:t|framing=pass:t|unknown=fail:extra"
    )

    with pytest.raises(VisualQAError, match="格式无效"):
        parse_visual_qa_checks([value])


def test_visual_qa_rejects_missing_required_instance(tmp_path: Path) -> None:
    _files(tmp_path)
    checks = parse_visual_qa_checks([_passing_check().replace("hero-primary-part", "other-instance", 1)])
    with pytest.raises(VisualQAError, match="实例集合不匹配"):
        write_visual_qa(tmp_path, "generated-image-v1.png", checks, REQUIRED)


@pytest.mark.parametrize("bad_context", ["qa/missing.png", "qa/empty.png"])
def test_visual_qa_rejects_missing_or_empty_context(tmp_path: Path, bad_context: str) -> None:
    _files(tmp_path)
    if bad_context.endswith("empty.png"):
        (tmp_path / bad_context).touch()
    checks = parse_visual_qa_checks([_passing_check().replace("qa/hero-context.png", bad_context, 1)])
    with pytest.raises(VisualQAError, match="上下文图"):
        write_visual_qa(tmp_path, "generated-image-v1.png", checks, REQUIRED)


def test_visual_qa_rejects_identical_detail_and_context_paths(tmp_path: Path) -> None:
    _files(tmp_path)
    checks = parse_visual_qa_checks([_passing_check().replace("qa/hero-context.png", "qa/hero-detail.png", 1)])
    with pytest.raises(VisualQAError, match="不同文件"):
        write_visual_qa(tmp_path, "generated-image-v1.png", checks, REQUIRED)


@pytest.mark.parametrize("escaped_path", ["../outside.png", "qa/../../outside.png"])
def test_visual_qa_rejects_evidence_path_escape(tmp_path: Path, escaped_path: str) -> None:
    _files(tmp_path)
    outside = tmp_path.parent / "outside.png"
    outside.write_bytes(b"outside")
    checks = parse_visual_qa_checks([_passing_check().replace("qa/hero-detail.png", escaped_path, 1)])
    with pytest.raises(VisualQAError, match="任务目录"):
        write_visual_qa(tmp_path, "generated-image-v1.png", checks, REQUIRED)


def test_visual_qa_rejects_candidate_mismatch(tmp_path: Path) -> None:
    _files(tmp_path)
    checks = parse_visual_qa_checks([_passing_check()])
    report = load_visual_qa(
        write_visual_qa(tmp_path, "generated-image-v1.png", checks, REQUIRED)
    )
    with pytest.raises(VisualQAError, match="候选图不匹配"):
        validate_visual_qa(
            tmp_path, report, REQUIRED, "another.png", require_pass=True
        )


def test_visual_qa_rejects_failed_report_when_pass_required(tmp_path: Path) -> None:
    _files(tmp_path)
    checks = parse_visual_qa_checks(
        [_passing_check().replace("clearance=pass:整条路径与周围实体保持可见净空", "clearance=fail:路径穿过固定主体", 1)]
    )
    report = load_visual_qa(
        write_visual_qa(tmp_path, "generated-image-v1.png", checks, REQUIRED)
    )
    assert report.checks[0].result == "fail"
    assert report.status == "failed"
    with pytest.raises(VisualQAError, match="未通过"):
        validate_visual_qa(
            tmp_path, report, REQUIRED, "generated-image-v1.png", require_pass=True
        )


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("- 实例结果: fail", "实例结果"),
        ("- 状态: failed", "汇总状态"),
    ],
)
def test_load_visual_qa_rejects_tampered_derived_results(
    tmp_path: Path, replacement: str, message: str
) -> None:
    _files(tmp_path)
    path = write_visual_qa(
        tmp_path, "generated-image-v1.png", parse_visual_qa_checks([_passing_check()]), REQUIRED
    )
    text = path.read_text(encoding="utf-8")
    target = "- 实例结果: pass" if "实例结果" in replacement else "- 状态: passed"
    path.write_text(text.replace(target, replacement, 1), encoding="utf-8")

    with pytest.raises(VisualQAError, match=message):
        load_visual_qa(path)


def test_load_visual_qa_rejects_legacy_markdown_without_version(tmp_path: Path) -> None:
    report_path = tmp_path / "visual-qa.md"
    report_path.write_text(
        "# 可见部件实例质检\n\n- 候选图: generated-image-v1.png\n- 状态: passed\n",
        encoding="utf-8",
    )

    with pytest.raises(VisualQAError, match="版本"):
        load_visual_qa(report_path)


@pytest.mark.parametrize(
    ("target", "replacement"),
    [
        ("- 版本: 3", "- 版本: 3\n- 版本: 3"),
        (
            "- 候选图: generated-image-v1.png",
            "- 候选图: generated-image-v1.png\n- 候选图: other.png",
        ),
        ("- 状态: passed", "- 状态: passed\n- 状态: failed"),
    ],
)
def test_load_visual_qa_rejects_duplicate_report_headers(
    tmp_path: Path, target: str, replacement: str
) -> None:
    _files(tmp_path)
    path = write_visual_qa(
        tmp_path, "generated-image-v1.png", parse_visual_qa_checks([_passing_check()]), REQUIRED
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace(target, replacement, 1),
        encoding="utf-8",
    )

    with pytest.raises(VisualQAError, match="格式无效"):
        load_visual_qa(path)


@pytest.mark.parametrize(
    "extra_field",
    [
        "- unknown: pass",
        "- clearance: fail:solid collision",
        "- malformed instance field",
    ],
)
def test_load_visual_qa_rejects_unknown_or_malformed_instance_fields(
    tmp_path: Path, extra_field: str
) -> None:
    _files(tmp_path)
    path = write_visual_qa(
        tmp_path, "generated-image-v1.png", parse_visual_qa_checks([_passing_check()]), REQUIRED
    )
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("- 实例结果: pass", f"{extra_field}\n- 实例结果: pass", 1),
        encoding="utf-8",
    )

    with pytest.raises(VisualQAError, match="格式无效"):
        load_visual_qa(path)


@pytest.mark.parametrize(
    "bad_check",
    [
        _passing_check().replace("hero-primary-part", "hero\nprimary-part", 1),
        _passing_check().replace("qa/hero-detail.png", "qa/hero\ndetail.png", 1),
        _passing_check().replace("qa/hero-context.png", "qa/hero\rcontext.png", 1),
        _passing_check().replace(
            "端点A经连续主体和连接件到端点B", "端点A经连续主体\n和连接件到端点B", 1
        ),
    ],
)
def test_parse_visual_qa_checks_rejects_line_breaks_before_lossy_round_trip(
    bad_check: str,
) -> None:
    with pytest.raises(VisualQAError, match="换行"):
        parse_visual_qa_checks([bad_check])


def test_record_visual_qa_command_writes_report_and_preserves_pending_status(
    tmp_path: Path, monkeypatch
) -> None:
    task_dir = tmp_path / "projects" / "demo" / "images" / "01-detail"
    task_dir.mkdir(parents=True)
    (task_dir / "brief.md").write_text("# 图片任务\n\n- 状态: pending_user_review\n", encoding="utf-8")
    identity = ProductIdentity(
        truth_sources=("product.png",),
        surface_graphics=("保持原图",),
        physical_constraints=("真实支撑",),
        human_interaction_constraints=("无人物",),
        components=("一个产品",),
        relationships=("部件关系保持原图",),
        visible_connection_evidence=("连接连续",),
        functional_features=("结构保持原图",),
        required_use_states=("静置",),
        assembly_state_evidence=("装配完整",),
        visible_component_instances=("hero-primary-part: 端点A到端点B连续",),
        forbidden_inventions=("禁止断裂",),
        approved=True,
    )
    write_product_identity(task_dir, identity)
    _files(task_dir)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)

    result = runner.main(
        [
            "record-visual-qa",
            "--project",
            "demo",
            "--image",
            "1",
            "--candidate",
            "generated-image-v1.png",
            "--instance-check",
            _passing_check(),
        ]
    )

    assert result == 0
    assert load_visual_qa(task_dir / "visual-qa.md").status == "passed"
    assert "pending_user_review" in (task_dir / "brief.md").read_text(encoding="utf-8")


def test_approve_image_command_requires_passing_visual_qa(tmp_path: Path, monkeypatch) -> None:
    task_dir = tmp_path / "projects" / "demo" / "images" / "01-detail"
    task_dir.mkdir(parents=True)
    (task_dir / "brief.md").write_text("- 状态: pending_user_review\n", encoding="utf-8")
    identity = ProductIdentity(
        truth_sources=("product.png",), surface_graphics=("保持原图",),
        physical_constraints=("真实支撑",), human_interaction_constraints=("无人物",),
        components=("一个产品",), relationships=("保持连接",),
        visible_connection_evidence=("连续可见",), functional_features=("保持结构",),
        required_use_states=("静置",), assembly_state_evidence=("装配完整",),
        visible_component_instances=("hero-primary-part: 端点A到端点B连续",),
        forbidden_inventions=("禁止断裂",), approved=True,
    )
    write_product_identity(task_dir, identity)
    _files(task_dir)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)

    missing_result = runner.main(
        ["approve-image", "--project", "demo", "--image", "1", "--candidate", "generated-image-v1.png"]
    )
    assert missing_result == 1
    assert "pending_user_review" in (task_dir / "brief.md").read_text(encoding="utf-8")

    write_visual_qa(
        task_dir,
        "generated-image-v1.png",
        parse_visual_qa_checks(
            [_passing_check()]
        ),
        REQUIRED,
    )
    passing_result = runner.main(
        ["approve-image", "--project", "demo", "--image", "1", "--candidate", "generated-image-v1.png"]
    )
    assert passing_result == 0
    assert "- 状态: approved" in (task_dir / "brief.md").read_text(encoding="utf-8")


def test_approve_image_rejects_legacy_report(tmp_path: Path, monkeypatch) -> None:
    task_dir = tmp_path / "projects" / "demo" / "images" / "01-detail"
    task_dir.mkdir(parents=True)
    brief_path = task_dir / "brief.md"
    brief_text = "- 状态: pending_user_review\n"
    brief_path.write_text(brief_text, encoding="utf-8")
    identity = ProductIdentity(
        truth_sources=("product.png",), surface_graphics=("保持原图",),
        physical_constraints=("真实支撑",), human_interaction_constraints=("无人物",),
        components=("一个产品",), relationships=("保持连接",),
        visible_connection_evidence=("连续可见",), functional_features=("保持结构",),
        required_use_states=("静置",), assembly_state_evidence=("装配完整",),
        visible_component_instances=("hero-primary-part: 端点A到端点B连续",),
        forbidden_inventions=("禁止断裂",), approved=True,
    )
    write_product_identity(task_dir, identity)
    _files(task_dir)
    (task_dir / "visual-qa.md").write_text(
        "# 可见部件实例质检\n\n"
        "- 候选图: generated-image-v1.png\n"
        "- 状态: passed\n\n"
        "## hero-primary-part\n\n"
        "- 裁图: qa/hero-detail.png\n"
        "- 结果: pass\n"
        "- 追踪: 端点A到端点B连续\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "root", lambda: tmp_path)

    result = runner.main(
        ["approve-image", "--project", "demo", "--image", "1", "--candidate", "generated-image-v1.png"]
    )

    assert result == 1
    assert brief_path.read_text(encoding="utf-8") == brief_text


def test_approve_image_rejects_clearance_failure(tmp_path: Path, monkeypatch) -> None:
    task_dir = tmp_path / "projects" / "demo" / "images" / "01-detail"
    task_dir.mkdir(parents=True)
    brief_path = task_dir / "brief.md"
    brief_text = "- 状态: pending_user_review\n"
    brief_path.write_text(brief_text, encoding="utf-8")
    identity = ProductIdentity(
        truth_sources=("product.png",), surface_graphics=("保持原图",),
        physical_constraints=("真实支撑",), human_interaction_constraints=("无人物",),
        components=("一个产品",), relationships=("保持连接",),
        visible_connection_evidence=("连续可见",), functional_features=("保持结构",),
        required_use_states=("静置",), assembly_state_evidence=("装配完整",),
        visible_component_instances=("hero-primary-part: 端点A到端点B连续",),
        forbidden_inventions=("禁止断裂",), approved=True,
    )
    write_product_identity(task_dir, identity)
    _files(task_dir)
    write_visual_qa(
        task_dir,
        "generated-image-v1.png",
        parse_visual_qa_checks(
            [_passing_check().replace("clearance=pass:整条路径与周围实体保持可见净空", "clearance=fail:路径穿过固定主体", 1)]
        ),
        REQUIRED,
    )
    monkeypatch.setattr(runner, "root", lambda: tmp_path)

    result = runner.main(
        ["approve-image", "--project", "demo", "--image", "1", "--candidate", "generated-image-v1.png"]
    )

    assert result == 1
    assert brief_path.read_text(encoding="utf-8") == brief_text

from __future__ import annotations

from pathlib import Path

import pytest

from workflow.models import DisplayCopy, ProductIdentity, TemplateMetadata, TemplateRecord
from workflow.projects import (
    ProjectError,
    load_display_copy,
    load_product_identity,
    parse_visible_component_instances,
    prepare_image_task,
    select_template,
    write_display_copy,
    write_product_identity,
)
from workflow import runner
from workflow.templates import load_template_record, write_template_record
from workflow.visual_qa import parse_visual_qa_checks, write_visual_qa


def _write_passing_previous_image_qa(task_dir: Path) -> None:
    identity = ProductIdentity(
        truth_sources=("product.png",),
        surface_graphics=("保持原图",),
        physical_constraints=("真实支撑",),
        human_interaction_constraints=("无人物",),
        components=("一个产品",),
        relationships=("保持原始连接",),
        visible_connection_evidence=("连接连续可见",),
        functional_features=("保持原始结构",),
        required_use_states=("静置",),
        assembly_state_evidence=("装配完整",),
        visible_component_instances=("hero-primary-part: 端点A到端点B连续",),
        forbidden_inventions=("禁止断裂",),
        approved=True,
    )
    write_product_identity(task_dir, identity)
    (task_dir / "qa").mkdir()
    (task_dir / "candidate.png").write_bytes(b"candidate")
    (task_dir / "qa" / "hero-detail.png").write_bytes(b"detail")
    (task_dir / "qa" / "hero-context.png").write_bytes(b"context")
    write_visual_qa(
        task_dir,
        "candidate.png",
        parse_visual_qa_checks(
            [
                "hero-primary-part|qa/hero-detail.png|qa/hero-context.png|"
                "topology=pass:端点A经连续主体到端点B|"
                "support=pass:主体由桌面稳定支撑|"
                "clearance=pass:整条路径与周围实体保持净空|"
                "assembly=pass:部件装配状态完整且无冲突|"
                "framing=pass:画框无意外留白带且关键主体完整"
            ]
        ),
        {"hero-primary-part": "端点A到端点B连续"},
    )


@pytest.fixture
def template_record() -> TemplateRecord:
    return TemplateRecord(
        template_id="amazon-clean-main",
        platform="amazon",
        role="main image",
        aspect_ratio="1:1",
        output_size="2000x2000",
        layout="product centered",
        copy_safe_zone="top 20%",
        style="clean",
        scene="white studio",
        suitable_for=["small products"],
        avoid_for=[],
        references=["template-reference.png"],
    )


def test_select_template_prioritizes_platform_and_role() -> None:
    candidates = [
        TemplateRecord("taobao-main", "taobao", "main image", "1:1", "800x800", "center", "none", "warm", "studio", [], [], []),
        TemplateRecord("amazon-selling", "amazon", "selling-point image", "1:1", "2000x2000", "right product", "left 40%", "bright", "studio", [], [], []),
        TemplateRecord("amazon-main", "amazon", "main image", "1:1", "2000x2000", "center", "none", "clean", "white", [], [], []),
    ]

    selected = select_template(candidates, platform="amazon", role="main image", aspect_ratio="1:1")

    assert selected.template_id == "amazon-main"


def test_select_template_uses_template_id_for_ties(template_record: TemplateRecord) -> None:
    later = TemplateRecord(
        template_id="z-last",
        platform=template_record.platform,
        role=template_record.role,
        aspect_ratio=template_record.aspect_ratio,
        output_size=template_record.output_size,
        layout=template_record.layout,
        copy_safe_zone=template_record.copy_safe_zone,
        style=template_record.style,
        scene=template_record.scene,
        suitable_for=[],
        avoid_for=[],
        references=[],
    )
    earlier = TemplateRecord(
        template_id="a-first",
        platform=template_record.platform,
        role=template_record.role,
        aspect_ratio=template_record.aspect_ratio,
        output_size=template_record.output_size,
        layout=template_record.layout,
        copy_safe_zone=template_record.copy_safe_zone,
        style=template_record.style,
        scene=template_record.scene,
        suitable_for=[],
        avoid_for=[],
        references=[],
    )

    selected = select_template([later, earlier], "amazon", "main image", "1:1")

    assert selected.template_id == "a-first"


def test_select_template_scores_layout_and_safe_zone_keywords(template_record: TemplateRecord) -> None:
    alternate = TemplateRecord(
        template_id="amazon-alternate-main",
        platform=template_record.platform,
        role=template_record.role,
        aspect_ratio=template_record.aspect_ratio,
        output_size=template_record.output_size,
        layout="product on right",
        copy_safe_zone="left 40%",
        style=template_record.style,
        scene=template_record.scene,
        suitable_for=[],
        avoid_for=[],
        references=[],
    )

    selected = select_template(
        [template_record, alternate],
        "amazon",
        "main image",
        "1:1",
        layout_keywords=["right"],
        safe_zone_keywords=["left"],
    )

    assert selected.template_id == "amazon-alternate-main"


def test_select_template_requires_platform_and_role_match(template_record: TemplateRecord) -> None:
    with pytest.raises(ProjectError, match="review-templates"):
        select_template([template_record], "taobao", "main image", "1:1")


def test_select_template_allows_generic_but_not_another_explicit_platform() -> None:
    generic = TemplateRecord("generic-hero", "generic", "main image", "1:1", "1200x1200", "center", "none", "clean", "studio", [], [], [])
    taobao = TemplateRecord("taobao-hero", "taobao", "main image", "1:1", "1200x1200", "center", "none", "clean", "studio", [], [], [])

    selected = select_template([generic, taobao], "amazon", "main image", "1:1")

    assert selected.template_id == "generic-hero"


def test_select_template_scores_product_position_and_scene_keywords() -> None:
    metadata = TemplateMetadata(
        role="main image", aspect_ratio="1:1", output_size="1200x1200", layout="product right",
        copy_safe_zone="left", style="clean", scene="kitchen", suitable_for=(), avoid_for=(),
        product_position="right", copy_density="low", card_count=1, scene_type="kitchen",
        non_transferable_elements=(),
    )
    hero = TemplateRecord("hero", "amazon", "main image", "1:1", "1200x1200", "product right", "left", "clean", "kitchen", [], [], [], metadata=metadata)
    alternate = TemplateRecord("alternate", "amazon", "main image", "1:1", "1200x1200", "product center", "right", "clean", "studio", [], [], [])

    selected = select_template(
        [alternate, hero], "amazon", "main image", "1:1",
        product_position_keywords=["right"], scene_keywords=["kitchen"],
    )

    assert selected.template_id == "hero"


def test_select_template_honors_agent_selected_template_set_module() -> None:
    comparison = TemplateRecord(
        "warm-organic-brown-editorial-01--benefit-comparison", "amazon", "详情页横幅图", "97:60", "970x600",
        "left benefits, right comparison", "right comparison copy", "warm brown", "studio", [], [], [],
        template_set_id="warm-organic-brown-editorial-01", module_id="benefit-comparison",
    )
    hero = TemplateRecord(
        "warm-organic-brown-editorial-01--feature-hero", "amazon", "详情页横幅图", "97:60", "970x600",
        "left lifestyle image, right title", "right title copy", "warm brown", "studio", [], [], [],
        template_set_id="warm-organic-brown-editorial-01", module_id="feature-hero",
    )

    selected = select_template(
        [comparison, hero], "amazon", "详情页横幅图", "97:60",
        template_set_id="warm-organic-brown-editorial-01", module_id="feature-hero",
    )

    assert selected == hero


def test_prepare_image_task_writes_first_image_artifacts(tmp_path: Path, template_record: TemplateRecord) -> None:
    task_dir = prepare_image_task(
        tmp_path,
        "demo-product",
        template_record,
        ["front.png", "side.png"],
        "Create a clean hero image.",
        1,
        False,
    )

    request = (tmp_path / "projects" / "demo-product" / "request.md").read_text(encoding="utf-8")
    selected = (tmp_path / "projects" / "demo-product" / "selected-template.md").read_text(encoding="utf-8")
    brief = (task_dir / "brief.md").read_text(encoding="utf-8")
    assert task_dir == tmp_path / "projects" / "demo-product" / "images" / "01-main-image"
    assert "平台: amazon" in request
    assert "图片用途: main image" in request
    assert "front.png" in request
    assert "Create a clean hero image." in request
    assert "all_images: false" in request
    assert "amazon-clean-main" in selected
    assert "template-reference.png" in selected
    assert "pending_user_route" in brief


def test_display_copy_round_trips_with_evidence(tmp_path: Path) -> None:
    copy = DisplayCopy(
        language="English",
        headline="VITAMINS + MINERALS",
        subheadline="2 GUMMIES PER SERVING",
        labels=("VITAMIN D", "B VITAMINS"),
        evidence=("Supplement Facts panel",),
    )

    path = write_display_copy(tmp_path, copy)

    assert path.name == "copy-brief.md"
    assert load_display_copy(path) == copy


def test_product_identity_round_trips_component_relationship_and_forbidden_rules(tmp_path: Path) -> None:
    identity = ProductIdentity(
        truth_sources=("product-front.png", "product-detail.png"),
        surface_graphics=("杯身图案、文字、数量和排布逐项保持原图",),
        physical_constraints=("勺柄末端由杯盖表面稳定支撑，不得水平悬空",),
        human_interaction_constraints=("单人操作；左右手和腕部姿态必须可执行",),
        visible_connection_evidence=("球端必须显示连接套环和连续勺杆",),
        components=("1 个杯子", "1 个杯盖", "1 把完整长勺"),
        relationships=("棕色球形末端固定连接在金属勺杆上",),
        functional_features=("杯盖边缘有供勺杆穿过的专用缺口",),
        required_use_states=("合盖时勺杆穿过缺口，勺头在杯内，棕色末端在杯外",),
        assembly_state_evidence=(
            "合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸",
        ),
        visible_component_instances=(
            "hero-primary-part: 主部件；端点A → 连续结构 → 连接件 → 端点B；无遮挡；桌面支撑；禁止断裂",
        ),
        forbidden_inventions=("独立的棕色球形摆件",),
        unknowns=(),
        approved=True,
    )

    path = write_product_identity(tmp_path, identity)

    assert path.name == "product-identity.md"
    assert load_product_identity(path) == identity


@pytest.mark.parametrize(
    ("omitted_heading", "message"),
    [
        ("唯一事实依据", "唯一事实依据"),
        ("表面图案与印刷", "表面图案与印刷"),
        ("物理与支撑关系", "物理与支撑关系"),
        ("人物与动作可行性", "人物与动作可行性"),
        ("可见连接证据", "可见连接证据"),
        ("功能结构", "功能结构"),
        ("必须呈现的使用状态", "必须呈现的使用状态"),
        ("装配状态证据", "装配状态证据"),
        ("可见部件实例", "可见部件实例"),
    ],
)
def test_product_identity_rejects_missing_functional_sections(
    tmp_path: Path, omitted_heading: str, message: str
) -> None:
    sections = {
        "唯一事实依据": "- product-front.png",
        "表面图案与印刷": "- 无表面图案或印刷",
        "物理与支撑关系": "- 所有物体遵循重力并由真实接触面稳定支撑",
        "人物与动作可行性": "- 单人操作；左右手和腕部姿态必须可执行",
        "可见连接证据": "- 球端必须显示连接套环和连续勺杆",
        "部件与数量": "- 1 个杯子",
        "部件关系": "- 杯盖属于杯子",
        "功能结构": "- 杯盖边缘有专用缺口",
        "必须呈现的使用状态": "- 勺杆穿过缺口",
        "装配状态证据": "- 合盖时杯盖安装在杯口，勺杆由杯内经缺口向外延伸",
        "可见部件实例": "- hero-primary-part: 端点A → 连续结构 → 端点B",
        "禁止出现": "- 独立球形摆件",
        "待用户确认": "- 无",
    }
    sections.pop(omitted_heading)
    body = "\n\n".join(f"## {heading}\n\n{value}" for heading, value in sections.items())
    path = tmp_path / "product-identity.md"
    path.write_text(f"# 产品一致性清单\n\n- 状态: approved\n\n{body}\n", encoding="utf-8")

    with pytest.raises(ProjectError, match=message):
        load_product_identity(path)


def test_product_identity_rejects_empty_required_sections(tmp_path: Path) -> None:
    path = tmp_path / "product-identity.md"
    path.write_text(
        "# 产品一致性清单\n\n- 状态: approved\n\n"
        "## 唯一事实依据\n\n- product-front.png\n\n"
        "## 表面图案与印刷\n\n- 无表面图案或印刷\n\n"
        "## 物理与支撑关系\n\n- 所有物体遵循重力并由真实接触面稳定支撑\n\n"
        "## 人物与动作可行性\n\n- 单人操作；左右手和腕部姿态必须可执行\n\n"
        "## 可见连接证据\n\n- 球端必须显示连接套环和连续勺杆\n\n"
        "## 部件与数量\n\n- 无\n\n"
        "## 部件关系\n\n- 无\n\n"
        "## 功能结构\n\n- 无特殊功能结构\n\n"
        "## 必须呈现的使用状态\n\n- 按参考图保持标准状态\n\n"
        "## 装配状态证据\n\n- 已拆卸部件不演示安装状态功能\n\n"
        "## 可见部件实例\n\n- hero-primary-part: 端点A → 连续结构 → 端点B\n\n"
        "## 禁止出现\n\n- 无\n\n"
        "## 待用户确认\n\n- 无\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectError, match="部件与数量"):
        load_product_identity(path)


def test_product_identity_rejects_empty_assembly_state_evidence_section(tmp_path: Path) -> None:
    path = tmp_path / "product-identity.md"
    path.write_text(
        "# 产品一致性清单\n\n- 状态: approved\n\n"
        "## 唯一事实依据\n\n- product-front.png\n\n"
        "## 表面图案与印刷\n\n- 无表面图案或印刷\n\n"
        "## 物理与支撑关系\n\n- 所有物体由真实接触面稳定支撑\n\n"
        "## 人物与动作可行性\n\n- 无人物或手部\n\n"
        "## 部件与数量\n\n- 1 个杯子\n\n"
        "## 部件关系\n\n- 杯盖属于杯子\n\n"
        "## 可见连接证据\n\n- 勺杆连接连续\n\n"
        "## 功能结构\n\n- 杯盖边缘有开放缺口\n\n"
        "## 必须呈现的使用状态\n\n- 合盖使用\n\n"
        "## 装配状态证据\n\n- 无\n\n"
        "## 禁止出现\n\n- 混合互斥状态\n\n"
        "## 待用户确认\n\n- 无\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectError, match="装配状态证据"):
        load_product_identity(path)


@pytest.mark.parametrize(
    ("items", "message"),
    [
        ((), "可见部件实例不能为空"),
        (("Bad_ID: 连续结构",), "格式无效"),
        (("missing-description:",), "格式无效"),
        (("missing-colon",), "格式无效"),
        (("valid-id: 连续结构", "valid-id: 重复"), "ID 重复"),
    ],
)
def test_parse_visible_component_instances_rejects_invalid_contracts(
    items: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ProjectError, match=message):
        parse_visible_component_instances(items)


def test_prepare_image_task_records_template_set_and_module_reference(tmp_path: Path, template_record: TemplateRecord) -> None:
    module = TemplateRecord(
        "warm-organic-brown-editorial-01--feature-hero",
        "amazon",
        "详情页横幅图",
        "97:60",
        "970x600",
        "left lifestyle image, right title, bottom icon strip",
        "right title; bottom icon strip",
        "warm brown editorial",
        "home kitchen",
        [],
        [],
        ["reference-01.png"],
        template_set_id="warm-organic-brown-editorial-01",
        module_id="feature-hero",
    )

    prepare_image_task(tmp_path, "demo", module, ["product.png"], "make image", 1, False)

    selected = (tmp_path / "projects" / "demo" / "selected-template.md").read_text(encoding="utf-8")
    assert "模板体系 ID: warm-organic-brown-editorial-01" in selected
    assert "模块 ID: feature-hero" in selected
    assert "template-library/amazon/warm-organic-brown-editorial-01/modules/feature-hero/reference-01.png" in selected


def test_prepare_image_task_keeps_chinese_role_in_task_directory(tmp_path: Path, template_record: TemplateRecord) -> None:
    chinese_role_template = TemplateRecord(
        template_record.template_id,
        template_record.platform,
        "详情页横幅图",
        template_record.aspect_ratio,
        template_record.output_size,
        template_record.layout,
        template_record.copy_safe_zone,
        template_record.style,
        template_record.scene,
        template_record.suitable_for,
        template_record.avoid_for,
        template_record.references,
    )

    task_dir = prepare_image_task(tmp_path, "demo", chinese_role_template, ["product.png"], "make image", 1, False)

    assert task_dir.name == "01-详情页横幅图"


def test_prepare_image_task_blocks_next_image_until_approval(tmp_path: Path, template_record: TemplateRecord) -> None:
    prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 1, False)

    with pytest.raises(ProjectError, match="approved"):
        prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 2, False)


def test_prepare_image_task_rejects_manual_approval_without_visual_qa(tmp_path: Path, template_record: TemplateRecord) -> None:
    first = prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 1, False)
    (first / "brief.md").write_text("状态: approved\n", encoding="utf-8")

    with pytest.raises(ProjectError, match="逐实例视觉质检"):
        prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 2, False)


def test_prepare_image_rejects_approved_status_with_legacy_report(
    tmp_path: Path, template_record: TemplateRecord
) -> None:
    first = prepare_image_task(
        tmp_path, "demo", template_record, ["product.png"], "make images", 1, False
    )
    write_product_identity(
        first,
        ProductIdentity(
            truth_sources=("product.png",),
            surface_graphics=("保持原图",),
            physical_constraints=("真实支撑",),
            human_interaction_constraints=("无人物",),
            components=("一个产品",),
            relationships=("保持原始连接",),
            visible_connection_evidence=("连接连续可见",),
            functional_features=("保持原始结构",),
            required_use_states=("静置",),
            assembly_state_evidence=("装配完整",),
            visible_component_instances=("hero-primary-part: 端点A到端点B连续",),
            forbidden_inventions=("禁止断裂",),
            approved=True,
        ),
    )
    (first / "brief.md").write_text("状态: approved\n", encoding="utf-8")
    (first / "qa").mkdir()
    (first / "candidate.png").write_bytes(b"candidate")
    (first / "qa" / "hero-detail.png").write_bytes(b"detail")
    (first / "qa" / "hero-context.png").write_bytes(b"context")
    (first / "visual-qa.md").write_text(
        "# 可见部件实例质检\n\n"
        "- 候选图: candidate.png\n"
        "- 状态: passed\n\n"
        "## hero-primary-part\n\n"
        "- 裁图: qa/hero-detail.png\n"
        "- 结果: pass\n"
        "- 追踪: 端点A到端点B连续\n",
        encoding="utf-8",
    )

    with pytest.raises(ProjectError, match="上一张图片缺少通过的逐实例视觉质检"):
        prepare_image_task(
            tmp_path, "demo", template_record, ["product.png"], "make images", 2, False
        )


def test_prepare_image_accepts_complete_version_2_report(tmp_path: Path, template_record: TemplateRecord) -> None:
    first = prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 1, False)
    _write_passing_previous_image_qa(first)
    (first / "brief.md").write_text("状态: approved\n", encoding="utf-8")

    second = prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 2, False)

    assert second.name == "02-main-image"


def test_prepare_image_task_reads_approval_from_previous_role(tmp_path: Path, template_record: TemplateRecord) -> None:
    first = prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 1, False)
    _write_passing_previous_image_qa(first)
    (first / "brief.md").write_text("状态: approved\n", encoding="utf-8")
    next_role = TemplateRecord(
        "amazon-selling",
        "amazon",
        "selling-point image",
        "1:1",
        "2000x2000",
        "product right",
        "left 40%",
        "bright",
        "studio",
        [],
        [],
        [],
    )

    second = prepare_image_task(tmp_path, "demo", next_role, ["product.png"], "make images", 2, False)

    assert second.name == "02-selling-point-image"


def test_prepare_image_task_all_images_bypasses_approval(tmp_path: Path, template_record: TemplateRecord) -> None:
    prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 1, False)

    second = prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 2, True)

    assert second.name == "02-main-image"


@pytest.mark.parametrize("slug", ["../outside", "nested/demo", "nested\\demo", ".", ""])
def test_prepare_image_task_rejects_unsafe_slug(tmp_path: Path, template_record: TemplateRecord, slug: str) -> None:
    with pytest.raises(ProjectError, match="slug"):
        prepare_image_task(tmp_path, slug, template_record, ["product.png"], "make images", 1, False)


def test_prepare_image_task_refuses_to_overwrite_existing_image(tmp_path: Path, template_record: TemplateRecord) -> None:
    prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 1, False)

    with pytest.raises(ProjectError, match="already exists"):
        prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "changed request", 1, False)


def test_prepare_image_task_refuses_duplicate_number_with_different_role(tmp_path: Path, template_record: TemplateRecord) -> None:
    prepare_image_task(tmp_path, "demo", template_record, ["product.png"], "make images", 1, False)
    next_role = TemplateRecord(
        "amazon-selling",
        "amazon",
        "selling-point image",
        "1:1",
        "2000x2000",
        "product right",
        "left 40%",
        "bright",
        "studio",
        [],
        [],
        [],
    )

    with pytest.raises(ProjectError, match="already exists"):
        prepare_image_task(tmp_path, "demo", next_role, ["product.png"], "make images", 1, False)


def test_load_template_record_round_trips_registered_template(tmp_path: Path, template_record: TemplateRecord) -> None:
    directory = tmp_path / "template-library" / "amazon" / template_record.template_id
    write_template_record(directory, template_record)

    loaded = load_template_record(directory)

    assert loaded == template_record


def test_load_template_record_preserves_empty_reference_list(tmp_path: Path, template_record: TemplateRecord) -> None:
    empty_references = TemplateRecord(
        template_record.template_id,
        template_record.platform,
        template_record.role,
        template_record.aspect_ratio,
        template_record.output_size,
        template_record.layout,
        template_record.copy_safe_zone,
        template_record.style,
        template_record.scene,
        template_record.suitable_for,
        template_record.avoid_for,
        [],
    )
    directory = tmp_path / "template-library" / "amazon" / empty_references.template_id
    write_template_record(directory, empty_references)

    loaded = load_template_record(directory)

    assert loaded.references == []


def test_prepare_image_command_selects_registered_template(tmp_path: Path, template_record: TemplateRecord, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "template-library" / "amazon" / template_record.template_id
    write_template_record(directory, template_record)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)

    result = runner.main(
        [
            "prepare-image",
            "--project",
            "demo",
            "--platform",
            "amazon",
            "--role",
            "main image",
            "--ratio",
            "1:1",
            "--product-reference",
            "product.png",
            "--request",
            "make images",
        ]
    )

    assert result == 0
    assert (tmp_path / "projects" / "demo" / "selected-template.md").exists()


def test_prepare_image_command_records_actual_match_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template_record = TemplateRecord(
        "amazon-right-main",
        "amazon",
        "main image",
        "1:1",
        "2000x2000",
        "product on right",
        "left 40%",
        "bright",
        "studio",
        [],
        [],
        [],
    )
    write_template_record(tmp_path / "template-library" / "amazon" / template_record.template_id, template_record)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)

    runner.main(
        [
            "prepare-image",
            "--project",
            "non-square-request",
            "--platform",
            "amazon",
            "--role",
            "main image",
            "--ratio",
            "4:5",
            "--layout-keyword",
            "right",
            "--safe-zone-keyword",
            "left",
            "--request",
            "make images",
        ]
    )

    selected = (tmp_path / "projects" / "non-square-request" / "selected-template.md").read_text(encoding="utf-8")
    assert "匹配得分: 160" in selected
    assert "版式关键词“right”匹配（+5）" in selected
    assert "文案安全区关键词“left”匹配（+5）" in selected
    assert "画幅比例完全匹配" not in selected

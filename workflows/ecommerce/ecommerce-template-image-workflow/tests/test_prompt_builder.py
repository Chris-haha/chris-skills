from pathlib import Path
import json

import pytest

from workflow.models import DisplayCopy, ProductIdentity, TemplateRecord
from workflow.geometry import create_geometry_preflight
from workflow.projects import (
    load_product_identity,
    ProjectError,
    validate_product_identity,
    write_product_identity,
    write_web_handoff,
)
from workflow.prompt_builder import build_direct_image_prompt
from workflow.templates import write_template_record
from workflow import runner
from workflow.visual_qa import parse_visual_qa_checks, write_visual_qa


def _template() -> TemplateRecord:
    return TemplateRecord(
        "amazon-selling-01", "amazon", "selling-point image", "1:1", "2000x2000",
        "product on right", "left 40%", "bright studio", "soft neutral", [], [], ["reference-01.png"],
    )


def _identity(
    *,
    approved: bool = True,
    unknowns: tuple[str, ...] = (),
    truth_sources: tuple[str, ...] = ("product-front.png",),
    surface_graphics: tuple[str, ...] = ("杯身图案严格保持原图中的元素、文字与排布",),
    physical_constraints: tuple[str, ...] = ("所有物体遵循重力并由真实接触面稳定支撑",),
    human_interaction_constraints: tuple[str, ...] = (
        "单人操作；左右手方向、腕部姿态和动作时序必须可执行",
    ),
    visible_connection_evidence: tuple[str, ...] = (
        "球端到勺杆必须显示银色连接套环和至少一段连续金属杆",
    ),
    functional_features: tuple[str, ...] = ("杯盖边缘有供勺杆穿过的专用缺口",),
    required_use_states: tuple[str, ...] = ("合盖时勺杆穿过缺口，勺头在杯内，棕色末端在杯外",),
    assembly_state_evidence: tuple[str, ...] = (
        "合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸",
    ),
    visible_component_instances: tuple[str, ...] = (
        "hero-primary-part: 主部件；端点A → 连续结构 → 连接件 → 端点B；无遮挡；桌面支撑；禁止断裂",
    ),
) -> ProductIdentity:
    return ProductIdentity(
        truth_sources=truth_sources,
        surface_graphics=surface_graphics,
        physical_constraints=physical_constraints,
        human_interaction_constraints=human_interaction_constraints,
        visible_connection_evidence=visible_connection_evidence,
        components=("1 个杯子", "1 个杯盖", "1 把完整长勺"),
        relationships=("棕色球形末端固定连接在金属勺杆上，属于同一把勺子",),
        functional_features=functional_features,
        required_use_states=required_use_states,
        assembly_state_evidence=assembly_state_evidence,
        visible_component_instances=visible_component_instances,
        forbidden_inventions=("独立的棕色球形摆件", "第二把勺子"),
        unknowns=unknowns,
        approved=approved,
    )


def _geometry(objective: str, identity: ProductIdentity | None = None) -> dict:
    identity = identity or _identity()
    constraints = {
        "rigidity": "rigid-straight-shaft",
        "joints": "fixed-ball-collar-no-hinge",
        "endpoints": "bowl-inside-ball-beside-notch",
        "direction": "single-straight-route-through-open-notch",
        "support": "bowl-and-collar-on-real-contact-surfaces",
    }
    return create_geometry_preflight({
        "version": 1,
        "checks": [{
            "instance_id": item.partition(":")[0],
            "dimensions": {
                name: {"allowed": [value], "required": [value], "verdict": "pass",
                       "sources": list(identity.truth_sources),
                       "evidence": f"The original product view supports {value}; the proposed pose preserves it.",
                       "conflicts": []}
                for name, value in constraints.items()
            },
        } for item in identity.visible_component_instances],
    }, identity, objective)


def _save_geometry(task_dir: Path, objective: str, identity: ProductIdentity | None = None) -> None:
    (task_dir / "geometry-preflight.json").write_text(
        json.dumps(_geometry(objective, identity)), encoding="utf-8",
    )


def test_build_direct_image_prompt_includes_product_identity_hard_constraints() -> None:
    prompt = build_direct_image_prompt(
        _template(),
        ["product-front.png"],
        "展示杯具",
        product_identity=_identity(),
        geometry_preflight=_geometry("展示杯具"),
    )

    assert "产品一致性硬约束" in prompt
    assert "唯一事实依据（最高优先级）" in prompt
    assert "product-front.png" in prompt
    assert "表面图案与印刷" in prompt
    assert "杯身图案严格保持原图中的元素、文字与排布" in prompt
    assert "历史生成图不得作为产品事实依据" in prompt
    assert "不得增删、替换、重排或风格化改写" in prompt
    assert "物理与支撑关系" in prompt
    assert "所有物体遵循重力并由真实接触面稳定支撑" in prompt
    assert "不得无支撑悬空" in prompt
    assert "手持或运动中的部件必须有明确施力与支撑来源" in prompt
    assert "人物与动作可行性" in prompt
    assert "单人操作；左右手方向、腕部姿态和动作时序必须可执行" in prompt
    assert "同一人可独立完成" in prompt
    assert "单手可以完成时优先只展示一只手" in prompt
    assert "镜像手" in prompt
    assert "1 把完整长勺" in prompt
    assert "棕色球形末端固定连接" in prompt
    assert "可见连接证据" in prompt
    assert "球端到勺杆必须显示银色连接套环和至少一段连续金属杆" in prompt
    assert "遮挡前后" in prompt
    assert "相邻、相切或叠放不能冒充固定连接" in prompt
    assert "功能结构" in prompt
    assert "杯盖边缘有供勺杆穿过的专用缺口" in prompt
    assert "必须呈现的使用状态" in prompt
    assert "合盖时勺杆穿过缺口" in prompt
    assert "装配状态证据" in prompt
    assert "同一功能交互中的主体与参与部件必须处于同一个真实装配状态" in prompt
    assert "已拆卸部件不能同时演示只有安装后才成立的使用关系" in prompt
    assert "不得生成封闭孔洞、桥状假结构或实体穿透" in prompt
    assert "可见部件实例" in prompt
    assert "hero-primary-part" in prompt
    assert "每个可见部件实例必须独立验收" in prompt
    assert "断口、残端、两截错位、凭空终止、穿透、错误归属" in prompt
    assert "占用空间" in prompt
    assert "允许接触面" in prompt
    assert "禁止相交实体" in prompt
    assert "路径净空" in prompt
    assert "无法区分正常遮挡与实体穿透时直接判定失败" in prompt
    assert "装饰性构图不能覆盖物理可行性" in prompt
    assert "产品画面必须填满预定媒体框" in prompt
    assert "上下或左右空白带" in prompt
    assert "不得拉伸产品" in prompt
    assert "必须先调整画框比例或版式" in prompt
    assert "不得省略、封闭、平滑或改变功能结构" in prompt
    assert "独立的棕色球形摆件" in prompt
    assert "不得拆分、复制、合并或新增" in prompt


@pytest.mark.parametrize(
    ("identity", "message"),
    [
        (_identity(approved=False), "尚未获得用户确认"),
        (_identity(unknowns=("球形部件属于哪里？",)), "球形部件属于哪里"),
        (_identity(functional_features=()), "功能结构不能为空"),
        (_identity(required_use_states=()), "必须呈现的使用状态不能为空"),
        (_identity(truth_sources=()), "唯一事实依据不能为空"),
        (_identity(surface_graphics=()), "表面图案与印刷不能为空"),
        (_identity(physical_constraints=()), "物理与支撑关系不能为空"),
        (_identity(human_interaction_constraints=()), "人物与动作可行性不能为空"),
        (_identity(visible_connection_evidence=()), "可见连接证据不能为空"),
        (_identity(assembly_state_evidence=()), "装配状态证据不能为空"),
        (_identity(visible_component_instances=()), "可见部件实例不能为空"),
    ],
)
def test_validate_product_identity_blocks_unapproved_or_unknown(
    identity: ProductIdentity, message: str
) -> None:
    with pytest.raises(ProjectError, match=message):
        validate_product_identity(identity)


def test_build_direct_image_prompt_is_direct_and_lists_references() -> None:
    prompt = build_direct_image_prompt(
        template=_template(),
        product_references=["product-front.png", "product-side.png"],
        objective="展示材质细节",
        product_identity=_identity(),
        geometry_preflight=_geometry("展示材质细节"),
    )

    assert "直接生成一张图片" in prompt
    assert "product-front.png" in prompt
    assert "reference-01.png" in prompt
    assert "不要分析过程" in prompt
    assert "生成提示词" not in prompt
    assert "仅复用模板的版式和视觉语言" in prompt
    assert "不得照搬模板参考图中的产品、品类或道具" in prompt


def test_build_direct_image_prompt_rejects_truth_source_not_in_product_references() -> None:
    with pytest.raises(ProjectError, match="未列入当前原始产品参考图"):
        build_direct_image_prompt(
            template=_template(),
            product_references=["product-front.png"],
            objective="展示材质细节",
            product_identity=_identity(truth_sources=("product-detail.png",)),
        )


def test_build_direct_image_prompt_rejects_generated_image_as_truth_source() -> None:
    with pytest.raises(ProjectError, match="历史生成图不能作为产品事实依据"):
        build_direct_image_prompt(
            template=_template(),
            product_references=["generated-image-v2.png"],
            objective="展示材质细节",
            product_identity=_identity(truth_sources=("generated-image-v2.png",)),
        )


def test_build_direct_image_prompt_renders_display_copy_without_redrawing_package_text() -> None:
    prompt = build_direct_image_prompt(
        template=_template(),
        product_references=["product-front.png"],
        objective="展示营养配方",
        display_copy=DisplayCopy(
            language="English",
            headline="VITAMINS + MINERALS",
            subheadline="2 GUMMIES PER SERVING",
            labels=("VITAMINS A + C", "VITAMIN D", "B VITAMINS", "ZINC + IODINE"),
            evidence=("Supplement Facts panel",),
        ),
        product_identity=_identity(),
        geometry_preflight=_geometry("展示营养配方"),
    )

    assert "VITAMINS + MINERALS" in prompt
    assert "2 GUMMIES PER SERVING" in prompt
    assert "VITAMINS A + C" in prompt
    assert "将以上展示文案逐字清晰排版" in prompt
    assert "不要重绘或生成包装上的 Logo、包装文字、营养成分表、条码或法规标签" in prompt
    assert "不要生成可读文字或乱码文字" not in prompt


def test_write_web_handoff_lists_required_uploads_without_gateway_credentials(tmp_path: Path) -> None:
    task_dir = tmp_path / "images" / "01-selling-point-image"
    prompt = build_direct_image_prompt(
        _template(), ["product-front.png"], "展示材质细节", product_identity=_identity(),
        geometry_preflight=_geometry("展示材质细节"),
    )

    path = write_web_handoff(
        task_dir, prompt, _template(), ["product-front.png"], product_identity=_identity(),
        geometry_preflight=_geometry("展示材质细节"),
    )

    text = path.read_text(encoding="utf-8")
    identity_section = text.split("## 产品一致性检查\n", 1)[1]
    assert path.name == "web-chatgpt-prompt.md"
    assert "必须上传的产品图" in text
    assert "product-front.png" in text
    assert "必须上传的模板图" in text
    assert "reference-01.png" in text
    assert "每次仅生成当前一张" in text
    assert "逐项核对功能结构" in text
    assert "逐项核对使用状态" in text
    assert "只以这些原始产品图为产品事实依据" in text
    assert "逐项核对表面图案与印刷" in text
    assert "逐项核对物理与支撑关系" in text
    assert "重力、支撑点、接触关系和稳定静置姿态" in text
    assert "逐项核对人物与动作可行性" in text
    assert "人数、左右手职责、进场方向、握持点、关节姿态和动作时序" in text
    assert "逐项核对可见连接证据" in text
    assert "端点、连接件、连续段、遮挡入口与出口、所属主体" in text
    assert "场景状态、承载主体、功能结构、交互部件路径、支撑来源和遮挡一致性" in text
    assert "混合互斥装配状态" in text
    assert "端点消失" in text
    assert "镜像手" in text
    assert "占用空间" in identity_section
    assert "允许接触面" in identity_section
    assert "禁止相交实体" in identity_section
    assert "路径净空" in identity_section
    assert "无法区分正常遮挡与实体穿透时直接判定失败" in identity_section
    assert "装饰性构图不能覆盖物理可行性" in identity_section
    assert "topology" in identity_section
    assert "support" in identity_section
    assert "clearance" in identity_section
    assert "assembly" in identity_section
    assert "任一维度失败即整图失败" in identity_section
    assert "api_key" not in text
    assert "base_url" not in text


def test_web_handoff_identifies_template_set_module_reference_path(tmp_path: Path) -> None:
    template = TemplateRecord(
        "warm-organic-brown-editorial-01--feature-hero", "amazon", "详情页横幅图", "97:60", "970x600",
        "left image, right title", "right title", "warm brown", "kitchen", [], [], ["reference-01.png"],
        template_set_id="warm-organic-brown-editorial-01", module_id="feature-hero",
    )

    prompt = build_direct_image_prompt(
        template, ["product-front.png"], "展示材质细节", product_identity=_identity(),
        geometry_preflight=_geometry("展示材质细节"),
    )
    path = write_web_handoff(
        tmp_path,
        prompt,
        template,
        ["product-front.png"],
        product_identity=_identity(),
        geometry_preflight=_geometry("展示材质细节"),
    )

    assert "template-library/amazon/warm-organic-brown-editorial-01/modules/feature-hero/reference-01.png" in path.read_text(encoding="utf-8")


def test_write_web_handoff_command_creates_direct_prompt_for_current_image(
    tmp_path: Path, monkeypatch
) -> None:
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product-front.png", "--request", "show detail",
        ]
    )
    task_dir = tmp_path / "projects" / "demo" / "images" / "01-selling-point-image"
    write_product_identity(task_dir, _identity())
    _save_geometry(task_dir, "展示材质细节")

    result = runner.main(
        ["write-web-handoff", "--project", "demo", "--image", "1", "--objective", "展示材质细节"]
    )

    handoff = (tmp_path / "projects" / "demo" / "images" / "01-selling-point-image" / "web-chatgpt-prompt.md")
    assert result == 0
    assert "展示材质细节" in handoff.read_text(encoding="utf-8")


def test_web_handoff_includes_display_copy_for_current_image(tmp_path: Path, monkeypatch) -> None:
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product-front.png", "--request", "show nutrients",
        ]
    )
    task_dir = tmp_path / "projects" / "demo" / "images" / "01-selling-point-image"
    write_product_identity(task_dir, _identity())
    _save_geometry(task_dir, "show nutrients")

    result = runner.main(
        [
            "set-display-copy", "--project", "demo", "--image", "1", "--language", "English",
            "--headline", "VITAMINS + MINERALS", "--subheadline", "2 GUMMIES PER SERVING",
            "--label", "VITAMIN D", "--evidence", "Supplement Facts panel",
        ]
    )
    runner.main(["write-web-handoff", "--project", "demo", "--image", "1", "--objective", "show nutrients"])

    handoff = (tmp_path / "projects" / "demo" / "images" / "01-selling-point-image" / "web-chatgpt-prompt.md")
    text = handoff.read_text(encoding="utf-8")
    assert result == 0
    assert "VITAMINS + MINERALS" in text
    assert "2 GUMMIES PER SERVING" in text
    assert "VITAMIN D" in text
    assert "展示文案检查" in text


def test_web_handoff_uses_template_selected_for_current_image(tmp_path: Path, monkeypatch) -> None:
    first = TemplateRecord(
        "amazon-hero", "amazon", "selling-point image", "1:1", "2000x2000",
        "hero layout", "right title", "bright studio", "lifestyle", [], [], ["hero-reference.png"],
    )
    second = TemplateRecord(
        "amazon-ingredients", "amazon", "selling-point image", "1:1", "2000x2000",
        "ingredient grid", "top title", "bright studio", "ingredients", [], [], ["ingredient-reference.png"],
    )
    write_template_record(tmp_path / "template-library" / "amazon" / first.template_id, first)
    write_template_record(tmp_path / "template-library" / "amazon" / second.template_id, second)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)

    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product.png", "--request", "first image",
        ]
    )
    first_brief = tmp_path / "projects" / "demo" / "images" / "01-selling-point-image" / "brief.md"
    first_task = first_brief.parent
    write_product_identity(first_task, _identity(truth_sources=("product.png",)))
    (first_task / "qa").mkdir()
    (first_task / "candidate.png").write_bytes(b"candidate")
    (first_task / "qa" / "hero-detail.png").write_bytes(b"detail")
    (first_task / "qa" / "hero-context.png").write_bytes(b"context")
    write_visual_qa(
        first_task,
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
    first_brief.write_text("- 状态: approved\n", encoding="utf-8")
    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product.png", "--request", "second image",
            "--image-number", "2", "--layout-keyword", "ingredient",
        ]
    )
    second_task = tmp_path / "projects" / "demo" / "images" / "02-selling-point-image"
    write_product_identity(second_task, _identity(truth_sources=("product.png",)))
    _save_geometry(second_task, "展示成分", _identity(truth_sources=("product.png",)))

    result = runner.main(
        ["write-web-handoff", "--project", "demo", "--image", "2", "--objective", "展示成分"]
    )

    handoff = (tmp_path / "projects" / "demo" / "images" / "02-selling-point-image" / "web-chatgpt-prompt.md")
    text = handoff.read_text(encoding="utf-8")
    assert result == 0
    assert "ingredient-reference.png" in text
    assert "hero-reference.png" not in text


def test_write_web_handoff_command_blocks_missing_product_identity(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product-front.png", "--request", "show detail",
        ]
    )

    result = runner.main(
        ["write-web-handoff", "--project", "demo", "--image", "1", "--objective", "展示材质细节"]
    )

    prompt_path = tmp_path / "projects" / "demo" / "images" / "01-selling-point-image" / "direct-image-prompt.md"
    assert result == 1
    assert "缺少 product-identity.md" in capsys.readouterr().out
    assert not prompt_path.exists()


def test_set_product_identity_command_writes_approved_inventory(
    tmp_path: Path, monkeypatch
) -> None:
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product-front.png", "--request", "show detail",
        ]
    )

    result = runner.main(
        [
            "set-product-identity", "--project", "demo", "--image", "1",
            "--truth-source", "product-front.png",
            "--surface-graphic", "杯身小狗图案、文字和排布逐项保持原图",
            "--physical-constraint", "球形勺柄末端由杯盖表面稳定支撑，不得水平悬空",
            "--human-interaction-constraint", "单人操作；左右手和腕部姿态必须可执行",
            "--visible-connection-evidence", "球端必须显示连接套环和连续勺杆",
            "--component", "1 个杯子", "--component", "1 把完整长勺",
            "--relationship", "球形末端连接在勺杆上",
            "--functional-feature", "杯盖边缘有供勺杆穿过的专用缺口",
            "--use-state", "合盖时勺杆穿过缺口",
            "--assembly-state-evidence",
            "合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸",
            "--visible-component-instance",
            "hero-primary-part: 端点A → 连续结构 → 连接件 → 端点B",
            "--forbid", "独立球形摆件", "--approved",
        ]
    )

    identity_path = tmp_path / "projects" / "demo" / "images" / "01-selling-point-image" / "product-identity.md"
    identity = load_product_identity(identity_path)
    assert result == 0
    assert identity.approved is True
    assert identity.truth_sources == ("product-front.png",)
    assert identity.surface_graphics == ("杯身小狗图案、文字和排布逐项保持原图",)
    assert identity.physical_constraints == ("球形勺柄末端由杯盖表面稳定支撑，不得水平悬空",)
    assert identity.human_interaction_constraints == ("单人操作；左右手和腕部姿态必须可执行",)
    assert identity.visible_connection_evidence == ("球端必须显示连接套环和连续勺杆",)
    assert identity.components == ("1 个杯子", "1 把完整长勺")
    assert identity.relationships == ("球形末端连接在勺杆上",)
    assert identity.functional_features == ("杯盖边缘有供勺杆穿过的专用缺口",)
    assert identity.required_use_states == ("合盖时勺杆穿过缺口",)
    assert identity.assembly_state_evidence == (
        "合盖使用时杯盖安装在杯口，勺杆由杯内经开放缺口向外延伸",
    )
    assert identity.visible_component_instances == (
        "hero-primary-part: 端点A → 连续结构 → 连接件 → 端点B",
    )
    assert identity.forbidden_inventions == ("独立球形摆件",)


def test_set_product_identity_command_rejects_missing_functional_semantics(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product-front.png", "--request", "show detail",
        ]
    )

    result = runner.main(
        [
            "set-product-identity", "--project", "demo", "--image", "1",
            "--truth-source", "product-front.png",
            "--surface-graphic", "无表面图案或印刷",
            "--physical-constraint", "所有物体遵循重力并由真实接触面稳定支撑",
            "--human-interaction-constraint", "无人物或手部",
            "--visible-connection-evidence", "所有固定连接必须有可见接缝",
            "--component", "1 个杯子", "--relationship", "杯盖属于杯子",
            "--forbid", "虚构部件", "--approved",
        ]
    )

    assert result == 1
    assert "functional-feature must contain" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("omitted", "message"),
    [
        ("--truth-source", "truth-source must contain"),
        ("--surface-graphic", "surface-graphic must contain"),
        ("--physical-constraint", "physical-constraint must contain"),
        ("--human-interaction-constraint", "human-interaction-constraint must contain"),
        ("--visible-connection-evidence", "visible-connection-evidence must contain"),
    ],
)
def test_set_product_identity_command_rejects_missing_source_truth_fields(
    tmp_path: Path, monkeypatch, capsys, omitted: str, message: str
) -> None:
    template = _template()
    write_template_record(tmp_path / "template-library" / "amazon" / template.template_id, template)
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    runner.main(
        [
            "prepare-image", "--project", "demo", "--platform", "amazon", "--role", "selling-point image",
            "--ratio", "1:1", "--product-reference", "product-front.png", "--request", "show detail",
        ]
    )
    fields = [
        "--truth-source", "product-front.png",
        "--surface-graphic", "无表面图案或印刷",
        "--physical-constraint", "所有物体遵循重力并由真实接触面稳定支撑",
        "--human-interaction-constraint", "单人操作；左右手和腕部姿态必须可执行",
        "--visible-connection-evidence", "球端必须显示连接套环和连续勺杆",
    ]
    remove_at = fields.index(omitted)
    del fields[remove_at:remove_at + 2]

    result = runner.main(
        [
            "set-product-identity", "--project", "demo", "--image", "1",
            *fields,
            "--component", "1 个杯子", "--relationship", "杯盖属于杯子",
            "--functional-feature", "无特殊功能结构",
            "--use-state", "按参考图保持标准状态",
            "--forbid", "虚构部件", "--approved",
        ]
    )

    assert result == 1
    assert message in capsys.readouterr().out

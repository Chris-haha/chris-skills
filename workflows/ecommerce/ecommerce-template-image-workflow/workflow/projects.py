from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Sequence

from workflow.geometry import validate_geometry_preflight
from workflow.models import DisplayCopy, ProductIdentity, TemplateRecord
from workflow.templates import template_reference_paths
from workflow.visual_qa import load_visual_qa, validate_visual_qa


class ProjectError(ValueError):
    """Raised when a project task cannot be prepared safely."""


_VISIBLE_INSTANCE_ID = re.compile(r"[a-z0-9][a-z0-9-]*\Z")


def parse_visible_component_instances(items: Sequence[str]) -> dict[str, str]:
    """Parse and validate stable IDs for every visible physical instance."""
    if not items:
        raise ProjectError("产品一致性清单的可见部件实例不能为空")
    parsed: dict[str, str] = {}
    for item in items:
        instance_id, separator, description = item.partition(":")
        instance_id = instance_id.strip()
        description = description.strip()
        if not separator:
            raise ProjectError("可见部件实例格式无效，必须使用 instance-id: description")
        if not _VISIBLE_INSTANCE_ID.fullmatch(instance_id):
            raise ProjectError(f"可见部件实例格式无效，ID 无效：{instance_id}")
        if not description:
            raise ProjectError(f"可见部件实例格式无效，描述不能为空：{instance_id}")
        if instance_id in parsed:
            raise ProjectError(f"可见部件实例 ID 重复：{instance_id}")
        parsed[instance_id] = description
    return parsed


def _is_simple_name(value: str) -> bool:
    return bool(value) and "\x00" not in value and "/" not in value and "\\" not in value and value not in {".", ".."}


def _keyword_score(value: str, keywords: Iterable[str], label: str) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    comparison = value.casefold()
    for keyword in keywords:
        normalized = keyword.strip()
        if normalized and normalized.casefold() in comparison:
            score += 5
            reasons.append(f"{label}关键词“{normalized}”匹配（+5）")
    return score, reasons


def template_score(
    record: TemplateRecord,
    platform: str,
    role: str,
    aspect_ratio: str,
    layout_keywords: Iterable[str] = (),
    safe_zone_keywords: Iterable[str] = (),
    product_position_keywords: Iterable[str] = (),
    scene_keywords: Iterable[str] = (),
) -> tuple[int, list[str]]:
    """Return a deterministic score and the human-readable reasons for it."""
    score = 0
    reasons: list[str] = []
    if record.platform == platform:
        score += 100
        reasons.append("平台完全匹配（+100）")
    if record.role == role:
        score += 50
        reasons.append("图片用途完全匹配（+50）")
    if record.aspect_ratio == aspect_ratio:
        score += 20
        reasons.append("画幅比例完全匹配（+20）")

    layout_score, layout_reasons = _keyword_score(record.layout, layout_keywords, "版式")
    safe_zone_score, safe_zone_reasons = _keyword_score(record.copy_safe_zone, safe_zone_keywords, "文案安全区")
    metadata = record.metadata
    position_score, position_reasons = _keyword_score(
        metadata.product_position if metadata else "", product_position_keywords, "产品位置"
    )
    scene_score, scene_reasons = _keyword_score(
        metadata.scene_type if metadata else "", scene_keywords, "场景类型"
    )
    return (
        score + layout_score + safe_zone_score + position_score + scene_score,
        reasons + layout_reasons + safe_zone_reasons + position_reasons + scene_reasons,
    )


def select_template(
    candidates: Sequence[TemplateRecord],
    platform: str,
    role: str,
    aspect_ratio: str,
    layout_keywords: Iterable[str] = (),
    safe_zone_keywords: Iterable[str] = (),
    template_set_id: str | None = None,
    module_id: str | None = None,
    product_position_keywords: Iterable[str] = (),
    scene_keywords: Iterable[str] = (),
) -> TemplateRecord:
    """Select the best template, allowing only the target platform or generic."""
    eligible = [record for record in candidates if record.platform in {platform, "generic"} and record.role == role]
    if template_set_id is not None:
        eligible = [record for record in eligible if record.template_set_id == template_set_id]
    if module_id is not None:
        eligible = [record for record in eligible if record.module_id == module_id]
    if not eligible:
        if template_set_id is not None or module_id is not None:
            raise ProjectError("指定的模板体系或模块没有匹配当前平台和图片用途的记录")
        raise ProjectError(f"没有匹配平台“{platform}”或通用库且用途为“{role}”的模板；请补充模板或运行 review-templates。")

    return min(
        eligible,
        key=lambda record: (
            -template_score(
                record, platform, role, aspect_ratio, layout_keywords, safe_zone_keywords,
                product_position_keywords, scene_keywords,
            )[0],
            record.platform != platform,
            record.template_id,
        ),
    )


def _validate_slug(value: str) -> str:
    candidate = Path(value)
    if not _is_simple_name(value) or candidate.name != value:
        raise ProjectError("slug 必须是单层目录名")
    return value


def _safe_role_component(role: str) -> str:
    if not _is_simple_name(role) or Path(role).name != role:
        raise ProjectError("role 必须是单层名称")
    component = re.sub(r"[^\w]+", "-", role.casefold()).strip("-")
    return component or "image"


def _validate_reference_filenames(product_references: Sequence[str]) -> list[str]:
    validated: list[str] = []
    for filename in product_references:
        path = Path(filename)
        if not _is_simple_name(filename) or path.name != filename:
            raise ProjectError("产品参考图必须使用文件名，不能包含目录路径")
        validated.append(filename)
    return validated


def _read_status(brief_path: Path) -> str | None:
    if not brief_path.exists():
        return None
    for line in brief_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- 状态:") or line.startswith("状态:"):
            return line.split(":", 1)[1].strip()
    return None


def _display_copy_section(lines: list[str], heading: str) -> list[str]:
    try:
        start = lines.index(f"## {heading}") + 1
    except ValueError as error:
        raise ProjectError(f"展示文案缺少区块：{heading}") from error
    values: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        value = line.removeprefix("- ").strip()
        if value and value != "无":
            values.append(value)
    return values


def write_display_copy(task_directory: Path, display_copy: DisplayCopy) -> Path:
    """Write approved layout text separately from protected package text."""
    task_directory.mkdir(parents=True, exist_ok=True)
    labels = "\n".join(f"- {label}" for label in display_copy.labels) or "- 无"
    evidence = "\n".join(f"- {item}" for item in display_copy.evidence) or "- 无"
    subheadline = display_copy.subheadline or "无"
    path = task_directory / "copy-brief.md"
    path.write_text(
        f"""# 详情图展示文案

- 文案语言: {display_copy.language}

## 主标题

{display_copy.headline}

## 副标题

{subheadline}

## 卖点短标签

{labels}

## 事实依据

{evidence}

## 保护规则

- 仅渲染本文件中的展示文案。
- 不重绘或生成产品包装上的 Logo、包装文字、营养成分表、条码或法规标签。
""",
        encoding="utf-8",
    )
    return path


def load_display_copy(path: Path) -> DisplayCopy:
    """Load a display-copy brief created by :func:`write_display_copy`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    language = next(
        (line.removeprefix("- 文案语言: ") for line in lines if line.startswith("- 文案语言: ")),
        None,
    )
    headline = _display_copy_section(lines, "主标题")
    subheadline = _display_copy_section(lines, "副标题")
    if not language or len(headline) != 1 or len(subheadline) > 1:
        raise ProjectError("展示文案格式无效")
    return DisplayCopy(
        language=language,
        headline=headline[0],
        subheadline=subheadline[0] if subheadline else None,
        labels=tuple(_display_copy_section(lines, "卖点短标签")),
        evidence=tuple(_display_copy_section(lines, "事实依据")),
    )


def write_product_identity(task_directory: Path, identity: ProductIdentity) -> Path:
    """Write a reviewable product inventory and relationship lock."""
    task_directory.mkdir(parents=True, exist_ok=True)
    sections = {
        "唯一事实依据": identity.truth_sources,
        "表面图案与印刷": identity.surface_graphics,
        "物理与支撑关系": identity.physical_constraints,
        "人物与动作可行性": identity.human_interaction_constraints,
        "部件与数量": identity.components,
        "部件关系": identity.relationships,
        "可见连接证据": identity.visible_connection_evidence,
        "功能结构": identity.functional_features,
        "必须呈现的使用状态": identity.required_use_states,
        "装配状态证据": identity.assembly_state_evidence,
        "可见部件实例": identity.visible_component_instances,
        "禁止出现": identity.forbidden_inventions,
        "待用户确认": identity.unknowns,
    }
    blocks: list[str] = []
    for heading, values in sections.items():
        items = "\n".join(f"- {value}" for value in values) or "- 无"
        blocks.append(f"## {heading}\n\n{items}")
    status = "approved" if identity.approved else "pending_user_confirmation"
    path = task_directory / "product-identity.md"
    path.write_text(
        f"# 产品一致性清单\n\n- 状态: {status}\n\n" + "\n\n".join(blocks) + "\n",
        encoding="utf-8",
    )
    return path


def _identity_section(lines: list[str], heading: str) -> tuple[str, ...]:
    try:
        start = lines.index(f"## {heading}") + 1
    except ValueError as error:
        raise ProjectError(f"产品一致性清单缺少区块：{heading}") from error
    values: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.startswith("- ") and line[2:] != "无":
            value = line[2:].strip()
            if value:
                values.append(value)
    return tuple(values)


def load_product_identity(path: Path) -> ProductIdentity:
    """Load and structurally validate a product identity Markdown file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    status = next(
        (line.removeprefix("- 状态: ") for line in lines if line.startswith("- 状态: ")),
        None,
    )
    if status not in {"approved", "pending_user_confirmation"}:
        raise ProjectError("产品一致性清单状态无效")
    truth_sources = _identity_section(lines, "唯一事实依据")
    surface_graphics = _identity_section(lines, "表面图案与印刷")
    physical_constraints = _identity_section(lines, "物理与支撑关系")
    human_interaction_constraints = _identity_section(lines, "人物与动作可行性")
    components = _identity_section(lines, "部件与数量")
    relationships = _identity_section(lines, "部件关系")
    visible_connection_evidence = _identity_section(lines, "可见连接证据")
    functional_features = _identity_section(lines, "功能结构")
    required_use_states = _identity_section(lines, "必须呈现的使用状态")
    assembly_state_evidence = _identity_section(lines, "装配状态证据")
    if not truth_sources:
        raise ProjectError("产品一致性清单的唯一事实依据不能为空")
    if not surface_graphics:
        raise ProjectError("产品一致性清单的表面图案与印刷不能为空")
    if not physical_constraints:
        raise ProjectError("产品一致性清单的物理与支撑关系不能为空")
    if not human_interaction_constraints:
        raise ProjectError("产品一致性清单的人物与动作可行性不能为空")
    if not components:
        raise ProjectError("产品一致性清单的部件与数量不能为空")
    if not relationships:
        raise ProjectError("产品一致性清单的部件关系不能为空")
    if not visible_connection_evidence:
        raise ProjectError("产品一致性清单的可见连接证据不能为空")
    if not functional_features:
        raise ProjectError("产品一致性清单的功能结构不能为空")
    if not required_use_states:
        raise ProjectError("产品一致性清单的必须呈现的使用状态不能为空")
    if not assembly_state_evidence:
        raise ProjectError("产品一致性清单的装配状态证据不能为空")
    visible_component_instances = _identity_section(lines, "可见部件实例")
    parse_visible_component_instances(visible_component_instances)
    forbidden = _identity_section(lines, "禁止出现")
    if not forbidden:
        raise ProjectError("产品一致性清单的禁止出现不能为空")
    return ProductIdentity(
        truth_sources=truth_sources,
        surface_graphics=surface_graphics,
        physical_constraints=physical_constraints,
        human_interaction_constraints=human_interaction_constraints,
        components=components,
        relationships=relationships,
        visible_connection_evidence=visible_connection_evidence,
        functional_features=functional_features,
        required_use_states=required_use_states,
        assembly_state_evidence=assembly_state_evidence,
        visible_component_instances=visible_component_instances,
        forbidden_inventions=forbidden,
        unknowns=_identity_section(lines, "待用户确认"),
        approved=status == "approved",
    )


def validate_product_identity(identity: ProductIdentity) -> None:
    """Block generation until every product fact is explicitly resolved."""
    if not identity.truth_sources:
        raise ProjectError("产品一致性清单的唯一事实依据不能为空")
    if not identity.surface_graphics:
        raise ProjectError("产品一致性清单的表面图案与印刷不能为空")
    if not identity.physical_constraints:
        raise ProjectError("产品一致性清单的物理与支撑关系不能为空")
    if not identity.human_interaction_constraints:
        raise ProjectError("产品一致性清单的人物与动作可行性不能为空")
    if not identity.visible_connection_evidence:
        raise ProjectError("产品一致性清单的可见连接证据不能为空")
    if not identity.functional_features:
        raise ProjectError("产品一致性清单的功能结构不能为空")
    if not identity.required_use_states:
        raise ProjectError("产品一致性清单的必须呈现的使用状态不能为空")
    if not identity.assembly_state_evidence:
        raise ProjectError("产品一致性清单的装配状态证据不能为空")
    parse_visible_component_instances(identity.visible_component_instances)
    if not identity.approved:
        raise ProjectError("产品一致性清单尚未获得用户确认，禁止生图")
    if identity.unknowns:
        questions = "；".join(identity.unknowns)
        raise ProjectError(f"产品仍有待用户确认的问题，禁止生图：{questions}")


def validate_truth_sources(
    identity: ProductIdentity, product_references: Sequence[str]
) -> None:
    """Require every truth source to be an uploaded original product reference."""
    reference_names = {Path(reference).name for reference in product_references}
    for source in identity.truth_sources:
        source_name = Path(source).name
        if source_name.casefold().startswith("generated-image"):
            raise ProjectError(f"历史生成图不能作为产品事实依据：{source}")
        if source not in product_references and source_name not in reference_names:
            raise ProjectError(f"唯一事实依据未列入当前原始产品参考图：{source}")


def _request_markdown(
    record: TemplateRecord,
    product_references: Sequence[str],
    raw_request: str,
    all_images: bool,
) -> str:
    product_lines = "\n".join(f"- {reference}" for reference in product_references) or "- 无"
    return f"""# 项目请求

- 平台: {record.platform}
- 图片用途: {record.role}
- all_images: {str(all_images).lower()}

## 产品参考图

{product_lines}

## 原始需求

{raw_request}
"""


def _selected_template_markdown(
    record: TemplateRecord,
    platform: str,
    role: str,
    aspect_ratio: str,
    layout_keywords: Iterable[str],
    safe_zone_keywords: Iterable[str],
    product_position_keywords: Iterable[str] = (),
    scene_keywords: Iterable[str] = (),
) -> str:
    score, reasons = template_score(
        record,
        platform,
        role,
        aspect_ratio,
        layout_keywords,
        safe_zone_keywords,
        product_position_keywords,
        scene_keywords,
    )
    reason_lines = "\n".join(f"- {reason}" for reason in reasons)
    set_lines = ""
    if record.template_set_id is not None:
        set_lines += f"- 模板体系 ID: {record.template_set_id}\n"
    if record.module_id is not None:
        set_lines += f"- 模块 ID: {record.module_id}\n"
    reference_lines = "\n".join(f"- {path}" for path in template_reference_paths(Path("template-library"), record)) or "- 无"
    return f"""# 已选模板

- 模板 ID: {record.template_id}
{set_lines}- 匹配得分: {score}

## 得分理由

{reason_lines}

## 模板参考图路径

{reference_lines}
"""


def _brief_markdown(record: TemplateRecord, image_number: int) -> str:
    return f"""# 图片任务

- 图片编号: {image_number:02d}
- 图片用途: {record.role}
- 状态: pending_user_route
"""


def write_web_handoff(
    task_directory: Path,
    direct_prompt: str,
    template: TemplateRecord,
    product_references: Sequence[str],
    display_copy: DisplayCopy | None = None,
    product_identity: ProductIdentity | None = None,
    geometry_preflight: dict[str, Any] | None = None,
) -> Path:
    """Write the self-contained handoff packet for the web ChatGPT channel."""
    if product_identity is None:
        raise ProjectError("缺少产品一致性清单，禁止创建生图交接包")
    validate_product_identity(product_identity)
    validate_truth_sources(product_identity, product_references)
    objective = geometry_preflight.get("objective", "") if isinstance(geometry_preflight, dict) else ""
    validate_geometry_preflight(geometry_preflight, product_identity, objective)
    # Import here because prompt_builder also uses the product-identity validators.
    from workflow.prompt_builder import build_direct_image_prompt

    expected = build_direct_image_prompt(
        template, product_references, objective, display_copy, product_identity, geometry_preflight,
    )
    if direct_prompt.rstrip("\n") != expected:
        raise ProjectError("直接生图提示词与当前几何预检不一致，请重新创建提示词")
    task_directory.mkdir(parents=True, exist_ok=True)
    product_lines = "\n".join(f"- {reference}" for reference in product_references) or "- 无"
    template_lines = "\n".join(
        f"- {path}" for path in template_reference_paths(Path("template-library"), template)
    ) or "- 无"
    review_section = ""
    if display_copy is not None:
        review_section = """\n## 展示文案检查

- 检查主标题、副标题和每个卖点短标签是否逐字正确、完整且清晰可读。
- 任何文字遗漏、错字或乱码都应只重做当前图片，不能进入下一张。
- 不检查或修改产品包装上的 Logo、包装文字、营养成分表、条码或法规标签。
"""
    identity_review = f"""
## 产品一致性检查

- 只以这些原始产品图为产品事实依据：{'；'.join(product_identity.truth_sources)}
- 逐项核对表面图案与印刷，包括元素、文字、数量、顺序、位置、朝向、比例与线条：{'；'.join(product_identity.surface_graphics)}
- 逐项核对物理与支撑关系，包括重力、支撑点、接触关系和稳定静置姿态：{'；'.join(product_identity.physical_constraints)}
- 逐项核对人物与动作可行性，包括人数、左右手职责、进场方向、握持点、关节姿态和动作时序：{'；'.join(product_identity.human_interaction_constraints)}
- 逐项核对部件数量：{'；'.join(product_identity.components)}
- 逐项核对连接关系：{'；'.join(product_identity.relationships)}
- 逐项核对可见连接证据，包括端点、连接件、连续段、遮挡入口与出口、所属主体：{'；'.join(product_identity.visible_connection_evidence)}
- 逐项核对功能结构及其位置：{'；'.join(product_identity.functional_features)}
- 逐项核对使用状态与部件交互：{'；'.join(product_identity.required_use_states)}
- 逐项追踪装配状态证据，包括场景状态、承载主体、功能结构、交互部件路径、支撑来源和遮挡一致性：{'；'.join(product_identity.assembly_state_evidence)}
- 逐个独立核对可见部件实例，其他实例正确不能抵消任一实例失败：{'；'.join(product_identity.visible_component_instances)}
- 每个已登记的可见部件实例必须独立通过 topology（拓扑连续与归属）、support（真实支撑）、clearance（路径净空）、assembly（真实装配）和 framing（画框填充与安全裁切）五个维度；任一维度失败即整图失败。
- framing 必须证明产品画面填满预定媒体框，没有意外露出的占位底色、上下/左右空白带或拉伸变形；裁切不得切断需要展示的主体、部件或关键图案。不能同时满足填满与主体完整时，必须先调整画框比例或版式，不能用留白遮掩比例冲突。
- 对每个实例建立完整路径与占用空间：先追踪端点、连续段和连接件，再标记允许接触面与沿途禁止相交实体。整条路径必须保持可见净空，不得与其他固体重叠、裁切、穿透或用相切伪装连接。遮挡只有在入口、出口、方向和前后层级一致时才成立；无法区分正常遮挡与实体穿透时直接判定失败。必须调整机位或路径来证明净空，装饰性构图不能覆盖物理可行性。
- 确认未出现：{'；'.join(product_identity.forbidden_inventions)}
- 任何近似、增删、替换、重排、风格化改写、无支撑悬空、违反重力、实体穿透、不稳定摆放、镜像手、重复手、同侧手、错接手腕、反关节、不可能抓握、操作者数量不符、动作时序冲突、连接链中断、端点消失、连接件缺失、遮挡边界方向矛盾、部件归属不明、混合互斥装配状态、功能主体未安装、交互路径错误、开放结构被画成封闭孔洞或桥状假结构都判定失败；保留失败图并只重做当前图片，不得批准或继续下一张。
"""
    path = task_directory / "web-chatgpt-prompt.md"
    path.write_text(
        f"""# 网页 ChatGPT 生图交接包

## 最终生图指令

{direct_prompt}

## 必须上传的产品图

{product_lines}

## 必须上传的模板图

{template_lines}

- 图片类型: {template.role}
- 图片比例: {template.aspect_ratio}
- 生成规则: 每次仅生成当前一张，确认后再继续下一张。
{review_section}
{identity_review}
""",
        encoding="utf-8",
    )
    return path


def prepare_image_task(
    workflow_root: Path,
    slug: str,
    selected: TemplateRecord,
    product_references: Sequence[str],
    raw_request: str,
    image_number: int,
    all_images: bool,
    match_platform: str | None = None,
    match_role: str | None = None,
    match_aspect_ratio: str | None = None,
    layout_keywords: Iterable[str] = (),
    safe_zone_keywords: Iterable[str] = (),
    product_position_keywords: Iterable[str] = (),
    scene_keywords: Iterable[str] = (),
) -> Path:
    """Prepare one image task without overwriting an existing image task."""
    if image_number < 1:
        raise ProjectError("图片编号必须从 1 开始")

    safe_slug = _validate_slug(slug)
    safe_role = _safe_role_component(selected.role)
    references = _validate_reference_filenames(product_references)
    project_dir = workflow_root / "projects" / safe_slug
    images_dir = project_dir / "images"
    task_dir = images_dir / f"{image_number:02d}-{safe_role}"
    existing_tasks = sorted(images_dir.glob(f"{image_number:02d}-*")) if images_dir.exists() else []
    if existing_tasks:
        raise ProjectError(f"图片任务目录 already exists: {existing_tasks[0]}")

    if image_number > 1 and not all_images:
        previous_briefs = sorted(images_dir.glob(f"{image_number - 1:02d}-*/brief.md")) if images_dir.exists() else []
        if len(previous_briefs) != 1 or _read_status(previous_briefs[0]) != "approved":
            raise ProjectError("上一张图片必须为 approved 后才能准备下一张")
        previous_task = previous_briefs[0].parent
        try:
            identity = load_product_identity(previous_task / "product-identity.md")
            required_instances = parse_visible_component_instances(
                identity.visible_component_instances
            )
            report = load_visual_qa(previous_task / "visual-qa.md")
            validate_visual_qa(
                previous_task,
                report,
                required_instances,
                report.candidate,
                require_pass=True,
            )
        except (OSError, ValueError) as error:
            raise ProjectError("上一张图片缺少通过的逐实例视觉质检") from error

    project_dir.mkdir(parents=True, exist_ok=True)
    request_path = project_dir / "request.md"
    selected_path = project_dir / "selected-template.md"
    if not request_path.exists():
        request_path.write_text(_request_markdown(selected, references, raw_request, all_images), encoding="utf-8")
    if not selected_path.exists():
        selected_path.write_text(
            _selected_template_markdown(
                selected,
                match_platform if match_platform is not None else selected.platform,
                match_role if match_role is not None else selected.role,
                match_aspect_ratio if match_aspect_ratio is not None else selected.aspect_ratio,
                layout_keywords,
                safe_zone_keywords,
                product_position_keywords,
                scene_keywords,
            ),
            encoding="utf-8",
        )

    task_dir.mkdir(parents=True)
    (task_dir / "selected-template.md").write_text(
        _selected_template_markdown(
            selected,
            match_platform if match_platform is not None else selected.platform,
            match_role if match_role is not None else selected.role,
            match_aspect_ratio if match_aspect_ratio is not None else selected.aspect_ratio,
            layout_keywords,
            safe_zone_keywords,
            product_position_keywords,
            scene_keywords,
        ),
        encoding="utf-8",
    )
    (task_dir / "brief.md").write_text(_brief_markdown(selected, image_number), encoding="utf-8")
    return task_dir

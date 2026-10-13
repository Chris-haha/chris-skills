from __future__ import annotations

import math
import shutil
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from PIL import Image, UnidentifiedImageError

from workflow.models import InboxSet, ModuleDraft, TemplateMetadata, TemplateSetDraft


class InboxError(ValueError):
    """Raised when an uploaded template set cannot be stored safely."""


def _safe_component(value: str, field: str) -> str:
    path = Path(value)
    if not value or path.name != value or value in {".", ".."}:
        raise InboxError(f"{field} must be a simple directory name")
    return value


def _validate_image(path: Path) -> None:
    if not path.is_file():
        raise InboxError(f"source image is missing: {path}")
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, UnidentifiedImageError) as error:
        raise InboxError(f"source image is unreadable: {path}") from error


def _write_manifest(directory: Path, inbox_set: InboxSet) -> None:
    sources = "\n".join(f"- {name}" for name in inbox_set.sources)
    (directory / "manifest.md").write_text(
        f"""# 模板收件箱清单

- 批次 ID: {inbox_set.batch_id}
- 套组 ID: {inbox_set.set_id}
- 平台: {inbox_set.platform}

## 源文件

{sources}
""",
        encoding="utf-8",
    )


def _write_contact_sheet(directory: Path, source_names: Sequence[str]) -> Path:
    thumbnail_size = (240, 180)
    padding = 16
    columns = min(4, len(source_names))
    rows = math.ceil(len(source_names) / columns)
    canvas = Image.new(
        "RGB",
        (columns * thumbnail_size[0] + (columns + 1) * padding, rows * thumbnail_size[1] + (rows + 1) * padding),
        "white",
    )
    for index, source_name in enumerate(source_names):
        with Image.open(directory / source_name) as opened:
            image = opened.convert("RGB")
        image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        column = index % columns
        row = index // columns
        x = padding + column * (thumbnail_size[0] + padding) + (thumbnail_size[0] - image.width) // 2
        y = padding + row * (thumbnail_size[1] + padding) + (thumbnail_size[1] - image.height) // 2
        canvas.paste(image, (x, y))
    path = directory / "contact-sheet.webp"
    canvas.save(path, "WEBP")
    return path


def import_template_set(
    workflow_root: Path,
    batch_id: str,
    set_id: str,
    sources: Sequence[Path],
    platform: str = "generic",
) -> Path:
    """Copy one user-uploaded set into an isolated, stable local inbox directory."""
    safe_batch = _safe_component(batch_id, "batch")
    safe_set = _safe_component(set_id, "set")
    safe_platform = _safe_component(platform, "platform")
    if not sources:
        raise InboxError("at least one source image is required")
    for source in sources:
        _validate_image(source)

    directory = workflow_root / "template-inbox" / safe_batch / safe_set
    if directory.exists():
        raise InboxError(f"template inbox set already exists: {directory}")
    directory.mkdir(parents=True)
    copied: list[str] = []
    try:
        for index, source in enumerate(sources, 1):
            suffix = source.suffix.lower()
            if not suffix:
                raise InboxError(f"source image has no extension: {source}")
            name = f"source-{index:02d}{suffix}"
            shutil.copy2(source, directory / name)
            copied.append(name)
        _write_manifest(directory, InboxSet(safe_batch, safe_set, safe_platform, tuple(copied)))
        _write_contact_sheet(directory, copied)
    except Exception:
        shutil.rmtree(directory)
        raise
    return directory


def _metadata_from_dict(value: dict[str, object]) -> TemplateMetadata:
    return TemplateMetadata(
        role=str(value["role"]),
        aspect_ratio=str(value["aspect_ratio"]),
        output_size=str(value["output_size"]),
        layout=str(value["layout"]),
        copy_safe_zone=str(value["copy_safe_zone"]),
        style=str(value["style"]),
        scene=str(value["scene"]),
        suitable_for=tuple(str(item) for item in value["suitable_for"]),
        avoid_for=tuple(str(item) for item in value["avoid_for"]),
        product_position=str(value["product_position"]),
        copy_density=str(value["copy_density"]),
        card_count=int(value["card_count"]),
        scene_type=str(value["scene_type"]),
        non_transferable_elements=tuple(str(item) for item in value["non_transferable_elements"]),
    )


def _draft_from_dict(value: dict[str, object]) -> TemplateSetDraft:
    try:
        modules = tuple(
            ModuleDraft(
                module_id=str(module["module_id"]),
                source_images=tuple(str(item) for item in module["source_images"]),
                metadata=_metadata_from_dict(module["metadata"]),
            )
            for module in value["modules"]
        )
        suggestions = tuple(tuple(str(item) for item in pair) for pair in value.get("merge_suggestions", []))
        if any(len(pair) != 2 for pair in suggestions):
            raise ValueError("merge suggestion must contain two module IDs")
        return TemplateSetDraft(
            template_set_id=str(value["template_set_id"]),
            platform=str(value["platform"]),
            modules=modules,
            overall_style=str(value.get("overall_style", "")),
            merge_suggestions=suggestions,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise InboxError("analysis draft has an invalid format") from error


def _validate_draft(inbox_directory: Path, draft: TemplateSetDraft) -> None:
    _safe_component(draft.template_set_id, "template-set")
    _safe_component(draft.platform, "platform")
    if not draft.modules:
        raise InboxError("analysis draft must contain at least one module")
    source_names = {path.name for path in inbox_directory.glob("source-*.*")}
    assigned_sources: set[str] = set()
    module_ids: set[str] = set()
    for module in draft.modules:
        _safe_component(module.module_id, "module-id")
        if module.module_id in module_ids:
            raise InboxError(f"analysis draft has duplicate module ID: {module.module_id}")
        module_ids.add(module.module_id)
        if not module.source_images:
            raise InboxError(f"analysis draft module has no source images: {module.module_id}")
        for source_name in module.source_images:
            if source_name not in source_names:
                raise InboxError(f"draft source does not belong to inbox set: {source_name}")
            if source_name in assigned_sources:
                raise InboxError(f"draft source is used by more than one module: {source_name}")
            assigned_sources.add(source_name)
        if module.metadata.card_count < 0:
            raise InboxError("card_count must not be negative")
    if assigned_sources != source_names:
        raise InboxError("analysis draft must classify every source in the inbox set")
    for first, second in draft.merge_suggestions:
        if first not in module_ids or second not in module_ids or first == second:
            raise InboxError("merge suggestion must name two different known modules")


def _draft_markdown(draft: TemplateSetDraft) -> str:
    modules: list[str] = []
    for module in draft.modules:
        metadata = module.metadata
        sources = ", ".join(module.source_images)
        non_transferable = "；".join(metadata.non_transferable_elements) or "无"
        modules.append(
            f"""### {module.module_id}

- 候选源图: {sources}
- 图片用途: {metadata.role}
- 比例: {metadata.aspect_ratio}
- 产品位置: {metadata.product_position}
- 文案安全区: {metadata.copy_safe_zone}
- 图文密度: {metadata.copy_density}
- 卡片数量: {metadata.card_count}
- 视觉风格: {metadata.style}
- 场景类型: {metadata.scene_type}
- 不可照搬元素: {non_transferable}
"""
        )
    suggestions = "\n".join(f"- 需用户确认合并: {first} + {second}" for first, second in draft.merge_suggestions) or "- 无"
    return f"""# 模板套组分析草稿

- 候选模板体系 ID: {draft.template_set_id}
- 平台: {draft.platform}
- 整体风格: {draft.overall_style or "未填写"}

## 候选模块

{'\n'.join(modules)}
## 组内合并建议

{suggestions}

## 审核规则

- 每张源图在确认前保持独立候选模块。
- 仅限本套组提出合并建议；合并必须由用户确认后才能归档。
- 不会跨套组移动、合并或借用参考图。
"""


def write_analysis_draft(inbox_directory: Path, draft: TemplateSetDraft) -> Path:
    """Store a validated machine draft and its human-readable review summary."""
    _validate_draft(inbox_directory, draft)
    (inbox_directory / "analysis-draft.json").write_text(
        json.dumps(asdict(draft), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    path = inbox_directory / "analysis-draft.md"
    path.write_text(_draft_markdown(draft), encoding="utf-8")
    return path


def load_analysis_draft(inbox_directory: Path) -> TemplateSetDraft:
    """Load and validate a previously written set-local analysis draft."""
    path = inbox_directory / "analysis-draft.json"
    if not path.is_file():
        raise InboxError(f"analysis draft is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InboxError("analysis draft is invalid JSON") from error
    if not isinstance(value, dict):
        raise InboxError("analysis draft must be a JSON object")
    draft = _draft_from_dict(value)
    _validate_draft(inbox_directory, draft)
    return draft

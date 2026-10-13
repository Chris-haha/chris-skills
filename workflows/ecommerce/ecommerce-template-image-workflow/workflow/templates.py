from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from workflow.models import TemplateMetadata, TemplateRecord


def _list_lines(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) or "- 无"


def _reference_lines(values: list[str]) -> str:
    return "\n".join(f"- 参考图: {value}" for value in values) or "- 参考图: 无"


def write_template_record(directory: Path, record: TemplateRecord) -> Path:
    """Write one template's classification record without touching reference images."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "template.md"
    hierarchy = ""
    if record.template_set_id is not None:
        hierarchy += f"- 模板体系 ID: {record.template_set_id}\n"
    if record.module_id is not None:
        hierarchy += f"- 模块 ID: {record.module_id}\n"
    content = f"""# 模板记录

- 模板 ID: {record.template_id}
{hierarchy}- 平台: {record.platform}
- 图片用途: {record.role}
- 比例: {record.aspect_ratio}
- 建议尺寸: {record.output_size}
- 版式: {record.layout}
- 文案安全区: {record.copy_safe_zone}
- 风格: {record.style}
- 场景: {record.scene}

## 适用条件

{_list_lines(record.suitable_for)}

## 不适用条件

{_list_lines(record.avoid_for)}

## 参考图

{_reference_lines(record.references)}
"""
    path.write_text(content, encoding="utf-8")
    return path


def write_template_annotations(directory: Path, metadata: TemplateMetadata) -> Path:
    """Write structured tags without changing the human-readable template record."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "annotations.json"
    path.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_template_annotations(directory: Path) -> TemplateMetadata | None:
    """Return optional structured tags; legacy templates do not have this file."""
    path = directory / "annotations.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
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
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"template annotations are invalid: {path}") from error


def _scalar_values(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        if line.startswith("## "):
            break
        if line.startswith("- ") and ": " in line:
            key, value = line[2:].split(": ", 1)
            values[key] = value
    return values


def _section_list(lines: list[str], heading: str, reference_prefix: str = "") -> list[str]:
    try:
        start = lines.index(f"## {heading}") + 1
    except ValueError as error:
        raise ValueError(f"template record is missing section: {heading}") from error
    values: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.startswith("- "):
            value = line[2:]
            if reference_prefix and value.startswith(reference_prefix):
                value = value[len(reference_prefix) :]
            if value == "无":
                continue
            values.append(value)
    return values


def load_template_record(directory: Path) -> TemplateRecord:
    """Read a template record written by :func:`write_template_record`."""
    path = directory / "template.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    values = _scalar_values(lines)
    required = {
        "模板 ID": "template_id",
        "平台": "platform",
        "图片用途": "role",
        "比例": "aspect_ratio",
        "建议尺寸": "output_size",
        "版式": "layout",
        "文案安全区": "copy_safe_zone",
        "风格": "style",
        "场景": "scene",
    }
    missing = [label for label in required if label not in values]
    if missing:
        raise ValueError(f"template record is missing fields: {', '.join(missing)}")
    return TemplateRecord(
        template_id=values["模板 ID"],
        platform=values["平台"],
        role=values["图片用途"],
        aspect_ratio=values["比例"],
        output_size=values["建议尺寸"],
        layout=values["版式"],
        copy_safe_zone=values["文案安全区"],
        style=values["风格"],
        scene=values["场景"],
        suitable_for=_section_list(lines, "适用条件"),
        avoid_for=_section_list(lines, "不适用条件"),
        references=_section_list(lines, "参考图", "参考图: "),
        template_set_id=values.get("模板体系 ID"),
        module_id=values.get("模块 ID"),
        metadata=load_template_annotations(directory),
    )


def discover_template_records(library_root: Path) -> list[TemplateRecord]:
    """Return every registered template below a template-library directory."""
    paths = set(library_root.glob("*/*/template.md"))
    paths.update(library_root.glob("*/**/modules/*/template.md"))
    return [load_template_record(path.parent) for path in sorted(paths)]


def template_storage_directory(library_root: Path, record: TemplateRecord) -> Path:
    """Return the directory that owns a template's reference files."""
    if record.template_set_id is not None and record.module_id is not None:
        return library_root / record.platform / record.template_set_id / "modules" / record.module_id
    return library_root / record.platform / record.template_id


def template_reference_paths(library_root: Path, record: TemplateRecord) -> list[Path]:
    """Return paths for a template's references without changing those files."""
    directory = template_storage_directory(library_root, record)
    return [directory / reference for reference in record.references]

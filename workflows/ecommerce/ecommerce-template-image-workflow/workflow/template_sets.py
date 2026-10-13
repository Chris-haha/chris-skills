from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from workflow.inbox import InboxError, load_analysis_draft
from workflow.models import ModuleDraft, TemplateSetDraft
from workflow.templates import write_template_annotations, write_template_record
from workflow.models import TemplateRecord


class TemplateSetError(ValueError):
    """Raised when a reviewed template set cannot be archived safely."""


def _template_set_markdown(draft: TemplateSetDraft) -> str:
    modules = "\n".join(f"- {module.module_id}" for module in draft.modules)
    return f"""# 模板体系

- 模板体系 ID: {draft.template_set_id}
- 平台: {draft.platform}
- 整体风格: {draft.overall_style or "未填写"}

## 模块

{modules}
"""


def _write_module(directory: Path, inbox_directory: Path, draft: TemplateSetDraft, module: ModuleDraft) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    references: list[str] = []
    for index, source_name in enumerate(module.source_images, 1):
        source = inbox_directory / source_name
        if not source.is_file():
            raise TemplateSetError(f"draft source is missing from inbox set: {source_name}")
        reference_name = f"reference-{index:02d}{source.suffix.lower()}"
        shutil.copy2(source, directory / reference_name)
        references.append(reference_name)
    metadata = module.metadata
    write_template_record(
        directory,
        TemplateRecord(
            template_id=f"{draft.template_set_id}--{module.module_id}",
            platform=draft.platform,
            role=metadata.role,
            aspect_ratio=metadata.aspect_ratio,
            output_size=metadata.output_size,
            layout=metadata.layout,
            copy_safe_zone=metadata.copy_safe_zone,
            style=metadata.style,
            scene=metadata.scene,
            suitable_for=list(metadata.suitable_for),
            avoid_for=list(metadata.avoid_for),
            references=references,
            template_set_id=draft.template_set_id,
            module_id=module.module_id,
            metadata=metadata,
        ),
    )
    write_template_annotations(directory, metadata)


def _write_revision(directory: Path, revision: int, draft: TemplateSetDraft) -> Path:
    revisions = directory / "revisions"
    revisions.mkdir(parents=True, exist_ok=True)
    path = revisions / f"{revision:03d}.json"
    path.write_text(json.dumps(asdict(draft), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_set(directory: Path, inbox_directory: Path, draft: TemplateSetDraft) -> None:
    (directory / "modules").mkdir(parents=True, exist_ok=True)
    (directory / "template-set.md").write_text(_template_set_markdown(draft), encoding="utf-8")
    for module in draft.modules:
        _write_module(directory / "modules" / module.module_id, inbox_directory, draft, module)


def approve_template_set(workflow_root: Path, inbox_directory: Path) -> Path:
    """Archive one validated inbox draft without reading or mixing another set."""
    try:
        draft = load_analysis_draft(inbox_directory)
    except InboxError as error:
        raise TemplateSetError(str(error)) from error
    destination = workflow_root / "template-library" / draft.platform / draft.template_set_id
    staging = destination.with_name(f".{destination.name}.staging")
    if destination.exists():
        raise TemplateSetError("template set already exists; create a revision instead")
    if staging.exists():
        raise TemplateSetError(f"template set staging directory already exists: {staging}")
    staging.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write_set(staging, inbox_directory, draft)
        _write_revision(staging, 1, draft)
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def _next_revision(directory: Path) -> int:
    revisions = [int(path.stem) for path in (directory / "revisions").glob("*.json") if path.stem.isdigit()]
    return max(revisions, default=0) + 1


def revise_template_set(
    workflow_root: Path, platform: str, template_set_id: str, inbox_directory: Path
) -> Path:
    """Replace one approved set from a new set-local draft and save a new revision."""
    destination = workflow_root / "template-library" / platform / template_set_id
    if not destination.is_dir():
        raise TemplateSetError(f"template set does not exist: {template_set_id}")
    try:
        draft = load_analysis_draft(inbox_directory)
    except InboxError as error:
        raise TemplateSetError(str(error)) from error
    if draft.platform != platform or draft.template_set_id != template_set_id:
        raise TemplateSetError("revision draft does not match target template set")
    revision = _next_revision(destination)
    staging = destination.with_name(f".{destination.name}.revision-{revision}.staging")
    if staging.exists():
        raise TemplateSetError(f"revision staging directory already exists: {staging}")
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    try:
        for path in destination.iterdir():
            if path.name == "revisions":
                continue
            if path.name not in {"template-set.md", "modules"}:
                continue
            if path.is_dir():
                shutil.copytree(path, staging / path.name, dirs_exist_ok=True)
            else:
                shutil.copy2(path, staging / path.name)
        existing_revisions = destination / "revisions"
        shutil.copytree(existing_revisions, staging / "revisions", dirs_exist_ok=True)
        _write_set(staging, inbox_directory, draft)
        _write_revision(staging, revision, draft)
        backup = destination.with_name(f".{destination.name}.backup-{revision}")
        destination.replace(backup)
        staging.replace(destination)
        shutil.rmtree(backup)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def rollback_template_set(workflow_root: Path, platform: str, template_set_id: str, revision: int) -> Path:
    """Restore one set's approved metadata while retiring modules absent from the snapshot."""
    destination = workflow_root / "template-library" / platform / template_set_id
    if not destination.is_dir():
        raise TemplateSetError(f"template set does not exist: {template_set_id}")
    revision_path = destination / "revisions" / f"{revision:03d}.json"
    if not revision_path.is_file():
        raise TemplateSetError(f"template set revision does not exist: {revision}")
    try:
        value = json.loads(revision_path.read_text(encoding="utf-8"))
        from workflow.inbox import _draft_from_dict

        draft = _draft_from_dict(value)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise TemplateSetError(f"template set revision is invalid: {revision}") from error
    if draft.platform != platform or draft.template_set_id != template_set_id:
        raise TemplateSetError("revision does not match target template set")

    current_modules = destination / "modules"
    target_module_ids = {module.module_id for module in draft.modules}
    retired_root = destination / "retired" / f"{max(1, _next_revision(destination) - 1):03d}"
    for module_dir in current_modules.iterdir():
        if module_dir.is_dir() and module_dir.name not in target_module_ids:
            retired_root.mkdir(parents=True, exist_ok=True)
            shutil.move(str(module_dir), str(retired_root / module_dir.name))
    for module in draft.modules:
        module_dir = current_modules / module.module_id
        if not module_dir.is_dir():
            raise TemplateSetError(f"target revision module is not available: {module.module_id}")
        references = sorted(
            path.name for path in module_dir.glob("reference-*.*") if path.is_file()
        )
        metadata = module.metadata
        write_template_record(
            module_dir,
            TemplateRecord(
                template_id=f"{draft.template_set_id}--{module.module_id}",
                platform=draft.platform,
                role=metadata.role,
                aspect_ratio=metadata.aspect_ratio,
                output_size=metadata.output_size,
                layout=metadata.layout,
                copy_safe_zone=metadata.copy_safe_zone,
                style=metadata.style,
                scene=metadata.scene,
                suitable_for=list(metadata.suitable_for),
                avoid_for=list(metadata.avoid_for),
                references=references,
                template_set_id=draft.template_set_id,
                module_id=module.module_id,
                metadata=metadata,
            ),
        )
        write_template_annotations(module_dir, metadata)
    (destination / "template-set.md").write_text(_template_set_markdown(draft), encoding="utf-8")
    return destination

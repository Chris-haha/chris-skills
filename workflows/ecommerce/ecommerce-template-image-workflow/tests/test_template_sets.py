import json
from pathlib import Path

from PIL import Image

from workflow.inbox import import_template_set, write_analysis_draft
from workflow.models import ModuleDraft, TemplateMetadata, TemplateSetDraft
from workflow.template_sets import (
    TemplateSetError,
    approve_template_set,
    revise_template_set,
    rollback_template_set,
)


def _image(path: Path, color: str) -> Path:
    Image.new("RGB", (24, 16), color).save(path)
    return path


def _metadata() -> TemplateMetadata:
    return TemplateMetadata(
        role="详情页横幅图",
        aspect_ratio="3:2",
        output_size="1500x1000",
        layout="product right, title left",
        copy_safe_zone="left 40%",
        style="clean editorial",
        scene="bright studio",
        suitable_for=("packaged products",),
        avoid_for=(),
        product_position="right",
        copy_density="medium",
        card_count=1,
        scene_type="studio",
        non_transferable_elements=("reference brand copy",),
    )


def _drafted_set(root: Path, set_id: str, source: Path, template_set_id: str) -> Path:
    inbox = import_template_set(root, "batch-001", set_id, [source], "amazon")
    write_analysis_draft(
        inbox,
        TemplateSetDraft(
            template_set_id=template_set_id,
            platform="amazon",
            modules=(ModuleDraft("feature-hero", ("source-01.png",), _metadata()),),
            overall_style="clean editorial",
        ),
    )
    return inbox


def test_approve_template_set_copies_only_its_sources_and_writes_annotations(tmp_path: Path) -> None:
    first = _drafted_set(
        tmp_path, "set-001", _image(tmp_path / "first.png", "red"), "clean-editorial-01"
    )
    _drafted_set(tmp_path, "set-002", _image(tmp_path / "second.png", "blue"), "other-editorial-01")

    directory = approve_template_set(tmp_path, first)

    module = directory / "modules" / "feature-hero"
    assert (module / "reference-01.png").is_file()
    assert not any("set-002" in str(path) for path in directory.rglob("*"))
    annotations = json.loads((module / "annotations.json").read_text(encoding="utf-8"))
    assert annotations["card_count"] == 1
    assert (directory / "revisions" / "001.json").is_file()


def test_rollback_restores_prior_metadata_without_touching_another_set(tmp_path: Path) -> None:
    first = _drafted_set(
        tmp_path, "set-001", _image(tmp_path / "first.png", "red"), "clean-editorial-01"
    )
    other = _drafted_set(tmp_path, "set-002", _image(tmp_path / "second.png", "blue"), "other-editorial-01")
    directory = approve_template_set(tmp_path, first)
    approve_template_set(tmp_path, other)

    revised_metadata = TemplateMetadata(
        role="详情页横幅图", aspect_ratio="3:2", output_size="1500x1000",
        layout="product center, title top", copy_safe_zone="top 30%", style="revised editorial",
        scene="dark studio", suitable_for=("packaged products",), avoid_for=(), product_position="center",
        copy_density="high", card_count=2, scene_type="studio", non_transferable_elements=("new copy",),
    )
    revised = TemplateSetDraft(
        template_set_id="clean-editorial-01",
        platform="amazon",
        modules=(ModuleDraft("feature-hero-renamed", ("source-01.png",), revised_metadata),),
        overall_style="revised editorial",
    )
    revised_inbox = import_template_set(
        tmp_path, "batch-002", "set-001", [_image(tmp_path / "replacement.png", "green")], "amazon"
    )
    write_analysis_draft(revised_inbox, revised)
    revise_template_set(tmp_path, "amazon", "clean-editorial-01", revised_inbox)

    rollback_template_set(tmp_path, "amazon", "clean-editorial-01", 1)

    assert "clean-editorial-01" in (directory / "template-set.md").read_text(encoding="utf-8")
    assert (directory / "modules" / "feature-hero" / "template.md").is_file()
    assert "revised editorial" not in (directory / "modules" / "feature-hero" / "template.md").read_text(encoding="utf-8")
    assert json.loads((directory / "modules" / "feature-hero" / "annotations.json").read_text(encoding="utf-8"))["style"] == "clean editorial"
    assert not (directory / "modules" / "feature-hero-renamed" / "template.md").exists()
    assert (directory / "retired" / "002" / "feature-hero-renamed").is_dir()
    assert (tmp_path / "template-library" / "amazon" / "other-editorial-01").exists()


def test_approve_template_set_keeps_inbox_sources_after_archive(tmp_path: Path) -> None:
    inbox = _drafted_set(
        tmp_path, "set-001", _image(tmp_path / "first.png", "red"), "clean-editorial-01"
    )

    approve_template_set(tmp_path, inbox)

    assert (inbox / "source-01.png").is_file()
    assert (inbox / "analysis-draft.json").is_file()

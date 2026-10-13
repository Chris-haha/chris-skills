from pathlib import Path

import pytest
from PIL import Image

from workflow.inbox import InboxError, import_template_set, load_analysis_draft, write_analysis_draft
from workflow.models import ModuleDraft, TemplateMetadata, TemplateSetDraft
from workflow import runner


def _image(path: Path, color: str) -> Path:
    Image.new("RGB", (24, 16), color).save(path)
    return path


def test_import_template_set_copies_any_number_of_sources_in_order(tmp_path: Path) -> None:
    sources = [
        _image(tmp_path / "first.png", "red"),
        _image(tmp_path / "second.png", "green"),
        _image(tmp_path / "third.png", "blue"),
    ]

    directory = import_template_set(tmp_path, "batch-001", "set-001", sources, "amazon")

    assert [path.name for path in sorted(directory.glob("source-*"))] == [
        "source-01.png",
        "source-02.png",
        "source-03.png",
    ]
    manifest = (directory / "manifest.md").read_text(encoding="utf-8")
    assert "- 批次 ID: batch-001" in manifest
    assert "- 套组 ID: set-001" in manifest
    assert "source-01.png" in manifest
    assert (directory / "contact-sheet.webp").is_file()


def test_import_template_set_refuses_to_overwrite_an_existing_set(tmp_path: Path) -> None:
    source = _image(tmp_path / "first.png", "red")
    import_template_set(tmp_path, "batch-001", "set-001", [source], "generic")

    with pytest.raises(InboxError, match="already exists"):
        import_template_set(tmp_path, "batch-001", "set-001", [source], "generic")


def _metadata(role: str) -> TemplateMetadata:
    return TemplateMetadata(
        role=role,
        aspect_ratio="1:1",
        output_size="1200x1200",
        layout="product on right",
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


def test_analysis_draft_keeps_each_source_as_a_separate_candidate(tmp_path: Path) -> None:
    directory = import_template_set(
        tmp_path,
        "batch-001",
        "set-001",
        [_image(tmp_path / "first.png", "red"), _image(tmp_path / "second.png", "blue")],
        "amazon",
    )
    draft = TemplateSetDraft(
        template_set_id="clean-editorial-01",
        platform="amazon",
        modules=(
            ModuleDraft("feature-hero", ("source-01.png",), _metadata("hero")),
            ModuleDraft("comparison-proof", ("source-02.png",), _metadata("comparison")),
        ),
        overall_style="clean editorial",
    )

    path = write_analysis_draft(directory, draft)

    assert path.name == "analysis-draft.md"
    assert "feature-hero" in path.read_text(encoding="utf-8")
    assert load_analysis_draft(directory) == draft


def test_analysis_draft_rejects_source_from_another_set(tmp_path: Path) -> None:
    directory = import_template_set(
        tmp_path, "batch-001", "set-001", [_image(tmp_path / "first.png", "red")], "amazon"
    )
    draft = TemplateSetDraft(
        template_set_id="clean-editorial-01",
        platform="amazon",
        modules=(ModuleDraft("feature-hero", ("source-99.png",), _metadata("hero")),),
    )

    with pytest.raises(InboxError, match="does not belong to inbox set"):
        write_analysis_draft(directory, draft)


def test_runner_imports_two_sets_without_crossing_directories(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    first = _image(tmp_path / "first.png", "red")
    second = _image(tmp_path / "second.png", "blue")

    assert runner.main(["import-template-set", "--batch", "batch-001", "--set", "set-001", "--source", str(first)]) == 0
    assert runner.main(["import-template-set", "--batch", "batch-001", "--set", "set-002", "--source", str(second)]) == 0

    assert (tmp_path / "template-inbox" / "batch-001" / "set-001" / "source-01.png").is_file()
    assert (tmp_path / "template-inbox" / "batch-001" / "set-002" / "source-01.png").is_file()

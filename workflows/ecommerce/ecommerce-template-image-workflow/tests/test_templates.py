from pathlib import Path

from workflow.models import TemplateMetadata, TemplateRecord
from workflow.templates import (
    discover_template_records,
    load_template_annotations,
    load_template_record,
    template_storage_directory,
    write_template_annotations,
    write_template_record,
)


def test_write_template_record_creates_template_markdown(tmp_path: Path) -> None:
    record = TemplateRecord(
        template_id="amazon-selling-point-split-01",
        platform="amazon",
        role="selling-point image",
        aspect_ratio="1:1",
        output_size="2000x2000",
        layout="product on right, copy-safe zone on left",
        copy_safe_zone="left 40%",
        style="bright premium studio photography",
        scene="soft neutral studio",
        suitable_for=["compact packaged products"],
        avoid_for=["wide multi-product comparison"],
        references=["reference-01.png"],
    )

    path = write_template_record(tmp_path, record)

    text = path.read_text(encoding="utf-8")
    assert path == tmp_path / "template.md"
    assert "模板 ID: amazon-selling-point-split-01" in text
    assert "图片用途: selling-point image" in text
    assert "参考图: reference-01.png" in text


def test_template_record_is_immutable() -> None:
    record = TemplateRecord(
        "id", "amazon", "main image", "1:1", "2000x2000", "center", "none",
        "clean", "studio", [], [], [],
    )

    try:
        record.template_id = "changed"
    except Exception as error:
        assert type(error).__name__ == "FrozenInstanceError"
    else:
        raise AssertionError("TemplateRecord should be immutable")


def test_register_template_command_writes_under_library(tmp_path: Path, monkeypatch) -> None:
    from workflow import runner

    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    exit_code = runner.main(
        [
            "register-template",
            "--platform", "amazon",
            "--template-id", "amazon-main-01",
            "--role", "main image",
            "--ratio", "1:1",
            "--size", "2000x2000",
            "--layout", "centered product",
            "--safe-zone", "none",
            "--style", "clean catalog photography",
            "--scene", "pure white",
            "--suitable-for", "single products",
            "--avoid-for", "text-heavy banners",
            "--reference", "reference-01.png",
        ]
    )

    assert exit_code == 0
    path = tmp_path / "template-library" / "amazon" / "amazon-main-01" / "template.md"
    assert path.is_file()
    assert "参考图: reference-01.png" in path.read_text(encoding="utf-8")


def test_register_template_module_writes_under_template_set(tmp_path: Path, monkeypatch) -> None:
    from workflow import runner

    monkeypatch.setattr(runner, "root", lambda: tmp_path)
    exit_code = runner.main(
        [
            "register-template",
            "--platform", "amazon",
            "--template-set", "warm-organic-brown-editorial-01",
            "--module-id", "feature-hero",
            "--role", "详情页横幅图",
            "--ratio", "97:60",
            "--size", "970x600",
            "--layout", "left image, right title",
            "--safe-zone", "right 35%",
            "--style", "warm brown editorial",
            "--scene", "home kitchen",
            "--reference", "reference-01.png",
        ]
    )

    path = tmp_path / "template-library" / "amazon" / "warm-organic-brown-editorial-01" / "modules" / "feature-hero" / "template.md"
    text = path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "模板 ID: warm-organic-brown-editorial-01--feature-hero" in text
    assert "模板体系 ID: warm-organic-brown-editorial-01" in text
    assert "模块 ID: feature-hero" in text


def test_discover_template_module_under_product_neutral_template_set(tmp_path: Path) -> None:
    record = TemplateRecord(
        "warm-organic-brown-editorial-01--care-steps",
        "amazon",
        "详情页横幅图",
        "97:60",
        "970x600",
        "three care step cards",
        "top title; lower card captions",
        "warm brown editorial",
        "home kitchen",
        ["reusable household goods"],
        [],
        ["reference-01.png"],
        template_set_id="warm-organic-brown-editorial-01",
        module_id="care-steps",
    )
    directory = tmp_path / "amazon" / "warm-organic-brown-editorial-01" / "modules" / "care-steps"
    write_template_record(directory, record)

    records = discover_template_records(tmp_path)

    assert records == [record]
    assert template_storage_directory(tmp_path, record) == directory


def test_template_annotations_round_trip_and_legacy_record_stays_readable(tmp_path: Path) -> None:
    metadata = TemplateMetadata(
        role="main image", aspect_ratio="1:1", output_size="1200x1200", layout="center",
        copy_safe_zone="none", style="clean", scene="studio", suitable_for=("packaged products",),
        avoid_for=(), product_position="center", copy_density="low", card_count=1,
        scene_type="studio", non_transferable_elements=(),
    )
    directory = tmp_path / "amazon" / "set" / "modules" / "hero"
    write_template_annotations(directory, metadata)
    assert load_template_annotations(directory) == metadata

    legacy = TemplateRecord(
        "legacy", "amazon", "main image", "1:1", "1200x1200", "center", "none", "clean", "studio", [], [], []
    )
    write_template_record(tmp_path / "amazon" / "legacy", legacy)
    assert load_template_record(tmp_path / "amazon" / "legacy") == legacy

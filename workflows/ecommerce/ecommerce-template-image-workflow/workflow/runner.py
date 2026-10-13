from __future__ import annotations

import argparse
from pathlib import Path
import json

from workflow.config import ConfigError, load_image_env
from workflow.gateway import GatewayError, create_image_request
from workflow.geometry import (
    GeometryError, load_geometry_preflight, record_geometry_preflight_file, validate_geometry_preflight,
)
from workflow.models import DisplayCopy, ProductIdentity, TemplateRecord
from workflow.projects import (
    load_display_copy,
    load_product_identity,
    parse_visible_component_instances,
    prepare_image_task,
    select_template,
    validate_product_identity,
    validate_truth_sources,
    write_display_copy,
    write_product_identity,
    write_web_handoff,
)
from workflow.prompt_builder import build_direct_image_prompt
from workflow.visual_qa import (
    load_visual_qa,
    parse_visual_qa_checks,
    validate_visual_qa,
    write_visual_qa,
)
from workflow.templates import discover_template_records, template_storage_directory, write_template_record
from workflow.inbox import InboxError, import_template_set, write_analysis_draft
from workflow.template_sets import TemplateSetError, approve_template_set, rollback_template_set


def root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_component(value: str, field: str) -> str:
    path = Path(value)
    if not value or path.name != value or value in {".", ".."}:
        raise ValueError(f"{field} must be a simple directory name")
    return value


def _register_template(args: argparse.Namespace) -> int:
    platform = _safe_component(args.platform, "platform")
    if bool(args.template_set) != bool(args.module_id):
        raise ValueError("template-set and module-id must be provided together")
    if args.template_set:
        template_set_id = _safe_component(args.template_set, "template-set")
        module_id = _safe_component(args.module_id, "module-id")
        template_id = f"{template_set_id}--{module_id}"
        directory = root() / "template-library" / platform / template_set_id / "modules" / module_id
    else:
        if not args.template_id:
            raise ValueError("template-id is required when no template set is provided")
        template_set_id = None
        module_id = None
        template_id = _safe_component(args.template_id, "template-id")
        directory = root() / "template-library" / platform / template_id
    record = TemplateRecord(
        template_id=template_id,
        platform=platform,
        role=args.role,
        aspect_ratio=args.ratio,
        output_size=args.size,
        layout=args.layout,
        copy_safe_zone=args.safe_zone,
        style=args.style,
        scene=args.scene,
        suitable_for=args.suitable_for,
        avoid_for=args.avoid_for,
        references=args.reference,
        template_set_id=template_set_id,
        module_id=module_id,
    )
    path = write_template_record(directory, record)
    print(f"Wrote template record: {path}")
    return 0


def _import_template_set(args: argparse.Namespace) -> int:
    try:
        directory = import_template_set(
            root(), args.batch, args.set_id, [Path(source) for source in args.source], args.platform
        )
    except InboxError as error:
        print(str(error))
        return 1
    print(f"Imported template inbox set: {directory}")
    return 0


def _write_template_draft(args: argparse.Namespace) -> int:
    from workflow.inbox import _draft_from_dict

    inbox_directory = root() / "template-inbox" / _safe_component(args.batch, "batch") / _safe_component(args.set_id, "set")
    try:
        value = json.loads(Path(args.draft_file).read_text(encoding="utf-8"))
        draft = _draft_from_dict(value)
        path = write_analysis_draft(inbox_directory, draft)
    except (OSError, json.JSONDecodeError, InboxError, ValueError) as error:
        print(str(error))
        return 1
    print(f"Wrote template analysis draft: {path}")
    return 0


def _approve_template_set(args: argparse.Namespace) -> int:
    inbox_directory = root() / "template-inbox" / _safe_component(args.batch, "batch") / _safe_component(args.set_id, "set")
    try:
        directory = approve_template_set(root(), inbox_directory)
    except (TemplateSetError, ValueError) as error:
        print(str(error))
        return 1
    print(f"Approved template set: {directory}")
    return 0


def _rollback_template_set(args: argparse.Namespace) -> int:
    try:
        directory = rollback_template_set(root(), _safe_component(args.platform, "platform"), _safe_component(args.template_set, "template-set"), args.revision)
    except (TemplateSetError, ValueError) as error:
        print(str(error))
        return 1
    print(f"Rolled back template set: {directory}")
    return 0


def _prepare_image(args: argparse.Namespace) -> int:
    workflow_root = root()
    selected = select_template(
        discover_template_records(workflow_root / "template-library"),
        platform=args.platform,
        role=args.role,
        aspect_ratio=args.ratio,
        layout_keywords=args.layout_keyword,
        safe_zone_keywords=args.safe_zone_keyword,
        product_position_keywords=args.product_position_keyword,
        scene_keywords=args.scene_keyword,
        template_set_id=args.template_set,
        module_id=args.module_id,
    )
    task_path = prepare_image_task(
        workflow_root,
        args.project,
        selected,
        args.product_reference,
        args.request,
        args.image_number,
        args.all_images,
        match_platform=args.platform,
        match_role=args.role,
        match_aspect_ratio=args.ratio,
        layout_keywords=args.layout_keyword,
        safe_zone_keywords=args.safe_zone_keyword,
    )
    print(f"Prepared image task: {task_path}")
    return 0


def _project_task_directory(workflow_root: Path, project: str, image_number: int) -> Path:
    if not project or Path(project).name != project or project in {".", ".."}:
        raise ValueError("project must be a simple directory name")
    matches = sorted((workflow_root / "projects" / project / "images").glob(f"{image_number:02d}-*"))
    if len(matches) != 1:
        raise ValueError(f"could not find exactly one task for image {image_number:02d}")
    return matches[0]


def _project_product_references(request_path: Path) -> list[str]:
    lines = request_path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("## 产品参考图") + 1
    except ValueError as error:
        raise ValueError("project request is missing product references") from error
    references: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.startswith("- ") and line[2:] != "无":
            references.append(line[2:])
    return references


def _template_id(selected_path: Path) -> str:
    for line in selected_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- 模板 ID: "):
            return line.removeprefix("- 模板 ID: ")
    raise ValueError("selected template record is missing its template ID")


def _display_copy_from_args(args: argparse.Namespace) -> DisplayCopy:
    if not args.headline.strip():
        raise ValueError("headline must not be empty")
    return DisplayCopy(
        language=args.language,
        headline=args.headline.strip(),
        subheadline=args.subheadline.strip() if args.subheadline else None,
        labels=tuple(label.strip() for label in args.label if label.strip()),
        evidence=tuple(item.strip() for item in args.evidence if item.strip()),
    )


def _set_display_copy(args: argparse.Namespace) -> int:
    task_path = _project_task_directory(root(), args.project, args.image)
    path = write_display_copy(task_path, _display_copy_from_args(args))
    print(f"Wrote display copy: {path}")
    return 0


def _clean_required_items(values: list[str], field: str) -> tuple[str, ...]:
    items = tuple(value.strip() for value in values if value.strip())
    if not items:
        raise ValueError(f"{field} must contain at least one non-empty item")
    return items


def _product_identity_from_args(args: argparse.Namespace) -> ProductIdentity:
    return ProductIdentity(
        truth_sources=_clean_required_items(args.truth_source, "truth-source"),
        surface_graphics=_clean_required_items(args.surface_graphic, "surface-graphic"),
        physical_constraints=_clean_required_items(args.physical_constraint, "physical-constraint"),
        human_interaction_constraints=_clean_required_items(
            args.human_interaction_constraint, "human-interaction-constraint"
        ),
        components=_clean_required_items(args.component, "component"),
        relationships=_clean_required_items(args.relationship, "relationship"),
        visible_connection_evidence=_clean_required_items(
            args.visible_connection_evidence, "visible-connection-evidence"
        ),
        functional_features=_clean_required_items(args.functional_feature, "functional-feature"),
        required_use_states=_clean_required_items(args.use_state, "use-state"),
        assembly_state_evidence=_clean_required_items(
            args.assembly_state_evidence, "assembly-state-evidence"
        ),
        visible_component_instances=_clean_required_items(
            args.visible_component_instance, "visible-component-instance"
        ),
        forbidden_inventions=_clean_required_items(args.forbid, "forbid"),
        unknowns=tuple(item.strip() for item in args.unknown if item.strip()),
        approved=args.approved,
    )


def _set_product_identity(args: argparse.Namespace) -> int:
    task_path = _project_task_directory(root(), args.project, args.image)
    path = write_product_identity(task_path, _product_identity_from_args(args))
    print(f"Wrote product identity: {path}")
    return 0


def _record_visual_qa(args: argparse.Namespace) -> int:
    task_path = _project_task_directory(root(), args.project, args.image)
    identity = _load_generation_identity(task_path)
    required_instances = parse_visible_component_instances(
        identity.visible_component_instances
    )
    checks = parse_visual_qa_checks(args.instance_check)
    path = write_visual_qa(task_path, args.candidate, checks, required_instances)
    print(f"Wrote visual QA report: {path}")
    return 0


def _record_geometry_preflight(args: argparse.Namespace) -> int:
    task_path = _project_task_directory(root(), args.project, args.image)
    identity = _load_generation_identity(task_path)
    product_names = _project_product_references(task_path.parents[1] / "request.md")
    validate_truth_sources(identity, product_names)
    path = record_geometry_preflight_file(task_path, Path(args.checks_file), identity, args.objective)
    print(f"Wrote geometry preflight: {path}")
    return 0


def _approve_image(args: argparse.Namespace) -> int:
    task_path = _project_task_directory(root(), args.project, args.image)
    brief_path = task_path / "brief.md"
    report_path = task_path / "visual-qa.md"
    if not brief_path.is_file():
        raise ValueError("缺少 brief.md")
    if not report_path.is_file():
        raise ValueError("缺少 visual-qa.md；图片不能批准")
    identity = _load_generation_identity(task_path)
    required_instances = parse_visible_component_instances(
        identity.visible_component_instances
    )
    report = load_visual_qa(report_path)
    validate_visual_qa(
        task_path,
        report,
        required_instances,
        args.candidate,
        require_pass=True,
    )
    _set_brief_status(brief_path, "approved")
    print(f"Approved image: {task_path / args.candidate}")
    return 0


def _load_generation_identity(task_path: Path) -> ProductIdentity:
    path = task_path / "product-identity.md"
    if not path.is_file():
        raise ValueError("缺少 product-identity.md；请先检查全部产品参考图并确认部件数量与连接关系")
    identity = load_product_identity(path)
    validate_product_identity(identity)
    return identity


def _write_web_handoff(args: argparse.Namespace) -> int:
    workflow_root = root()
    task_path = _project_task_directory(workflow_root, args.project, args.image)
    project_dir = task_path.parents[1]
    selected_path = task_path / "selected-template.md"
    if not selected_path.exists():
        selected_path = project_dir / "selected-template.md"
    template_id = _template_id(selected_path)
    templates = discover_template_records(workflow_root / "template-library")
    try:
        template = next(record for record in templates if record.template_id == template_id)
    except StopIteration as error:
        raise ValueError(f"registered template not found: {template_id}") from error
    product_references = _project_product_references(project_dir / "request.md")
    copy_path = task_path / "copy-brief.md"
    display_copy = load_display_copy(copy_path) if copy_path.exists() else None
    product_identity = _load_generation_identity(task_path)
    geometry_preflight = load_geometry_preflight(task_path / "geometry-preflight.json")
    direct_prompt = build_direct_image_prompt(
        template,
        product_references,
        args.objective,
        display_copy,
        product_identity,
        geometry_preflight,
    )
    (task_path / "direct-image-prompt.md").write_text(direct_prompt + "\n", encoding="utf-8")
    path = write_web_handoff(
        task_path,
        direct_prompt,
        template,
        product_references,
        display_copy,
        product_identity,
        geometry_preflight,
    )
    print(f"Wrote web ChatGPT handoff: {path}")
    return 0


def _brief_status(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- 状态: "):
            return line.removeprefix("- 状态: ")
    return None


def _set_brief_status(path: Path, status: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(f"- 状态: {status}" if line.startswith("- 状态: ") else line for line in lines) + "\n", encoding="utf-8")


def _generate_codex(args: argparse.Namespace) -> int:
    workflow_root = root()
    task_path = _project_task_directory(workflow_root, args.project, args.image)
    brief_path = task_path / "brief.md"
    if args.route != "codex":
        raise ValueError("generate-codex requires an explicit --route codex selection")
    if _brief_status(brief_path) not in {"pending_user_route", "pending_generation"}:
        raise ValueError("current image is not ready for Codex generation")

    project_dir = task_path.parents[1]
    try:
        product_identity = _load_generation_identity(task_path)
        geometry_preflight = load_geometry_preflight(task_path / "geometry-preflight.json")
        objective = geometry_preflight.get("objective", "")
        validate_geometry_preflight(geometry_preflight, product_identity, objective)
        selected_path = task_path / "selected-template.md"
        if not selected_path.exists():
            selected_path = project_dir / "selected-template.md"
        template_id = _template_id(selected_path)
        template = next(record for record in discover_template_records(workflow_root / "template-library") if record.template_id == template_id)
        product_names = _project_product_references(project_dir / "request.md")
        prompt_path = task_path / "direct-image-prompt.md"
        if not prompt_path.exists():
            raise GatewayError("direct image prompt is missing; create the web handoff first")
        copy_path = task_path / "copy-brief.md"
        display_copy = load_display_copy(copy_path) if copy_path.exists() else None
        expected_prompt = build_direct_image_prompt(
            template, product_names, objective, display_copy, product_identity, geometry_preflight,
        )
        prompt = prompt_path.read_text(encoding="utf-8").rstrip("\n")
        if prompt != expected_prompt:
            raise GeometryError("直接生图提示词与当前几何预检不一致，请重新运行 write-web-handoff")
        config = load_image_env(workflow_root / "image-env.yaml")
        references = [project_dir / "product-references" / name for name in product_names]
        template_directory = template_storage_directory(workflow_root / "template-library", template)
        references.extend(template_directory / name for name in template.references)
        generated = create_image_request(config, prompt, references)
    except (ConfigError, GatewayError, StopIteration, ValueError) as error:
        message = str(error)
        (task_path / "gateway-error.md").write_text(f"# 中转站生图失败\n\n{message}\n", encoding="utf-8")
        if not isinstance(error, GeometryError):
            _set_brief_status(brief_path, "gateway_failed")
        print(message)
        return 1

    output = task_path / f"generated-image.{generated.extension}"
    output.write_bytes(generated.content)
    _set_brief_status(brief_path, "pending_user_review")
    print(f"Generated image: {output}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ecommerce template workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register-template", help="register a template")
    register.add_argument("--platform", required=True)
    register.add_argument("--template-id")
    register.add_argument("--template-set")
    register.add_argument("--module-id")
    register.add_argument("--role", required=True)
    register.add_argument("--ratio", required=True)
    register.add_argument("--size", required=True)
    register.add_argument("--layout", required=True)
    register.add_argument("--safe-zone", required=True)
    register.add_argument("--style", required=True)
    register.add_argument("--scene", required=True)
    register.add_argument("--suitable-for", action="append", default=[])
    register.add_argument("--avoid-for", action="append", default=[])
    register.add_argument("--reference", action="append", default=[])

    import_set = commands.add_parser("import-template-set", help="copy one uploaded template set into the inbox")
    import_set.add_argument("--batch", required=True)
    import_set.add_argument("--set", dest="set_id", required=True)
    import_set.add_argument("--platform", default="generic")
    import_set.add_argument("--source", action="append", required=True)

    write_draft = commands.add_parser("write-template-draft", help="store an agent-created analysis draft")
    write_draft.add_argument("--batch", required=True)
    write_draft.add_argument("--set", dest="set_id", required=True)
    write_draft.add_argument("--draft-file", required=True)

    approve_set = commands.add_parser("approve-template-set", help="archive a reviewed inbox set")
    approve_set.add_argument("--batch", required=True)
    approve_set.add_argument("--set", dest="set_id", required=True)

    rollback_set = commands.add_parser("rollback-template-set", help="restore one set revision")
    rollback_set.add_argument("--platform", required=True)
    rollback_set.add_argument("--template-set", required=True)
    rollback_set.add_argument("--revision", type=int, required=True)

    prepare = commands.add_parser("prepare-image", help="select a template and prepare one image task")
    prepare.add_argument("--project", required=True)
    prepare.add_argument("--platform", required=True)
    prepare.add_argument("--role", required=True)
    prepare.add_argument("--ratio", required=True)
    prepare.add_argument("--product-reference", action="append", default=[])
    prepare.add_argument("--request", required=True)
    prepare.add_argument("--image-number", type=int, default=1)
    prepare.add_argument("--all-images", action="store_true")
    prepare.add_argument("--layout-keyword", action="append", default=[])
    prepare.add_argument("--safe-zone-keyword", action="append", default=[])
    prepare.add_argument("--product-position-keyword", action="append", default=[])
    prepare.add_argument("--scene-keyword", action="append", default=[])
    prepare.add_argument("--template-set")
    prepare.add_argument("--module-id")

    handoff = commands.add_parser("write-web-handoff", help="write the web ChatGPT handoff for one image")
    handoff.add_argument("--project", required=True)
    handoff.add_argument("--image", type=int, required=True)
    handoff.add_argument("--objective", required=True)

    display_copy = commands.add_parser("set-display-copy", help="set protected layout copy for one image task")
    display_copy.add_argument("--project", required=True)
    display_copy.add_argument("--image", type=int, required=True)
    display_copy.add_argument("--language", choices=["English", "Chinese"], default="English")
    display_copy.add_argument("--headline", required=True)
    display_copy.add_argument("--subheadline")
    display_copy.add_argument("--label", action="append", default=[])
    display_copy.add_argument("--evidence", action="append", default=[])

    product_identity = commands.add_parser(
        "set-product-identity", help="set the reviewed product inventory and relationship lock"
    )
    product_identity.add_argument("--project", required=True)
    product_identity.add_argument("--image", type=int, required=True)
    product_identity.add_argument("--truth-source", action="append", default=[])
    product_identity.add_argument("--surface-graphic", action="append", default=[])
    product_identity.add_argument("--physical-constraint", action="append", default=[])
    product_identity.add_argument("--human-interaction-constraint", action="append", default=[])
    product_identity.add_argument("--component", action="append", default=[])
    product_identity.add_argument("--relationship", action="append", default=[])
    product_identity.add_argument("--visible-connection-evidence", action="append", default=[])
    product_identity.add_argument("--functional-feature", action="append", default=[])
    product_identity.add_argument("--use-state", action="append", default=[])
    product_identity.add_argument("--assembly-state-evidence", action="append", default=[])
    product_identity.add_argument("--visible-component-instance", action="append", default=[])
    product_identity.add_argument("--forbid", action="append", default=[])
    product_identity.add_argument("--unknown", action="append", default=[])
    product_identity.add_argument("--approved", action="store_true")

    geometry = commands.add_parser(
        "record-geometry-preflight", help="record source-grounded geometry checks before generation"
    )
    geometry.add_argument("--project", required=True)
    geometry.add_argument("--image", type=int, required=True)
    geometry.add_argument("--objective", required=True)
    geometry.add_argument("--checks-file", required=True)

    visual_qa = commands.add_parser(
        "record-visual-qa", help="record per-instance visual evidence for one candidate"
    )
    visual_qa.add_argument("--project", required=True)
    visual_qa.add_argument("--image", type=int, required=True)
    visual_qa.add_argument("--candidate", required=True)
    visual_qa.add_argument("--instance-check", action="append", default=[])

    approve_image = commands.add_parser(
        "approve-image", help="approve an image only after passing per-instance visual QA"
    )
    approve_image.add_argument("--project", required=True)
    approve_image.add_argument("--image", type=int, required=True)
    approve_image.add_argument("--candidate", required=True)

    generate = commands.add_parser("generate-codex", help="generate one image through the configured gateway")
    generate.add_argument("--project", required=True)
    generate.add_argument("--image", type=int, required=True)
    generate.add_argument("--route", choices=["codex"], required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "register-template":
            return _register_template(args)
        if args.command == "import-template-set":
            return _import_template_set(args)
        if args.command == "write-template-draft":
            return _write_template_draft(args)
        if args.command == "approve-template-set":
            return _approve_template_set(args)
        if args.command == "rollback-template-set":
            return _rollback_template_set(args)
        if args.command == "prepare-image":
            return _prepare_image(args)
        if args.command == "write-web-handoff":
            return _write_web_handoff(args)
        if args.command == "set-display-copy":
            return _set_display_copy(args)
        if args.command == "set-product-identity":
            return _set_product_identity(args)
        if args.command == "record-visual-qa":
            return _record_visual_qa(args)
        if args.command == "record-geometry-preflight":
            return _record_geometry_preflight(args)
        if args.command == "approve-image":
            return _approve_image(args)
        if args.command == "generate-codex":
            return _generate_codex(args)
    except (ConfigError, GatewayError, ValueError) as error:
        print(str(error))
        return 1
    raise ValueError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

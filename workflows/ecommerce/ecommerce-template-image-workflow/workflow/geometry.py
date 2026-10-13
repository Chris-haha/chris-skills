"""Source-grounded geometry review, not a physics or natural-language solver."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from workflow.models import ProductIdentity


GEOMETRY_DIMENSIONS = ("rigidity", "joints", "endpoints", "direction", "support")


class GeometryError(ValueError):
    """Raised when the planned geometry lacks complete, compatible evidence."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value or "\r" in value:
        raise GeometryError(f"几何预检字段必须为非空单行文本：{label}")
    return value


def _tokens(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise GeometryError(f"几何预检字段必须为{'可空' if allow_empty else '非空'}列表：{label}")
    items = [_text(item, label) for item in value]
    if len(items) != len(set(items)) or any(item != item.strip() for item in items):
        raise GeometryError(f"几何预检列表不能重复或包含首尾空白：{label}")
    return items


def _identity_digest(identity: ProductIdentity) -> str:
    content = json.dumps(asdict(identity), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _check_blockers(checks: Any, identity: ProductIdentity) -> list[str]:
    if not isinstance(checks, list) or not checks:
        raise GeometryError("几何预检缺少逐实例检查")
    required_ids = {item.partition(":")[0].strip() for item in identity.visible_component_instances}
    seen: set[str] = set()
    blockers: list[str] = []
    for check in checks:
        if not isinstance(check, dict) or set(check) != {"instance_id", "dimensions"}:
            raise GeometryError("几何预检实例字段无效")
        instance_id = _text(check["instance_id"], "instance_id")
        if instance_id in seen:
            raise GeometryError(f"几何预检实例重复：{instance_id}")
        seen.add(instance_id)
        dimensions = check["dimensions"]
        if not isinstance(dimensions, dict) or set(dimensions) != set(GEOMETRY_DIMENSIONS):
            raise GeometryError(f"几何预检维度集合不完整：{instance_id}")
        for name in GEOMETRY_DIMENSIONS:
            dimension = dimensions[name]
            label = f"{instance_id}/{name}"
            if not isinstance(dimension, dict) or set(dimension) != {
                "allowed", "required", "verdict", "sources", "evidence", "conflicts",
            }:
                raise GeometryError(f"几何预检维度字段不完整或无效：{label}")
            allowed = _tokens(dimension["allowed"], f"{label}/allowed")
            required = _tokens(dimension["required"], f"{label}/required")
            sources = _tokens(dimension["sources"], f"{label}/sources")
            conflicts = _tokens(dimension["conflicts"], f"{label}/conflicts", allow_empty=True)
            _text(dimension["evidence"], f"{label}/evidence")
            verdict = _text(dimension["verdict"], f"{label}/verdict")
            if verdict not in {"pass", "fail", "unknown"}:
                raise GeometryError(f"几何预检结果无效：{label}")
            for source in sources:
                if Path(source).name.casefold().startswith("generated-image") or source not in identity.truth_sources:
                    raise GeometryError(f"几何预检只能引用清单中的原始产品图：{source}")
            if verdict != "pass":
                blockers.append(f"{label}: {verdict}")
            if conflicts:
                blockers.append(f"{label}: 冲突 {'；'.join(conflicts)}")
            unsupported = set(required) - set(allowed)
            if unsupported:
                blockers.append(f"{label}: 要求超出原始事实允许范围 {'；'.join(sorted(unsupported))}")
    if seen != required_ids:
        raise GeometryError("几何预检实例集合必须与产品一致性清单完全一致")
    return blockers


def create_geometry_preflight(
    data: dict[str, Any], identity: ProductIdentity, objective: str,
) -> dict[str, Any]:
    """Preserve complete failed/unknown reviews; derive rather than trust status."""
    if not isinstance(data, dict) or set(data) != {"version", "checks"}:
        raise GeometryError("几何预检输入必须包含 version 和 checks")
    if type(data["version"]) is not int or data["version"] != 1:
        raise GeometryError("几何预检版本必须为 1")
    _text(objective, "objective")
    blockers = _check_blockers(data["checks"], identity)
    return {
        "version": 1,
        "identity_sha256": _identity_digest(identity),
        "objective": objective,
        "status": "blocked" if blockers else "passed",
        "checks": data["checks"],
    }


def validate_geometry_preflight(
    report: dict[str, Any] | None,
    identity: ProductIdentity,
    objective: str,
    *,
    require_pass: bool = True,
) -> None:
    """Fail closed on absent, malformed, stale, unknown, failed or conflicting evidence."""
    if report is None:
        raise GeometryError("缺少生图前几何预检，禁止创建提示词、交接包或生图")
    if isinstance(report, dict) and report.get("status") == "rejected":
        raise GeometryError("几何预检最近一次记录被拒绝，必须补齐证据重新检查")
    if not isinstance(report, dict) or set(report) != {
        "version", "identity_sha256", "objective", "status", "checks",
    }:
        raise GeometryError("几何预检报告字段不完整或无效")
    if type(report["version"]) is not int or report["version"] != 1:
        raise GeometryError("几何预检版本必须为 1")
    if report["identity_sha256"] != _identity_digest(identity):
        raise GeometryError("几何预检已过期：产品一致性清单已变化，必须重新检查")
    _text(report["objective"], "objective")
    if report["objective"] != objective:
        raise GeometryError("几何预检目标与当前图片目标不一致，必须重新检查")
    blockers = _check_blockers(report["checks"], identity)
    if report["status"] != ("blocked" if blockers else "passed"):
        raise GeometryError("几何预检汇总状态与逐项证据不一致")
    if require_pass and blockers:
        raise GeometryError(f"几何预检未通过，禁止生图：{'；'.join(blockers)}")


def write_geometry_preflight(
    task_directory: Path, data: dict[str, Any], identity: ProductIdentity, objective: str,
) -> Path:
    try:
        report = create_geometry_preflight(data, identity, objective)
    except GeometryError as error:
        _write_rejected_preflight(task_directory, data, error)
        raise
    return _write_preflight_document(task_directory, report)


def _write_preflight_document(task_directory: Path, report: dict[str, Any]) -> Path:
    task_directory.mkdir(parents=True, exist_ok=True)
    path = task_directory / "geometry-preflight.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=repr) + "\n", encoding="utf-8")
    return path


def _write_rejected_preflight(task_directory: Path, attempted_input: Any, error: GeometryError) -> None:
    """The newest attempt replaces previous clearance even when its schema is invalid."""
    _write_preflight_document(task_directory, {
        "version": 1, "status": "rejected", "attempted_input": attempted_input, "error": str(error),
    })


def record_geometry_preflight_file(
    task_directory: Path, input_path: Path, identity: ProductIdentity, objective: str,
) -> Path:
    """Preserve rejected raw JSON as well as structurally invalid parsed reviews."""
    try:
        data = load_geometry_preflight(input_path)
    except GeometryError as error:
        try:
            attempted_input = input_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            attempted_input = None
        _write_rejected_preflight(task_directory, attempted_input, error)
        raise
    return write_geometry_preflight(task_directory, data, identity, objective)


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GeometryError(f"几何预检 JSON 字段重复，不能覆盖原有证据：{key}")
        result[key] = value
    return result


def load_geometry_preflight(path: Path) -> dict[str, Any]:
    """Read input or saved JSON without discarding conflicts; consumers validate again."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GeometryError(f"缺少或无法读取生图前几何预检数据：{path.name}") from error
    if not isinstance(report, dict):
        raise GeometryError("几何预检报告必须为 JSON 对象")
    return report


def geometry_prompt_section(report: dict[str, Any]) -> str:
    """Render an already validated factual review with its proposed constraints."""
    lines = [
        "## 生图前几何可行性预检",
        "",
        "以下为根据原始产品图完成的逐实例几何审查。只能使用已核对的路径与支撑；不得为构图新增弯折、关节、端点位置或支撑。",
    ]
    for check in report["checks"]:
        lines.extend(["", f"实例：{check['instance_id']}"])
        for name in GEOMETRY_DIMENSIONS:
            dimension = check["dimensions"][name]
            lines.append(
                f"- {name}: 允许 {'；'.join(dimension['allowed'])}；当前要求 {'；'.join(dimension['required'])}；"
                f"原始图 {'；'.join(dimension['sources'])}；证据 {dimension['evidence']}"
            )
    return "\n".join(lines)

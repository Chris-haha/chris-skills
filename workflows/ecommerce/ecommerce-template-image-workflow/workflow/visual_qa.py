from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class VisualQAError(ValueError):
    """Raised when per-instance visual evidence is incomplete or unsafe."""


QA_DIMENSIONS = ("topology", "support", "clearance", "assembly", "framing")


@dataclass(frozen=True)
class VisualQADimension:
    name: str
    result: str
    trace: str


@dataclass(frozen=True)
class VisualQACheck:
    instance_id: str
    detail_crop_path: str
    context_crop_path: str
    dimensions: tuple[VisualQADimension, ...]

    @property
    def result(self) -> str:
        """Return the immutable result derived from all required dimensions."""
        return (
            "pass"
            if all(dimension.result == "pass" for dimension in self.dimensions)
            else "fail"
        )


@dataclass(frozen=True)
class VisualQAReport:
    version: int
    candidate: str
    status: str
    checks: tuple[VisualQACheck, ...]


def _reject_line_breaks(*values: str) -> None:
    if any("\n" in value or "\r" in value for value in values):
        raise VisualQAError("视觉质检字段不能包含换行")


def _validate_dimensions(
    dimensions: Sequence[VisualQADimension], instance_id: str
) -> tuple[VisualQADimension, ...]:
    if len(dimensions) != len(QA_DIMENSIONS):
        raise VisualQAError(f"实例检查维度集合不完整：{instance_id}")
    by_name: dict[str, VisualQADimension] = {}
    for dimension in dimensions:
        _reject_line_breaks(dimension.name, dimension.result, dimension.trace)
        if dimension.name not in QA_DIMENSIONS:
            raise VisualQAError(f"实例检查维度无效：{dimension.name}")
        if dimension.name in by_name:
            raise VisualQAError(f"实例检查维度重复：{dimension.name}")
        if dimension.result not in {"pass", "fail"}:
            raise VisualQAError(f"实例检查结果无效：{dimension.result}")
        if not dimension.trace.strip():
            raise VisualQAError(f"实例检查追踪证据不能为空：{dimension.name}")
        by_name[dimension.name] = dimension
    if set(by_name) != set(QA_DIMENSIONS):
        raise VisualQAError(f"实例检查维度集合不完整：{instance_id}")
    return tuple(by_name[name] for name in QA_DIMENSIONS)


def _parse_dimension(value: str) -> VisualQADimension:
    name, separator, outcome = value.partition("=")
    result, colon, trace = outcome.partition(":")
    name, result, trace = name.strip(), result.strip(), trace.strip()
    if not separator or not colon or not name:
        raise VisualQAError("实例检查维度格式无效")
    return VisualQADimension(name, result, trace)


def parse_visual_qa_checks(items: Sequence[str]) -> tuple[VisualQACheck, ...]:
    """Parse repeatable CLI check values into immutable checks."""
    if not items:
        raise VisualQAError("缺少实例检查")
    checks: list[VisualQACheck] = []
    seen: set[str] = set()
    for item in items:
        raw_parts = item.split("|")
        _reject_line_breaks(*raw_parts)
        parts = [part.strip() for part in raw_parts]
        if len(parts) != 3 + len(QA_DIMENSIONS):
            raise VisualQAError("实例检查格式无效，维度集合不完整")
        if not all(parts[:3]):
            raise VisualQAError("实例检查格式无效")
        instance_id, detail_crop_path, context_crop_path, *raw_dimensions = parts
        if instance_id in seen:
            raise VisualQAError(f"实例检查 ID 重复：{instance_id}")
        dimensions = _validate_dimensions(
            tuple(_parse_dimension(value) for value in raw_dimensions), instance_id
        )
        seen.add(instance_id)
        checks.append(
            VisualQACheck(
                instance_id, detail_crop_path, context_crop_path, dimensions
            )
        )
    return tuple(checks)


def _file_under(task_directory: Path, relative_path: str, label: str) -> Path:
    value = Path(relative_path)
    if value.is_absolute():
        raise VisualQAError(f"{label}必须位于任务目录内")
    task_root = task_directory.resolve()
    path = (task_directory / value).resolve()
    try:
        path.relative_to(task_root)
    except ValueError as error:
        raise VisualQAError(f"{label}必须位于任务目录内") from error
    if not path.is_file() or path.stat().st_size == 0:
        raise VisualQAError(f"{label}不存在或为空：{relative_path}")
    return path


def validate_visual_qa(
    task_directory: Path,
    report: VisualQAReport,
    required_instances: Mapping[str, str],
    candidate: str,
    require_pass: bool,
) -> None:
    """Validate exact instance coverage, evidence files, and report status."""
    if not required_instances:
        raise VisualQAError("缺少必检可见部件实例")
    if report.version != 3:
        raise VisualQAError("视觉质检报告版本必须为 3")
    _reject_line_breaks(report.candidate, report.status)
    if Path(candidate).name != candidate or candidate in {".", ".."}:
        raise VisualQAError("候选图必须是任务目录中的单个文件名")
    if report.candidate != candidate:
        raise VisualQAError(
            f"候选图不匹配：报告为 {report.candidate}，当前为 {candidate}"
        )
    _file_under(task_directory, candidate, "候选图")
    check_ids = [check.instance_id for check in report.checks]
    if len(check_ids) != len(set(check_ids)):
        raise VisualQAError("实例检查 ID 重复")
    if set(check_ids) != set(required_instances):
        raise VisualQAError("实例集合不匹配，必须逐一覆盖全部可见部件实例")
    for check in report.checks:
        _reject_line_breaks(
            check.instance_id, check.detail_crop_path, check.context_crop_path
        )
        _validate_dimensions(check.dimensions, check.instance_id)
        if check.detail_crop_path == check.context_crop_path:
            raise VisualQAError("细节裁图和上下文图必须是不同文件")
        detail_path = _file_under(task_directory, check.detail_crop_path, "细节裁图")
        context_path = _file_under(task_directory, check.context_crop_path, "上下文图")
        if detail_path == context_path:
            raise VisualQAError("细节裁图和上下文图必须是不同文件")
    computed_status = (
        "passed" if report.checks and all(check.result == "pass" for check in report.checks) else "failed"
    )
    if report.status != computed_status:
        raise VisualQAError("视觉质检汇总状态与实例结果不一致")
    if require_pass and report.status != "passed":
        raise VisualQAError("逐实例视觉质检未通过")


def write_visual_qa(
    task_directory: Path,
    candidate: str,
    checks: Sequence[VisualQACheck],
    required_instances: Mapping[str, str],
) -> Path:
    """Validate and write the deterministic task-local visual-QA report."""
    report = VisualQAReport(
        version=3,
        candidate=candidate,
        status="passed" if checks and all(check.result == "pass" for check in checks) else "failed",
        checks=tuple(checks),
    )
    validate_visual_qa(
        task_directory, report, required_instances, candidate, require_pass=False
    )
    by_id = {check.instance_id: check for check in checks}
    blocks: list[str] = []
    for instance_id in required_instances:
        check = by_id[instance_id]
        dimensions = {dimension.name: dimension for dimension in check.dimensions}
        dimension_lines = "\n".join(
            f"- {name}: {dimensions[name].result} | {dimensions[name].trace}"
            for name in QA_DIMENSIONS
        )
        blocks.append(
            f"## {instance_id}\n\n"
            f"- 细节裁图: {check.detail_crop_path}\n"
            f"- 上下文图: {check.context_crop_path}\n"
            f"{dimension_lines}\n"
            f"- 实例结果: {check.result}"
        )
    path = task_directory / "visual-qa.md"
    path.write_text(
        "# 可见部件实例质检\n\n"
        "- 版本: 3\n"
        f"- 候选图: {candidate}\n"
        f"- 状态: {report.status}\n\n"
        + "\n\n".join(blocks)
        + "\n",
        encoding="utf-8",
    )
    return path


def load_visual_qa(path: Path) -> VisualQAReport:
    """Load a report written by :func:`write_visual_qa`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    indexes = [index for index, line in enumerate(lines) if line.startswith("## ")]
    header = lines[: indexes[0] if indexes else len(lines)]
    header_prefixes = ("- 版本: ", "- 候选图: ", "- 状态: ")
    if any(
        line
        and line != "# 可见部件实例质检"
        and not line.startswith(header_prefixes)
        for line in header
    ):
        raise VisualQAError("视觉质检报告格式无效")
    version_values = [
        line.removeprefix("- 版本: ")
        for line in header
        if line.startswith("- 版本: ")
    ]
    if len(version_values) != 1 or version_values[0] != "3":
        raise VisualQAError("视觉质检报告版本格式无效")
    candidate_values = [
        line.removeprefix("- 候选图: ")
        for line in header
        if line.startswith("- 候选图: ")
    ]
    status_values = [
        line.removeprefix("- 状态: ")
        for line in header
        if line.startswith("- 状态: ")
    ]
    if (
        len(candidate_values) != 1
        or len(status_values) != 1
        or not candidate_values[0]
        or status_values[0] not in {"passed", "failed"}
    ):
        raise VisualQAError("视觉质检报告格式无效")
    candidate, status = candidate_values[0], status_values[0]
    checks: list[VisualQACheck] = []
    for position, start in enumerate(indexes):
        instance_id = lines[start].removeprefix("## ").strip()
        end = indexes[position + 1] if position + 1 < len(indexes) else len(lines)
        block = lines[start + 1 : end]
        prefixes = {
            "detail": "- 细节裁图: ",
            "context": "- 上下文图: ",
            "result": "- 实例结果: ",
            **{name: f"- {name}: " for name in QA_DIMENSIONS},
        }
        fields: dict[str, str] = {}
        for line in block:
            if not line:
                continue
            matches = [
                (name, prefix)
                for name, prefix in prefixes.items()
                if line.startswith(prefix)
            ]
            if len(matches) != 1:
                raise VisualQAError("视觉质检报告格式无效")
            name, prefix = matches[0]
            if name in fields:
                raise VisualQAError("视觉质检报告格式无效")
            fields[name] = line.removeprefix(prefix)
        if set(fields) != set(prefixes):
            raise VisualQAError("视觉质检报告格式无效")
        raw_dimensions: list[VisualQADimension] = []
        for name in QA_DIMENSIONS:
            result, trace_separator, trace = fields[name].partition(" | ")
            if not trace_separator:
                raise VisualQAError("视觉质检报告维度格式无效")
            raw_dimensions.append(
                VisualQADimension(name.strip(), result.strip(), trace.strip())
            )
        if not instance_id or not fields["detail"] or not fields["context"]:
            raise VisualQAError("视觉质检报告格式无效")
        dimensions = _validate_dimensions(raw_dimensions, instance_id)
        check = VisualQACheck(
            instance_id, fields["detail"], fields["context"], dimensions
        )
        if fields["result"] != check.result:
            raise VisualQAError("视觉质检报告实例结果与维度结果不一致")
        checks.append(check)
    if not checks:
        raise VisualQAError("视觉质检报告缺少实例检查")
    computed_status = (
        "passed" if all(check.result == "pass" for check in checks) else "failed"
    )
    if status != computed_status:
        raise VisualQAError("视觉质检汇总状态与实例结果不一致")
    return VisualQAReport(3, candidate, status, tuple(checks))

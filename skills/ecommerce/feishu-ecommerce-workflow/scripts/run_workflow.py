#!/usr/bin/env python3
"""Small command wrapper for the Feishu ecommerce mvp-workflow."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_ENV = [
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_APP_TOKEN",
    "FEISHU_TABLE_ID",
    "FEISHU_BOT_WEBHOOK",
    "OUTPUT_DIR",
    "RETENTION_DAYS",
]

SECRET_KEYS = {
    "FEISHU_APP_SECRET",
    "FEISHU_BOT_WEBHOOK",
    "OPENAI_API_KEY",
}

PLACEHOLDER_MARKERS = (
    "<your-",
    "your-",
    "replace-",
    "change-me",
    "example",
    "fill-in",
)


@dataclass
class DoctorResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        values[key] = value
    return values


def mask_value(key: str, value: str) -> str:
    if key in SECRET_KEYS and value:
        return f"{value[:4]}***{value[-4:]}" if len(value) > 8 else "***"
    return value


def is_placeholder(key: str, value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    if key == "FEISHU_BOT_WEBHOOK" and normalized.endswith("replace-me"):
        return True
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def default_runtime_dir() -> Path:
    configured = os.environ.get("FEISHU_ECOMMERCE_RUNTIME_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return (codex_home / "feishu-ecommerce-workflow-runtime").resolve()


def prepare_bundled_runtime(source_skill_dir: Path, runtime_dir: Path) -> Path:
    bundled_dir = source_skill_dir / "workflow"
    package_json = bundled_dir / "package.json"
    if not package_json.exists():
        raise SystemExit(f"Bundled workflow runtime is missing: {bundled_dir}")

    runtime_dir.mkdir(parents=True, exist_ok=True)
    for source in bundled_dir.rglob("*"):
        relative = source.relative_to(bundled_dir)
        destination = runtime_dir / relative
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        if relative.name in {".env", ".env.local", ".env.production"}:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    env_file = runtime_dir / ".env"
    env_example = runtime_dir / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy2(env_example, env_file)
        try:
            env_file.chmod(0o600)
        except OSError:
            pass
        print(f"Created local config template: {env_file}")
    return runtime_dir


def find_workflow_dir(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()

    env_dir = os.environ.get("FEISHU_ECOMMERCE_WORKFLOW_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    current = Path(__file__).resolve()
    for parent in current.parents:
        package_json = parent / "package.json"
        if package_json.exists() and package_json_contains_workflow_name(package_json):
            return parent

    cwd = Path.cwd().resolve()
    if package_json_contains_workflow_name(cwd / "package.json"):
        return cwd

    bundled = skill_dir() / "workflow"
    if (bundled / "package.json").exists():
        return prepare_bundled_runtime(skill_dir(), default_runtime_dir())

    raise SystemExit("Cannot locate a bundled workflow runtime.")


def package_json_contains_workflow_name(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return '"name": "mvp-workflow"' in path.read_text(encoding="utf-8")
    except OSError:
        return False


def merged_env(env_file: Path) -> dict[str, str]:
    env = parse_env_file(env_file)
    env.update(os.environ)
    return env


def validate_env(workflow_dir: Path, env_file: Path, env: dict[str, str]) -> DoctorResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not workflow_dir.exists():
        errors.append(f"workflow directory does not exist: {workflow_dir}")
        return DoctorResult(errors, warnings)

    if not (workflow_dir / "package.json").exists():
        errors.append(f"package.json not found in workflow directory: {workflow_dir}")

    if not env_file.exists():
        errors.append(f".env file not found: {env_file}")

    for key in REQUIRED_ENV:
        if is_placeholder(key, env.get(key)):
            errors.append(f"missing required env: {key}")

    provider = env.get("IMAGE_PROVIDER", "mock")
    if provider not in {"mock", "openai"}:
        errors.append("IMAGE_PROVIDER must be mock or openai")
    if provider == "openai" and is_placeholder("OPENAI_API_KEY", env.get("OPENAI_API_KEY")):
        errors.append("OPENAI_API_KEY is required when IMAGE_PROVIDER=openai")

    auto_run = env.get("AUTO_RUN_ENABLED", "false")
    if auto_run not in {"true", "false"}:
        errors.append("AUTO_RUN_ENABLED must be true or false")
    if auto_run == "true":
        warnings.append("AUTO_RUN_ENABLED=true: run-loop will keep polling until stopped")

    try:
        retention_days = int(env.get("RETENTION_DAYS", "0"))
        if retention_days <= 0:
            errors.append("RETENTION_DAYS must be a positive integer")
    except ValueError:
        errors.append("RETENTION_DAYS must be a positive integer")

    try:
        interval = int(env.get("AUTO_RUN_INTERVAL_MINUTES", "10"))
        if interval <= 0:
            errors.append("AUTO_RUN_INTERVAL_MINUTES must be a positive integer")
    except ValueError:
        errors.append("AUTO_RUN_INTERVAL_MINUTES must be a positive integer")

    return DoctorResult(errors, warnings)


def print_config_summary(env: dict[str, str]) -> None:
    keys = [
        *REQUIRED_ENV,
        "AUTO_RUN_ENABLED",
        "AUTO_RUN_INTERVAL_MINUTES",
        "IMAGE_PROVIDER",
        "OPENAI_BASE_URL",
        "OPENAI_IMAGE_MODEL",
        "ERP_REPORT_OWNER_OPEN_ID",
        "ERP_REPORT_OWNER_DISPLAY_NAME",
        "SEED_OWNER_OPEN_ID",
        "SEED_OWNER_DISPLAY_NAME",
    ]
    print("Config summary:")
    for key in keys:
        value = env.get(key)
        if value:
            print(f"  {key}={mask_value(key, value)}")


def run_command(command: Iterable[str], workflow_dir: Path, env: dict[str, str]) -> int:
    print(f"Running in {workflow_dir}: {' '.join(command)}")
    completed = subprocess.run(list(command), cwd=workflow_dir, env=env)
    return completed.returncode


def ensure_dependencies(workflow_dir: Path) -> bool:
    marker = workflow_dir / "node_modules" / ".bin" / "tsx"
    if marker.exists():
        return True
    if shutil.which("npm") is None:
        print("ERROR: npm is required to install workflow dependencies.", file=sys.stderr)
        return False
    print(f"Installing workflow dependencies in {workflow_dir}...")
    completed = subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
        cwd=workflow_dir,
        env=os.environ.copy(),
    )
    return completed.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Feishu ecommerce mvp-workflow with repeatable checks."
    )
    parser.add_argument(
        "command",
        choices=[
            "doctor",
            "init",
            "test",
            "build",
            "run-once",
            "run-loop",
            "rerun-task",
            "erp-report",
            "seed-task",
        ],
    )
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("--workflow-dir")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--confirm-rerun-completed", action="store_true")
    args = parser.parse_args(argv)

    workflow_dir = find_workflow_dir(args.workflow_dir)
    env_file = Path(args.env_file)
    if not env_file.is_absolute():
        env_file = workflow_dir / env_file
    env = merged_env(env_file)

    result = validate_env(workflow_dir, env_file, env)
    if args.command == "init":
        print(f"Workflow directory: {workflow_dir}")
        print(f"Env file: {env_file}")
        print("Edit the local .env with your Feishu and image-provider settings, then run doctor.")
        return 0
    if args.command == "doctor":
        print(f"Workflow directory: {workflow_dir}")
        print(f"Env file: {env_file}")
        print_config_summary(env)
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1

    if args.command not in {"test", "build"} and not result.ok:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("Run `doctor` for details.", file=sys.stderr)
        return 1

    if args.command in {"test", "build", "run-once", "run-loop", "rerun-task", "erp-report", "seed-task"}:
        if not ensure_dependencies(workflow_dir):
            return 1

    if args.command == "test":
        return run_command(["npm", "test"], workflow_dir, env)
    if args.command == "build":
        return run_command(["npm", "run", "build"], workflow_dir, env)
    if args.command == "run-once":
        return run_command(["npm", "exec", "tsx", "src/runner.ts"], workflow_dir, env)
    if args.command == "run-loop":
        if env.get("AUTO_RUN_ENABLED") != "true":
            print("ERROR: AUTO_RUN_ENABLED must be true for run-loop.", file=sys.stderr)
            return 1
        return run_command(
            ["npm", "exec", "tsx", "src/runner.ts", "run-loop"], workflow_dir, env
        )
    if args.command == "rerun-task":
        if not args.task_id:
            print("ERROR: rerun-task requires task_id.", file=sys.stderr)
            return 1
        command = ["npm", "exec", "tsx", "src/runner.ts", "rerun-task", args.task_id]
        if args.confirm_rerun_completed:
            command.append("--confirm-rerun-completed")
        return run_command(command, workflow_dir, env)
    if args.command == "erp-report":
        if not env.get("ERP_REPORT_OWNER_OPEN_ID"):
            print("ERROR: ERP_REPORT_OWNER_OPEN_ID is required.", file=sys.stderr)
            return 1
        return run_command(
            ["npm", "exec", "tsx", "src/runner.ts", "erp-report"], workflow_dir, env
        )
    if args.command == "seed-task":
        return run_command(
            ["npm", "exec", "tsx", "src/runner.ts", "seed-task"], workflow_dir, env
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

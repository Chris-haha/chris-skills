import tempfile
import unittest
from pathlib import Path
import sys
import os

import importlib.util


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "run_workflow.py"
)
spec = importlib.util.spec_from_file_location("run_workflow", SCRIPT_PATH)
run_workflow = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["run_workflow"] = run_workflow
spec.loader.exec_module(run_workflow)


class RunWorkflowTest(unittest.TestCase):
    def test_prepare_bundled_runtime_creates_user_runtime_and_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "skill"
            bundled_dir = skill_dir / "workflow"
            bundled_dir.mkdir(parents=True)
            (bundled_dir / "package.json").write_text(
                '{"name":"mvp-workflow"}', encoding="utf-8"
            )
            (bundled_dir / ".env.example").write_text(
                "IMAGE_PROVIDER=mock\n", encoding="utf-8"
            )
            runtime_dir = Path(temp_dir) / "runtime"

            result = run_workflow.prepare_bundled_runtime(skill_dir, runtime_dir)

            self.assertEqual(result, runtime_dir)
            self.assertTrue((runtime_dir / "package.json").exists())
            self.assertEqual(
                (runtime_dir / ".env").read_text(encoding="utf-8"),
                "IMAGE_PROVIDER=mock\n",
            )

    def test_prepare_bundled_runtime_preserves_existing_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "skill"
            bundled_dir = skill_dir / "workflow"
            bundled_dir.mkdir(parents=True)
            (bundled_dir / "package.json").write_text(
                '{"name":"mvp-workflow"}', encoding="utf-8"
            )
            (bundled_dir / ".env.example").write_text(
                "IMAGE_PROVIDER=mock\n", encoding="utf-8"
            )
            runtime_dir = Path(temp_dir) / "runtime"
            runtime_dir.mkdir()
            env_file = runtime_dir / ".env"
            env_file.write_text(
                "FEISHU_APP_SECRET=user-secret\n", encoding="utf-8"
            )

            run_workflow.prepare_bundled_runtime(skill_dir, runtime_dir)

            self.assertEqual(
                env_file.read_text(encoding="utf-8"),
                "FEISHU_APP_SECRET=user-secret\n",
            )

    def test_find_workflow_dir_uses_bundled_runtime_without_external_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "skill"
            bundled_dir = skill_dir / "workflow"
            bundled_dir.mkdir(parents=True)
            (bundled_dir / "package.json").write_text(
                '{"name":"mvp-workflow"}', encoding="utf-8"
            )
            (bundled_dir / ".env.example").write_text("", encoding="utf-8")
            runtime_dir = Path(temp_dir) / "runtime"

            original_script_path = run_workflow.__file__
            previous_runtime = os.environ.get("FEISHU_ECOMMERCE_RUNTIME_DIR")
            previous_cwd = Path.cwd()
            try:
                run_workflow.__file__ = str(skill_dir / "scripts" / "run_workflow.py")
                os.environ["FEISHU_ECOMMERCE_RUNTIME_DIR"] = str(runtime_dir)
                os.chdir(temp_dir)
                result = run_workflow.find_workflow_dir(None)
            finally:
                run_workflow.__file__ = original_script_path
                os.chdir(previous_cwd)
                if previous_runtime is None:
                    os.environ.pop("FEISHU_ECOMMERCE_RUNTIME_DIR", None)
                else:
                    os.environ["FEISHU_ECOMMERCE_RUNTIME_DIR"] = previous_runtime

            self.assertEqual(result, runtime_dir.resolve())

    def test_user_manual_does_not_contain_machine_specific_paths(self):
        manual_path = Path(__file__).resolve().parents[1] / "references" / "user-manual.md"
        content = manual_path.read_text(encoding="utf-8")

        forbidden_fragments = [
            "/" + "Volumes/",
            "/" + "Users/",
            "/" + "var/folders/",
            "/" + "private/var/",
            "~" + "/.codex",
        ]

        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, content)

    def test_parse_env_file_supports_comments_and_quoted_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "# comment",
                        "FEISHU_APP_ID=cli_123",
                        'OUTPUT_DIR="./data"',
                        "EMPTY=",
                    ]
                ),
                encoding="utf-8",
            )

            values = run_workflow.parse_env_file(env_file)

        self.assertEqual(values["FEISHU_APP_ID"], "cli_123")
        self.assertEqual(values["OUTPUT_DIR"], "./data")
        self.assertEqual(values["EMPTY"], "")

    def test_validate_env_requires_openai_key_for_openai_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_dir = Path(temp_dir)
            (workflow_dir / "package.json").write_text(
                '{"name":"mvp-workflow"}', encoding="utf-8"
            )
            env_file = workflow_dir / ".env"
            env_file.write_text("", encoding="utf-8")
            env = {
                "FEISHU_APP_ID": "cli_123",
                "FEISHU_APP_SECRET": "secret",
                "FEISHU_APP_TOKEN": "token",
                "FEISHU_TABLE_ID": "tbl_123",
                "FEISHU_BOT_WEBHOOK": "https://open.feishu.cn/open-apis/bot/v2/hook/x",
                "OUTPUT_DIR": "./data",
                "RETENTION_DAYS": "7",
                "IMAGE_PROVIDER": "openai",
            }

            result = run_workflow.validate_env(workflow_dir, env_file, env)

        self.assertIn(
            "OPENAI_API_KEY is required when IMAGE_PROVIDER=openai",
            result.errors,
        )

    def test_validate_env_accepts_mock_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow_dir = Path(temp_dir)
            (workflow_dir / "package.json").write_text(
                '{"name":"mvp-workflow"}', encoding="utf-8"
            )
            env_file = workflow_dir / ".env"
            env_file.write_text("", encoding="utf-8")
            env = {
                "FEISHU_APP_ID": "cli_123",
                "FEISHU_APP_SECRET": "secret",
                "FEISHU_APP_TOKEN": "token",
                "FEISHU_TABLE_ID": "tbl_123",
                "FEISHU_BOT_WEBHOOK": "https://open.feishu.cn/open-apis/bot/v2/hook/x",
                "OUTPUT_DIR": "./data",
                "RETENTION_DAYS": "7",
                "AUTO_RUN_ENABLED": "false",
                "AUTO_RUN_INTERVAL_MINUTES": "10",
                "IMAGE_PROVIDER": "mock",
            }

            result = run_workflow.validate_env(workflow_dir, env_file, env)

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])

    def test_shell_environment_overrides_env_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("AUTO_RUN_ENABLED=false\n", encoding="utf-8")
            previous = os.environ.get("AUTO_RUN_ENABLED")
            os.environ["AUTO_RUN_ENABLED"] = "true"
            try:
                values = run_workflow.merged_env(env_file)
            finally:
                if previous is None:
                    os.environ.pop("AUTO_RUN_ENABLED", None)
                else:
                    os.environ["AUTO_RUN_ENABLED"] = previous

        self.assertEqual(values["AUTO_RUN_ENABLED"], "true")


if __name__ == "__main__":
    unittest.main()

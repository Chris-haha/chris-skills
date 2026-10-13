from pathlib import Path

import pytest

from workflow.config import ConfigError, load_image_env


def test_load_image_env_returns_gateway_configuration(tmp_path: Path) -> None:
    path = tmp_path / "image-env.yaml"
    path.write_text(
        "base_url: https://gateway.example/v1\napi_key: test-key\nmodel: image-model\n",
        encoding="utf-8",
    )

    config = load_image_env(path)

    assert config.base_url == "https://gateway.example/v1"
    assert config.api_key == "test-key"
    assert config.model == "image-model"


@pytest.mark.parametrize(
    "content",
    ["", "base_url: https://x\n", "base_url: https://x\napi_key: k\n"],
)
def test_load_image_env_rejects_missing_required_values(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "image-env.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError):
        load_image_env(path)

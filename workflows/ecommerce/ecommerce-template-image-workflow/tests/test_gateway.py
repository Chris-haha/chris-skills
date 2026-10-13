from pathlib import Path

import pytest

from workflow.config import ImageEnv
from workflow.gateway import GatewayError, create_image_request


def test_create_image_request_rejects_missing_reference_file(tmp_path: Path) -> None:
    config = ImageEnv("https://gateway.example/v1", "secret", "image-model")

    with pytest.raises(GatewayError, match="reference"):
        create_image_request(config, "make one image", [tmp_path / "missing.png"])

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(ValueError):
    """Raised when the local image gateway configuration is invalid."""


@dataclass(frozen=True)
class ImageEnv:
    base_url: str
    api_key: str
    model: str


def load_image_env(path: Path) -> ImageEnv:
    """Load and validate the local OpenAI-compatible image gateway settings."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError("image-env.yaml could not be read") from error
    except yaml.YAMLError as error:
        raise ConfigError("image-env.yaml must contain valid YAML") from error

    if not isinstance(payload, dict):
        raise ConfigError("image-env.yaml must contain a mapping")

    values = {key: payload.get(key) for key in ("base_url", "api_key", "model")}
    if any(not isinstance(value, str) or not value.strip() for value in values.values()):
        raise ConfigError("image-env.yaml requires non-empty base_url, api_key, and model")

    return ImageEnv(**values)

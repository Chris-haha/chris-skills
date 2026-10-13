from __future__ import annotations

import base64
import json
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from workflow.config import ImageEnv


class GatewayError(RuntimeError):
    """A configuration or transport failure that is safe to write to disk."""


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    extension: str


def _multipart_body(config: ImageEnv, prompt: str, references: Sequence[Path]) -> tuple[bytes, str]:
    boundary = f"----ecommerceworkflow{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def field(name: str, value: str) -> None:
        chunks.extend((f"--{boundary}\r\n".encode(), f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(), value.encode(), b"\r\n"))

    field("model", config.model)
    field("prompt", prompt)
    field("response_format", "b64_json")
    for reference in references:
        mime_type = mimetypes.guess_type(reference.name)[0] or "application/octet-stream"
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image[]"; filename="{reference.name}"\r\n'.encode(),
            f"Content-Type: {mime_type}\r\n\r\n".encode(),
            reference.read_bytes(),
            b"\r\n",
        ))
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def create_image_request(config: ImageEnv, prompt: str, references: Sequence[Path]) -> GeneratedImage:
    """Submit one reference-guided image request to the configured compatible gateway."""
    missing = [path.name for path in references if not path.is_file()]
    if missing:
        raise GatewayError(f"reference file is missing: {', '.join(missing)}")
    if not references:
        raise GatewayError("at least one reference file is required")

    body, boundary = _multipart_body(config, prompt, references)
    request = Request(
        f"{config.base_url.rstrip('/')}/images/generations",
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise GatewayError(f"gateway returned HTTP {error.code}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise GatewayError("gateway request failed") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GatewayError("gateway returned an invalid image response") from error

    try:
        image = payload["data"][0]
        encoded = image["b64_json"]
        content = base64.b64decode(encoded, validate=True)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise GatewayError("gateway did not return a base64 image; reference images may be unsupported") from error
    if not content:
        raise GatewayError("gateway returned an empty image")
    return GeneratedImage(content=content, extension="png")

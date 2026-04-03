"""Load optional project `.env` into os.environ (does not override existing vars)."""

from __future__ import annotations

try:
    from runtime_logging_filter import install_hashlib_openssl_noise_filter

    install_hashlib_openssl_noise_filter()
except ImportError:
    pass

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or (_ROOT / ".env")
    if not env_path.is_file():
        return
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val

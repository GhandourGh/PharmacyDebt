"""
Suppress noisy ERROR logs from hashlib when OpenSSL lacks blake2 (some pyenv/macOS builds).
SHA-256 and the rest of the app still work; only the failed algorithm registration is hidden.
"""

from __future__ import annotations

import logging

_BLAKE_MSG = "code for hash blake2"
_installed = False


def install_hashlib_openssl_noise_filter() -> None:
    global _installed
    if _installed:
        return

    class _Filter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return _BLAKE_MSG not in record.getMessage()

    logging.getLogger().addFilter(_Filter())
    _installed = True

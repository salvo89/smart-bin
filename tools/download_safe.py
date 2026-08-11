# -*- coding: utf-8 -*-
"""SSL-tolerant PDF/HTML download helper."""
from __future__ import annotations

import ssl
import subprocess
import urllib.request
from pathlib import Path


def download_bytes(url: str, timeout: int = 120) -> bytes:
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Escilo"})
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        # Corporate MITM / incomplete CA store: fall back to curl -k
        result = subprocess.run(
            ["curl.exe", "-k", "-L", "-s", "--max-time", str(timeout), url],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(f"download failed for {url}: {result.stderr[:200]!r}")
        return result.stdout


def download_if_needed(url: str, dest: Path, force: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000 and not force:
        return dest
    data = download_bytes(url)
    dest.write_bytes(data)
    return dest

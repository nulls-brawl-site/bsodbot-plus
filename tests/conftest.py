"""Shared test environment defaults."""

from __future__ import annotations

import os

_LOCAL_NO_PROXY = "localhost,127.0.0.1,::1"

for _key in ("NO_PROXY", "no_proxy"):
    current = os.environ.get(_key)
    if current:
        values = {item.strip() for item in current.split(",") if item.strip()}
        values.update(_LOCAL_NO_PROXY.split(","))
        os.environ[_key] = ",".join(sorted(values))
    else:
        os.environ[_key] = _LOCAL_NO_PROXY

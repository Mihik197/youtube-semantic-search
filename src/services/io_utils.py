from __future__ import annotations

import json
import os
from typing import Any, TypeVar

T = TypeVar("T")


def read_json(path: str, default: T) -> T:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return default
    if default is None:
        return data
    return data if isinstance(data, type(default)) else default


def write_json_atomic(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


__all__ = ["read_json", "write_json_atomic"]

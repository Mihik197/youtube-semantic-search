from __future__ import annotations

import json
import os
from os import PathLike, fspath
from typing import Any, TypeVar, Union

T = TypeVar("T")

_Pathish = Union[str, PathLike[str]]


def read_json(path: _Pathish, default: T) -> T:
    path_str = fspath(path)
    if not os.path.exists(path_str):
        return default
    try:
        with open(path_str, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return default
    if default is None:
        return data
    return data if isinstance(data, type(default)) else default


def write_json_atomic(path: _Pathish, data: Any) -> None:
    path_str = fspath(path)
    os.makedirs(os.path.dirname(path_str), exist_ok=True)
    tmp_path = path_str + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path_str)


__all__ = ["read_json", "write_json_atomic"]

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from src import config
from src.services.io_utils import read_json, write_json_atomic


ARCHIVE_DIR = Path(config.ROOT_DIR) / "data"
ARCHIVE_FILE = ARCHIVE_DIR / "deleted_videos_archive.jsonl"
INDEX_FILE = ARCHIVE_DIR / "deleted_videos_index.json"


def _ensure_storage() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def _load_index(path: Path) -> Dict[str, Dict[str, str]]:
    _ensure_storage()
    return read_json(str(path), {})


def _save_index(path: Path, index: Dict[str, Dict[str, str]]) -> None:
    _ensure_storage()
    write_json_atomic(str(path), index)


def archive_deleted_videos(
    missing_ids: Iterable[str],
    historical_details: List[Dict],
    source_reason: str,
    run_context: Optional[Dict] = None,
) -> Dict[str, int]:
    """Persist snapshots for videos no longer returned by the API."""

    index = _load_index(INDEX_FILE)
    historical_lookup = {
        item.get("id"): item
        for item in historical_details
        if isinstance(item, dict) and item.get("id")
    }

    now_ts = int(time.time())
    missing_set = {vid for vid in missing_ids if vid}
    new_records: List[Dict] = []

    for video_id in sorted(missing_set):
        existing = index.get(video_id)
        if existing:
            existing["last_missing_ts"] = now_ts
            existing.setdefault("snapshot_count", 1)
            continue

        details = historical_lookup.get(video_id)
        if not details:
            continue

        record = {
            "id": video_id,
            "archived_at": now_ts,
            "source_reason": source_reason,
            "details": details,
        }
        if run_context:
            record["run_context"] = run_context

        new_records.append(record)
        index[video_id] = {
            "first_archived_ts": now_ts,
            "last_missing_ts": now_ts,
            "snapshot_count": 1,
        }

    if new_records:
        _ensure_storage()
        with ARCHIVE_FILE.open("a", encoding="utf-8") as handle:
            for record in new_records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    _save_index(INDEX_FILE, index)

    new_ids = {record["id"] for record in new_records}
    already_archived = len([
        vid for vid in missing_set if vid in index and vid not in new_ids
    ])

    return {
        "missing_input_count": len(missing_set),
        "archived_new_records": len(new_records),
        "already_archived": already_archived,
        "archive_file": str(ARCHIVE_FILE),
        "index_file": str(INDEX_FILE),
    }


def load_archive_records(limit: Optional[int] = None) -> List[Dict]:
    _ensure_storage()
    if not ARCHIVE_FILE.exists():
        return []

    records: List[Dict] = []
    with ARCHIVE_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if limit and len(records) >= limit:
                break
    return records


def load_archive_index() -> Dict[str, Dict[str, str]]:
    return _load_index(INDEX_FILE)

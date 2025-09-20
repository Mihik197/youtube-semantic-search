import os
import json
import time
from typing import Iterable, Dict, List, Optional

from src import config


ARCHIVE_DIR_NAME = "data"
ARCHIVE_FILENAME = "deleted_videos_archive.jsonl"  # newline-delimited JSON (JSONL)
INDEX_FILENAME = "deleted_videos_index.json"       # quick lookup to avoid duplicates


def _get_archive_paths():
    root = config.ROOT_DIR
    archive_dir = os.path.join(root, ARCHIVE_DIR_NAME)
    os.makedirs(archive_dir, exist_ok=True)
    archive_file = os.path.join(archive_dir, ARCHIVE_FILENAME)
    index_file = os.path.join(archive_dir, INDEX_FILENAME)
    return archive_file, index_file


def _load_index(index_path: str) -> Dict[str, Dict[str, str]]:
    if not os.path.exists(index_path):
        return {}
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_index(index_path: str, index: Dict[str, Dict[str, str]]):
    tmp_path = index_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, index_path)


def archive_deleted_videos(missing_ids: Iterable[str], historical_details: List[Dict], source_reason: str, run_context: Optional[Dict] = None) -> Dict[str, int]:
    """Archive details for videos that have disappeared (likely deleted/private).

    Strategy:
      - Maintain a JSONL append-only log of archived video detail snapshots.
      - Maintain an index JSON mapping video_id -> {first_archived_ts, last_archived_ts, snapshot_count}.
      - Only archive a video if we still have its details (from historical_details input) and have not already archived it.

    Args:
        missing_ids: IDs reported as missing (not returned by API) in this ingestion run.
        historical_details: List of previously stored video detail dicts (must contain 'id').
        source_reason: Short string describing trigger (e.g. 'ingestion_missing').
        run_context: Optional dict with extra context (e.g. batch size, ingestion run timestamp).

    Returns:
        Dict summarizing archival results.
    """
    archive_file, index_file = _get_archive_paths()
    index = _load_index(index_file)

    # Build lookup from historical details for fast access
    detail_lookup = {d.get('id'): d for d in historical_details if isinstance(d, dict) and d.get('id')}
    to_archive: List[Dict] = []

    now_ts = int(time.time())
    missing_set = set(missing_ids)
    for vid in sorted(missing_set):
        if vid in index:  # already archived at least once; update last_seen timestamp
            index_entry = index[vid]
            index_entry['last_missing_ts'] = now_ts
            index_entry['snapshot_count'] = index_entry.get('snapshot_count', 1)
            continue
        details = detail_lookup.get(vid)
        if not details:
            continue  # we have no stored details to archive
        record = {
            'id': vid,
            'archived_at': now_ts,
            'source_reason': source_reason,
            'details': details,
        }
        if run_context:
            record['run_context'] = run_context
        to_archive.append(record)
        index[vid] = {
            'first_archived_ts': now_ts,
            'last_missing_ts': now_ts,
            'snapshot_count': 1
        }

    # Append new records to JSONL
    if to_archive:
        with open(archive_file, 'a', encoding='utf-8') as f:
            for rec in to_archive:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    _save_index(index_file, index)

    return {
        'missing_input_count': len(missing_set),
        'archived_new_records': len(to_archive),
        'already_archived': len([vid for vid in missing_set if vid in index and vid not in {r['id'] for r in to_archive}]),
        'archive_file': archive_file,
        'index_file': index_file
    }


def load_archive_records(limit: Optional[int] = None) -> List[Dict]:
    archive_file, _ = _get_archive_paths()
    if not os.path.exists(archive_file):
        return []
    records: List[Dict] = []
    with open(archive_file, 'r', encoding='utf-8') as f:
        for line in f:
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
    _, index_file = _get_archive_paths()
    return _load_index(index_file)

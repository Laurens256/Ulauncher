from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger()


# remove json nulls
def sanitize_json(d):
    return {k: v for k, v in d.items() if v is not None}


def _filter_recursive(data, blacklist):
    if isinstance(data, dict):
        return {k: _filter_recursive(v, blacklist) for k, v in data.items() if v not in blacklist}
    if isinstance(data, list):
        return [_filter_recursive(v, blacklist) for v in data]
    return data


def json_load(path: str | Path) -> dict:
    data = {}
    file_path = Path(path).resolve()
    if file_path.is_file():
        try:
            data = json.loads(file_path.read_text(), object_hook=sanitize_json)
        except Exception:
            logger.exception('Error opening JSON file "%s"', file_path)
            logger.warning('Ignoring invalid JSON file "%s"', file_path)
    return data


def json_stringify(data, indent=None, sort_keys=True, value_blacklist: list[Any] | None = None) -> str:
    # When serializing to JSON, filter out common empty default values like None, empty list or dict
    # These are default values when initializing the objects, but they are not actual data
    if value_blacklist is None:
        value_blacklist = [[], {}, None, ""]
    filtered_data = _filter_recursive(data, value_blacklist)
    return json.dumps(filtered_data, indent=indent, sort_keys=sort_keys)


def json_save(data, path, indent=2, sort_keys=True, value_blacklist: list[Any] | None = None) -> bool:
    """Save self to file path"""
    # When serializing to JSON, filter out common empty default values like None, empty list or dict
    # These are default values when initializing the objects, but they are not actual data
    file_path = Path(path).resolve()
    if file_path:
        try:
            # Ensure parent dir first
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                json_stringify(data, indent=indent, sort_keys=sort_keys, value_blacklist=value_blacklist)
            )
        except Exception:
            logger.exception('Could not write to JSON file "%s"', file_path)
        else:
            return True
    return False

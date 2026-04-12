"""
Parse Softaculous WordPress Manager backup metadata.

The metadata file is a PHP serialized array. This parser handles
the subset of PHP serialization used by Softaculous without
requiring a third-party phpserialize library.
"""

import re
import tarfile
from io import BytesIO


def find_metadata_member(tar: tarfile.TarFile) -> tarfile.TarInfo | None:
    for member in tar.getmembers():
        name = member.name.lstrip("./")
        if (
            name.startswith("wp.")
            and not name.endswith(".php")
            and member.isfile()
            and "." in name[3:]
        ):
            return member
    return None


def parse_php_serialized_string(data: bytes, offset: int) -> tuple[str, int]:
    match = re.match(rb's:(\d+):"', data[offset:])
    if not match:
        return "", offset
    length = int(match.group(1))
    start = offset + len(match.group(0))
    value = data[start : start + length].decode("utf-8", errors="replace")
    end = start + length + 2
    return value, end


def parse_php_serialized_int(data: bytes, offset: int) -> tuple[int, int]:
    match = re.match(rb"i:(-?\d+);", data[offset:])
    if not match:
        return 0, offset
    return int(match.group(1)), offset + len(match.group(0))


def parse_php_serialized_bool(data: bytes, offset: int) -> tuple[bool, int]:
    match = re.match(rb"b:([01]);", data[offset:])
    if not match:
        return False, offset
    return match.group(1) == b"1", offset + len(match.group(0))


def parse_php_value(data: bytes, offset: int) -> tuple:
    if offset >= len(data):
        return None, offset

    tag = data[offset : offset + 2]

    if tag == b"s:":
        return parse_php_serialized_string(data, offset)
    elif tag == b"i:":
        return parse_php_serialized_int(data, offset)
    elif tag == b"b:":
        return parse_php_serialized_bool(data, offset)
    elif tag == b"N;":
        return None, offset + 2
    elif tag == b"a:":
        return parse_php_serialized_array(data, offset)
    else:
        return None, offset + 1


def parse_php_serialized_array(data: bytes, offset: int) -> tuple[dict, int]:
    match = re.match(rb"a:(\d+):\{", data[offset:])
    if not match:
        return {}, offset
    count = int(match.group(1))
    pos = offset + len(match.group(0))
    result = {}
    for _ in range(count):
        key, pos = parse_php_value(data, pos)
        value, pos = parse_php_value(data, pos)
        if key is not None:
            result[key] = value
    if pos < len(data) and data[pos : pos + 1] == b"}":
        pos += 1
    return result, pos


def parse_metadata(raw: bytes) -> dict:
    parsed, _ = parse_php_value(raw, 0)
    if not isinstance(parsed, dict):
        return {}
    return parsed


def extract_backup_info(metadata: dict) -> dict:
    return {
        "old_domain": metadata.get("softdomain", "unknown"),
        "old_url": metadata.get("softurl", "unknown"),
        "site_name": metadata.get("site_name", "unknown"),
        "db_prefix": metadata.get("dbprefix", "wp_"),
        "wp_version": metadata.get("ver", "unknown"),
        "admin_username": metadata.get("admin_username", "unknown"),
        "admin_email": metadata.get("admin_email", "unknown"),
        "backup_db": metadata.get("backup_db", 0) == 1,
        "backup_dir": metadata.get("backup_dir", 0) == 1,
        "softaculous_version": metadata.get("soft_version", "unknown"),
        "original_path": metadata.get("softpath", "unknown"),
    }


def parse_backup_file(file_bytes: bytes) -> dict | None:
    try:
        with tarfile.open(fileobj=BytesIO(file_bytes), mode="r:gz") as tar:
            meta_member = find_metadata_member(tar)
            if meta_member is None:
                return None

            raw = tar.extractfile(meta_member).read()
            metadata = parse_metadata(raw)
            if not metadata:
                return None

            has_sql = any(m.name.endswith("softsql.sql") for m in tar.getmembers())

            info = extract_backup_info(metadata)
            info["has_database_dump"] = has_sql
            info["metadata_file"] = meta_member.name
            return info
    except (tarfile.TarError, OSError):
        return None

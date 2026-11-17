"""
Files bigger than one Supabase Storage object may be (50 MB on the free plan).

A file up to SINGLE_MAX is one object at `path`, exactly as before. A bigger one
is stored as `path.part0`, `path.part1`, ... (each STORAGE_PART_BYTES or less)
and referred to as `bucket/path#parts=N`, so whoever reads it knows to join the
parts in order. References without `#parts=` are single objects, so everything
stored before this module keeps working.

The functions here are blocking (supabase-py is synchronous): call them through
`async_db`.
"""

import math
import os
import re
from typing import List, Optional, Tuple

from config.settings import settings

# Supabase's per-object limit. Anything up to it stays a single object, so
# files that uploaded fine before are stored exactly as before.
SINGLE_MAX = 50 * 1024 * 1024
MAX_PARTS = 20

_REF = re.compile(r"^(?P<bucket>[^/]+)/(?P<path>.+?)(?:#parts=(?P<parts>\d+))?$")


def part_bytes() -> int:
    return min(int(settings.STORAGE_PART_BYTES), SINGLE_MAX)


def parts_needed(size: int) -> int:
    """How many objects a file of `size` bytes is stored as."""
    if size <= SINGLE_MAX:
        return 1
    return math.ceil(size / part_bytes())


def part_paths(path: str, parts: int) -> List[str]:
    if parts <= 1:
        return [path]
    return [f"{path}.part{i}" for i in range(parts)]


def make_ref(bucket: str, path: str, parts: int) -> str:
    ref = f"{bucket}/{path}"
    return f"{ref}#parts={parts}" if parts > 1 else ref


def parse_ref(ref: Optional[str]) -> Optional[Tuple[str, str, int]]:
    """`bucket/path[#parts=N]` -> (bucket, path, parts); None if it isn't one."""
    m = _REF.match(ref or "")
    if not m:
        return None
    return m["bucket"], m["path"], max(1, int(m["parts"] or 1))


def upload_file(client, bucket: str, path: str, file_path: str,
                content_type: Optional[str] = None) -> int:
    """
    Store the file at `file_path` under `path`, in parts if it is too big for
    one object. Reads one part at a time (never the whole file). Returns the
    number of parts.
    """
    size = os.path.getsize(file_path)
    parts = parts_needed(size)
    if parts > MAX_PARTS:
        raise ValueError(f"{size} bytes is too large to store ({parts} parts)")
    options = {"upsert": "true"}
    if content_type:
        options["content-type"] = content_type
    store = client.storage.from_(bucket)
    step = size if parts == 1 else part_bytes()
    with open(file_path, "rb") as f:
        for part_path in part_paths(path, parts):
            store.upload(file=f.read(step), path=part_path, file_options=dict(options))
    return parts


def download_to(client, bucket: str, path: str, parts: int, dest_path: str) -> int:
    """Join the stored parts into `dest_path`. Returns the number of bytes written."""
    store = client.storage.from_(bucket)
    written = 0
    with open(dest_path, "wb") as f:
        for part_path in part_paths(path, parts):
            data = store.download(part_path)
            f.write(data)
            written += len(data)
    return written


def remove(client, bucket: str, path: str, parts: int) -> None:
    client.storage.from_(bucket).remove(part_paths(path, parts))

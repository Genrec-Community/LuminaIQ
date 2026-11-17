"""
Shrink a big PDF for storage and reading, with Ghostscript.

Scanned books are mostly page images at 300-600 dpi; re-encoding them at
150 dpi (then 110 dpi if that isn't enough) usually makes the file several
times smaller and still reads well on a screen. Text, fonts and the page
layout are kept, so citations still find their passage in the reader.

Only the copy shown in the reader is compressed: text extraction and OCR
always read the original upload. Without Ghostscript (local runs) nothing is
compressed and the original is stored as it is (in parts if needed).
"""

import asyncio
import os
import shutil
import tempfile
from typing import Optional

from config.settings import settings
from utils.logger import logger

# (colour/grey dpi, black-and-white dpi): gentler first
PASSES = [(150, 300), (110, 300)]


def _gs_args(gs: str, src: str, out: str, dpi: int, mono_dpi: int) -> list:
    return [
        gs, "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5", "-dPDFSETTINGS=/ebook",
        "-dDetectDuplicateImages=true", "-dCompressFonts=true", "-dSubsetFonts=true",
        "-dDownsampleColorImages=true", "-dColorImageDownsampleType=/Bicubic",
        f"-dColorImageResolution={dpi}", "-dColorImageDownsampleThreshold=1.2",
        "-dDownsampleGrayImages=true", "-dGrayImageDownsampleType=/Bicubic",
        f"-dGrayImageResolution={dpi}", "-dGrayImageDownsampleThreshold=1.2",
        "-dDownsampleMonoImages=true", f"-dMonoImageResolution={mono_dpi}",
        f"-sOutputFile={out}", src,
    ]


async def _run(args: list, timeout: float) -> bool:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    try:
        _, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("[PDF compress] Ghostscript timed out")
        return False
    if proc.returncode != 0:
        logger.warning(f"[PDF compress] Ghostscript failed: {(err or b'').decode(errors='ignore')[:300]}")
        return False
    return True


async def compress_pdf(src: str, target_bytes: int) -> Optional[str]:
    """
    A smaller copy of `src` (a temp file the caller deletes), or None when
    Ghostscript is missing, fails, or can't make it meaningfully smaller.
    Stops at the first pass that gets under `target_bytes`.
    """
    gs = shutil.which("gs")
    if not gs:
        logger.info("[PDF compress] Ghostscript not installed; storing the original")
        return None
    original = os.path.getsize(src)
    best, best_size = None, original
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.PDF_COMPRESS_TIMEOUT_SECONDS
    for dpi, mono_dpi in PASSES:
        remaining = deadline - loop.time()
        if remaining <= 5:
            break
        fd, out = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(src) or None)
        os.close(fd)
        ok = await _run(_gs_args(gs, src, out, dpi, mono_dpi), remaining)
        size = os.path.getsize(out) if ok and os.path.exists(out) else 0
        # Keep it only if it is a real saving (and not an empty/broken output)
        if ok and 1024 < size < best_size * 0.9:
            if best:
                os.unlink(best)
            best, best_size = out, size
        else:
            os.unlink(out)
        if best_size <= target_bytes:
            break
    if best:
        logger.info(f"[PDF compress] {original / 1e6:.1f} MB -> {best_size / 1e6:.1f} MB")
    return best

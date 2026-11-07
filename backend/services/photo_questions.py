"""
Photo questions in chat (AGENTS.md Phase 6, owner decision 12).

A student photographs a question or diagram. The app shrinks it to ≤1600 px JPEG and
sends it as a data URL with the chat message. Here we:
  1. check it's a real, reasonably sized image (decode),
  2. keep it in the private chat-images bucket so the chat can show a thumbnail (store),
  3. ask the vision-capable model to transcribe the question and describe any diagram,
     and, for Class 5-10, to flag images that aren't suitable (read_photo).
The transcript then becomes part of the student's message, so retrieval searches the book
for it and the normal tutor answers at their level: book first, otherwise "Not from your
book" when allowed. Only this one step uses the vision model.
"""

from __future__ import annotations

import base64
import re
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

from config.settings import settings
from utils.logger import logger

PHOTO_MARKER = "[From the student's photo]"
_DATA_URL = re.compile(r"^data:(image/(?:jpeg|jpg|png|webp));base64,([A-Za-z0-9+/=\s]+)$")
_MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}


class PhotoError(ValueError):
    """The photo can't be used; the message is safe to show the student."""


@dataclass
class Photo:
    data: bytes
    mime: str
    data_url: str


def decode(data_url: str) -> Photo:
    m = _DATA_URL.match((data_url or "").strip())
    if not m:
        raise PhotoError("That file isn't a photo we can read. Please send a JPG or PNG image.")
    try:
        data = base64.b64decode(m.group(2), validate=False)
    except Exception:
        raise PhotoError("That photo didn't come through properly. Please try again.")
    if len(data) > settings.CHAT_IMAGE_MAX_BYTES:
        raise PhotoError("That photo is too large. Please try a smaller one.")
    mime = next((t for magic, t in _MAGIC.items() if data.startswith(magic)), None)
    if not mime:
        raise PhotoError("That file isn't a photo we can read. Please send a JPG or PNG image.")
    return Photo(data=data, mime=mime, data_url=f"data:{mime};base64,{base64.b64encode(data).decode()}")


async def store(user_id: str, photo: Photo) -> Optional[str]:
    """Save to the private bucket; the path, or None if storage is unavailable (the answer still works)."""
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[photo.mime]
    path = f"{user_id}/{uuid.uuid4().hex}.{ext}"
    try:
        from db.client import async_db, get_supabase_client
        await async_db(lambda: get_supabase_client().storage.from_(settings.CHAT_IMAGES_BUCKET).upload(
            file=photo.data, path=path, file_options={"content-type": photo.mime}))
        return path
    except Exception as e:
        logger.warning(f"[Photo] not stored (thumbnail won't show later): {e}")
        return None


async def signed_url(path: Optional[str], seconds: int = 3600) -> Optional[str]:
    if not path:
        return None
    try:
        from db.client import async_db, get_supabase_client
        res = await async_db(lambda: get_supabase_client().storage.from_(settings.CHAT_IMAGES_BUCKET)
                             .create_signed_url(path, seconds))
        return (res or {}).get("signedURL") or (res or {}).get("signedUrl") or (res or {}).get("signed_url")
    except Exception as e:
        logger.debug(f"[Photo] no signed URL: {e}")
        return None


_READ_PROMPT = (
    "A student sent this photo while studying. Transcribe exactly any question, problem or text in it "
    "(keep numbering and answer options), and describe any diagram, graph, table or figure precisely "
    "enough to solve the problem without seeing it (labels, values, axes, arrows). Write maths in LaTeX "
    "($...$). Don't solve anything.\n"
    "Reply in this form:\nQUESTION: <the transcribed text, or 'none'>\nDIAGRAM: <the description, or 'none'>"
)
_SCHOOL_CHECK = (
    "\nThe student is a child (10-16). If the photo shows anything unsuitable for a child (violence, sexual "
    "content, self-harm, drugs) or is clearly not study material, reply with exactly UNSAFE and nothing else."
)


async def read_photo(photo: Photo, level: str, plan: Optional[str] = None) -> Tuple[str, bool]:
    """(transcript, unsafe) for a photo, using the plan's image-capable model."""
    from services.llm_service import llm_service
    prompt = _READ_PROMPT + (_SCHOOL_CHECK if level == "school" else "")
    out = (await llm_service.vision_completion(prompt, photo.data_url, max_tokens=900, plan=plan)).strip()
    if level == "school" and out.upper().startswith("UNSAFE"):
        return "", True
    return out[:4000], False


def with_photo(message: str, transcript: str) -> str:
    """The student's message plus what the photo shows (what retrieval and the tutor see)."""
    text = (message or "").strip() or "Please explain this."
    return f"{text}\n\n{PHOTO_MARKER}\n{transcript}"


UNSAFE_REPLY = ("I can only help with study photos, like a question from your textbook or a diagram from class. "
                "Try taking a photo of the question you're working on!")

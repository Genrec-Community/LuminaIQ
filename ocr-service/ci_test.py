"""CI check for the OCR service: realistic scanned spreads, timings, accuracy."""
import argparse
import io
import sys
import time

import requests
from PIL import Image, ImageDraw, ImageFont

LEFT = ["Chapter 4: Engineering Ethics", "Engineers hold paramount the safety, health",
        "and welfare of the public in the performance", "of their professional duties. Integrity",
        "means acting honestly even when no one is", "watching, and keeping promises made."]
RIGHT = ["Respect for others and responsibility for", "one's actions build trust within teams",
         "and society. Courage is the willingness to", "do what is right despite the risk of",
         "personal loss, and empathy means sharing", "and understanding the feelings of others."]


def spread(n: int) -> bytes:
    """A two-page spread scanned at 300 dpi, sent as the backend sends it (long side 2400 px, JPEG)."""
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 38)
    img = Image.new("L", (3508, 2480), 246)
    d = ImageDraw.Draw(img)
    for i, t in enumerate(LEFT * 3):
        d.text((200, 220 + i * 105), t, font=font, fill=18)
    for i, t in enumerate(RIGHT * 3):
        d.text((1880, 220 + i * 105), t, font=font, fill=18)
    d.text((1700, 2380), str(n), font=font, fill=18)
    img = img.resize((2400, int(2480 * 2400 / 3508)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--token", default="")
    ap.add_argument("--pages", type=int, default=4)
    ap.add_argument("--label", default="")
    a = ap.parse_args()

    t = time.time()
    while True:
        try:
            h = requests.get(f"{a.url}/health", timeout=10).json()
            if h.get("ready"):
                break
            if h.get("error"):
                sys.exit(f"model load failed: {h['error']}")
        except Exception:
            pass
        if time.time() - t > 600:
            sys.exit("service not ready after 600 s")
        time.sleep(3)
    print(f"[{a.label}] ready after {time.time() - t:.0f} s (startup + model load)")

    # unauthorised request is refused
    r = requests.post(f"{a.url}/ocr", files=[("files", ("p.jpg", spread(0), "image/jpeg"))], timeout=600)
    assert r.status_code == 401, r.status_code

    files = [("files", (f"p{i}.jpg", spread(i + 1), "image/jpeg")) for i in range(a.pages)]
    t = time.time()
    r = requests.post(f"{a.url}/ocr", files=files, headers={"X-OCR-Token": a.token}, timeout=1800)
    r.raise_for_status()
    out = r.json()
    wall = time.time() - t
    per = [p["ms"] for p in out["pages"]]
    print(f"[{a.label}] {a.pages} spreads in {wall:.1f} s; per spread ms: {per}; "
          f"{wall / a.pages:.1f} s per spread")
    text = out["pages"][0]["text"]
    print(f"[{a.label}] first spread text:\n{text[:600]}")
    must = ["Engineering Ethics", "paramount", "Integrity", "responsibility", "empathy"]
    found = {m: m.lower() in text.lower() for m in must}
    print(f"[{a.label}] key phrases found: {found}")
    if not all(found.values()):
        sys.exit("accuracy check failed")


if __name__ == "__main__":
    main()

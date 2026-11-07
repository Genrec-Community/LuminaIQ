r"""
Parse JSON written by a model without losing LaTeX.

Models often put maths in JSON strings with single backslashes: "$\\frac{1}{2}mv^2$" arrives
as `"$\frac{1}{2}mv^2$"`. Standard JSON then reads `\f` as a form feed (leaving "rac"), `\t`
in `\theta` as a tab, `\n` in `\nabla` as a newline, and `\s` in `\sigma` is simply invalid.
repair() doubles a backslash when it starts a LaTeX command, while real JSON escapes
(`\n` before ordinary text, `\"`, `\\`, `\uXXXX`) are kept.

    loads(text)             -> parsed value (raises ValueError if it isn't JSON at all)
    extract(text, "[")      -> the first JSON array (or "{" object) found in a reply, parsed
"""

from __future__ import annotations

import json
import re
from typing import Any

# LaTeX commands that begin with a letter JSON also uses as an escape (b f n r t u):
# for these, the whole word decides whether it's maths or an escape.
_AMBIGUOUS = {
    "b": {"beta", "bar", "binom", "begin", "bf", "big", "Big", "bigg", "bmod", "bot", "boxed", "bullet", "bar", "backslash",
          "bigcup", "bigcap", "bigl", "bigr", "boldsymbol", "breve"},
    "f": {"frac", "forall", "flat", "frown", "footnotesize"},
    "n": {"nabla", "nu", "neq", "ne", "newline", "not", "ni", "neg", "nleq", "ngeq", "notin", "nexists", "nmid",
          "nparallel", "nsubseteq", "noindent", "normalsize"},
    "r": {"rho", "right", "rightarrow", "Rightarrow", "rangle", "rceil", "rfloor", "rm", "rbrace", "rvert", "rVert",
          "rightleftharpoons", "rightharpoonup", "rmoustache"},
    "t": {"theta", "tau", "times", "text", "textbf", "textit", "textrm", "tan", "tanh", "to", "top", "tilde", "triangle",
          "therefore", "tfrac", "texttt", "textsf", "textsuperscript", "textsubscript", "tiny", "triangleq", "tt"},
    "u": {"upsilon", "uparrow", "Uparrow", "underline", "underbrace", "cup", "union", "unlhd", "unrhd", "upharpoonright",
          "updownarrow"},
}
_JSON_ESCAPE_LETTERS = set("bfnrtu")
_CMD = re.compile(r'(?<!\\)((?:\\\\)*)\\([A-Za-z]+)')


def repair(text: str) -> str:
    def fix(m: re.Match) -> str:
        pairs, word = m.group(1), m.group(2)
        first = word[0]
        if first not in _JSON_ESCAPE_LETTERS:
            return f"{pairs}\\\\{word}"                     # \sigma, \alpha, \Delta: always LaTeX
        if word in _AMBIGUOUS.get(first, ()) or (first == "u" and not re.match(r"u[0-9a-fA-F]{4}", word)
                                                  and word in _AMBIGUOUS["u"]):
            return f"{pairs}\\\\{word}"
        return m.group(0)                                    # \n before text, \uXXXX: a real JSON escape
    return _CMD.sub(fix, text)


def _clean(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    return re.sub(r"\s*```$", "", text)


def loads(text: str) -> Any:
    text = _clean(text)
    try:
        return json.loads(repair(text))
    except json.JSONDecodeError:
        # Last resort: strict=False also accepts raw control characters inside strings
        return json.loads(repair(text), strict=False)


def extract(text: str, opener: str = "[") -> Any:
    """The outermost JSON array (or object) in a reply, parsed LaTeX-safely."""
    closer = "]" if opener == "[" else "}"
    text = _clean(text)
    start, end = text.find(opener), text.rfind(closer)
    if start == -1 or end <= start:
        raise ValueError("No JSON found in the reply")
    return loads(text[start:end + 1])

from __future__ import annotations

import re


MaskType = dict[int, str]


def get_headers(text: str) -> list[str]:
    return re.findall(r"^=+ *(.+?) *=+ *$", text, flags=re.M)


def mask_text(
    text: str,
    regex: re.Pattern[str],
    mask: MaskType | None = None,
) -> tuple[str, MaskType]:
    mask = mask or {}
    try:
        key = max(mask.keys()) + 1
    except ValueError:
        key = 1
    matches = [
        match[0] if isinstance(match, tuple) else match
        for match in regex.findall(text)
    ]
    matches = sorted(matches, key=len, reverse=True)
    for match in matches:
        mask[key] = match
        text = text.replace(match, f"***bot***masked***{key}***")
        key += 1
    return text, mask


def mask_html_tags(
    text: str,
    mask: MaskType | None = None,
) -> tuple[str, MaskType]:
    tags_regex = re.compile(
        r"""(<\/?\w+(?:\s+\w+(?:\s*=\s*(?:(?:"[^"]*")|(?:'[^']*')|"""
        r"""[^>\s]+))?)*\s*\/?>)""",
        flags=re.S,
    )
    return mask_text(text, tags_regex, mask)


def mask_pipe_mw(text: str) -> str:
    return text.replace("{{!}}", "|***bot***=***param***|")


def unmask_text(text: str, mask: MaskType) -> str:
    text = text.replace("|***bot***=***param***|", "{{!}}")
    while text.find("***bot***masked***") > -1:
        for key, value in mask.items():
            text = text.replace(f"***bot***masked***{key}***", value)
    return text

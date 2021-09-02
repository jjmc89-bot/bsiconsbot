"""Functions for manipulating wiki-text."""
from __future__ import annotations

import re
from typing import Dict, Pattern


MaskType = Dict[int, str]


# from pywikibot.textlib
FILE_LINK_REGEX = r"""
    \[\[\s*
    (?:{})  # namespace aliases
    \s*:
    (?=(?P<filename>
        [^]|]*
    ))(?P=filename)
    (
        \|
        (
            (
                (?=(?P<inner_link>
                    \[\[.*?\]\]
                ))(?P=inner_link)
            )?
            (?=(?P<other_chars>
                [^\[\]]*
            ))(?P=other_chars)
        |
            (?=(?P<not_wikilink>
                \[[^]]*\]
            ))(?P=not_wikilink)
        )*?
    )??
    \]\]
"""


def get_headers(text: str) -> list[str]:
    """
    Return a list of section headers.

    :param text: Text to parse
    """
    return re.findall(r"^=+ *(.+?) *=+ *$", text, flags=re.M)


def mask_text(
    text: str, regex: Pattern[str], mask: MaskType | None = None
) -> tuple[str, MaskType]:
    """
    Mask text using a regex.

    :param text: Text to mask
    :param regex: Compiled regex
    :param mask: Mask store
    :return: Masked text and mask store
    """
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
    text: str, mask: MaskType | None = None
) -> tuple[str, MaskType]:
    """
    Mask HTML tags.

    :param text: Text to mask
    :param mask: Mask store
    :return: Masked text and mask store
    """
    tags_regex = re.compile(
        r"""(<\/?\w+(?:\s+\w+(?:\s*=\s*(?:(?:"[^"]*")|(?:'[^']*')|"""
        r"""[^>\s]+))?)*\s*\/?>)""",
        flags=re.S,
    )
    return mask_text(text, tags_regex, mask)


def mask_pipe_mw(text: str) -> str:
    """
    Mask the pipe magic word ({{!}}).

    :param text: Text to mask
    :return: Masked text
    """
    return text.replace("{{!}}", "|***bot***=***param***|")


def unmask_text(text: str, mask: MaskType) -> str:
    """
    Unmask text.

    :param text: Text to unmask
    :param mask: Mask store
    :return: unasked text
    """
    text = text.replace("|***bot***=***param***|", "{{!}}")
    while text.find("***bot***masked***") > -1:
        for key, value in mask.items():
            text = text.replace(f"***bot***masked***{key}***", value)
    return text

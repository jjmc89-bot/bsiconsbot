"""Functions for manipulating wiki-text."""
import re

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


def get_headers(text):
    """
    Return a list of section headers.

    @param text: Text to parse
    @type text: str

    @rtype: list
    """
    return re.findall(r"^=+ *(.+?) *=+ *$", text, flags=re.M)


def mask_text(text, regex, mask=None):
    """
    Mask text using a regex.

    @rtype: str, dict
    """
    mask = mask or dict()
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


def mask_html_tags(text, mask=None):
    """Mask HTML tags."""
    tags_regex = re.compile(
        r"""(<\/?\w+(?:\s+\w+(?:\s*=\s*(?:(?:"[^"]*")|(?:'[^']*')|"""
        r"""[^>\s]+))?)*\s*\/?>)""",
        flags=re.S,
    )
    return mask_text(text, tags_regex, mask)


def mask_pipe_mw(text):
    """Mask the pipe magic word ({{!}})."""
    return text.replace("{{!}}", "|***bot***=***param***|")


def unmask_text(text, mask):
    """Unmask text."""
    text = text.replace("|***bot***=***param***|", "{{!}}")
    while text.find("***bot***masked***") > -1:
        for key, value in mask.items():
            text = text.replace(f"***bot***masked***{key}***", value)
    return text

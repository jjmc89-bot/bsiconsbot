"""
Objects representing various MediaWiki pages.

This module extends pywikibot_extensions.page.
"""

from __future__ import annotations

from typing import Any

import jsoncfg
import pywikibot
from jsoncfg.config_classes import ConfigJSONObject
from pywikibot_extensions.page import FilePage, PageSource


def load_config(page: pywikibot.Page, **kwargs: Any) -> ConfigJSONObject:
    """Load JSON config from the page."""
    if page.isRedirectPage():
        pywikibot.log(f"{page!r} is a redirect.")
        page = page.getRedirectTarget()
    _empty = jsoncfg.loads_config("{}")
    if not page.exists():
        pywikibot.log(f"{page!r} does not exist.")
        return _empty
    try:
        return jsoncfg.loads_config(page.get(**kwargs).strip())
    except pywikibot.exceptions.PageRelatedError:
        return _empty


class BSiconPage(FilePage):
    """Represents a BSicon file description page."""

    PREFIX = "BSicon_"
    SUFFIX = ".svg"

    def __init__(
        self, source: PageSource, title: str = "", name: str = ""
    ) -> None:
        """Initialize."""
        if not title and name:
            title = f"{self.PREFIX}{name}{self.SUFFIX}"
        super().__init__(source, title)
        title = self.title(underscore=True, with_ns=False)
        if not (title.startswith(self.PREFIX) and title.endswith(self.SUFFIX)):
            raise ValueError(f"{self.title()!r} is not a BSicon.")

    def __eq__(self, other: object) -> bool:
        """Test if two BSicons are equal."""
        if isinstance(other, self.__class__):
            return self.name == other.name
        return NotImplemented

    def __hash__(self) -> int:
        """Return a stable identifier to be used as a key in hash tables."""
        return hash(self.name)

    @property
    def name(self) -> str:
        """Return BSicon name."""
        return self.title(underscore=True, with_ns=False)[
            len(self.PREFIX) : -len(self.SUFFIX)  # noqa: E203
        ]

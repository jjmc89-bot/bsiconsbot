"""
Objects representing various MediaWiki pages.

This module extends pywikibot.page.
"""
import re
from typing import Any, Iterable, Optional, Set, Union

import jsoncfg
import pywikibot
from jsoncfg.config_classes import ConfigJSONObject


PageSource = Union[
    pywikibot.Page, pywikibot.site.BaseSite, pywikibot.page.BaseLink
]


def get_template_pages(
    templates: Iterable[pywikibot.Page],
) -> Set[pywikibot.Page]:
    """
    Given an iterable of templates, return a set of pages.

    :param templates: iterable of templates
    """
    pages = set()
    for template in templates:
        if template.isRedirectPage():
            template = template.getRedirectTarget()
        if not template.exists():
            continue
        pages.add(template)
        for tpl in template.backlinks(filter_redirects=True):
            pages.add(tpl)
    return pages


class Page(pywikibot.Page):
    """Represents a MediaWiki page."""

    BOT_START_END = re.compile(
        r"^(.*?<!--\s*bot start\s*-->).*?(<!--\s*bot end\s*-->.*)$",
        flags=re.S | re.I,
    )

    def get_json(self, **kwargs: Any) -> ConfigJSONObject:
        """Get JSON from the page."""
        if self.isRedirectPage():
            pywikibot.log(f"{self!r} is a redirect.")
            page = self.getRedirectTarget()
        else:
            page = self
        _empty = jsoncfg.loads_config("{}")
        if not page.exists():
            pywikibot.log(f"{self!r} does not exist.")
            return _empty
        try:
            return jsoncfg.loads_config(page.get(**kwargs).strip())
        except pywikibot.exceptions.PageRelatedError:
            return _empty

    def save_bot_start_end(
        self,
        text: str,
        minor: bool = False,
        botflag: Optional[bool] = False,
        **kwargs: Any,
    ) -> None:
        """
        Write text to the specified area of a given page.

        See pywikibot.Page.save() for arguments.
        """
        if not self.exists():
            pywikibot.error(f"{self!r} does not exist. Skipping.")
            return
        text = text.strip()
        current_text = self.text  # type: ignore[has-type]
        if self.BOT_START_END.match(current_text):
            self.text = self.BOT_START_END.sub(fr"\1\n{text}\2", current_text)
        else:
            self.text = text
        self.save(minor=minor, botflag=botflag, **kwargs)

    def title_regex(self, **kwargs: Any) -> str:
        """Return a regex to match the title of the page."""
        title = self.title(underscore=True, **kwargs)
        title = re.escape(title)
        title = title.replace("_", "[ _]+")
        if self.site.siteinfo["case"] == "first-letter":
            char1 = title[:1]
            if char1.isalpha():
                # The first letter is not case sensative.
                title = f"[{char1}{char1.swapcase()}]{title[1:]}"
        return title

    def titles_regex(self, **kwargs: Any) -> str:
        """Return a regex to match titles of the page, including redirects."""
        titles = set()
        titles.add(self.title_regex(**kwargs))
        try:
            redirects = self.backlinks(filter_redirects=True)
        except pywikibot.exceptions.CircularRedirectError:
            pass
        else:
            for redirect in redirects:
                titles.add(self.__class__(redirect).title_regex(**kwargs))
        return "|".join(titles)


class BSiconPage(Page, pywikibot.FilePage):
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
            raise ValueError(f"'{self.title()}' is not a BSicon.")

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

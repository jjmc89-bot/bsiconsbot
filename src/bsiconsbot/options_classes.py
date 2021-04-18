"""Classes for working with commmand line arguments and json-cfg."""
# Author : JJMC89
# License: MIT
# pylint: disable=missing-class-docstring,too-few-public-methods
from typing import Any, Dict, Set

import pywikibot
import pywikibot.pagegenerators
from jsoncfg import JSONValueMapper
from jsoncfg.value_mappers import require_dict

import bsiconsbot.page


class TitleToPage:
    """Convert title to a page."""

    def __init__(self, site: pywikibot.site.APISite) -> None:
        """Initialize."""
        self.site = site

    def __call__(self, title: str) -> bsiconsbot.page.Page:
        """Make instance behave as a simple function."""
        return bsiconsbot.page.Page(self.site, title)


class _SiteJSONValueMapper(JSONValueMapper):
    def __init__(self, site: pywikibot.site.APISite) -> None:
        self.site = site

    def __call__(self, arg: object) -> Any:
        raise NotImplementedError


class GenToPages(_SiteJSONValueMapper):
    """Convert page generators to a set of pages."""

    def __init__(self, site: pywikibot.site.APISite) -> None:
        """Initialize."""
        super().__init__(site)
        self.gen_factory = pywikibot.pagegenerators.GeneratorFactory(site)

    def __call__(self, arg: object) -> Set[pywikibot.Page]:
        """Make instance behave as a simple function."""
        if not isinstance(arg, list):
            raise TypeError(f"{arg!r} is not an array.")
        for item in arg:
            if not isinstance(item, str):
                raise TypeError(f"{item!r} is not a string.")
            if not self.gen_factory.handle_arg(item):
                raise ValueError(f"{item!r} is not a page generator.")
        return set(self.gen_factory.getCombinedGenerator())


class ToReplacementMap(_SiteJSONValueMapper):
    """Convert to BSicons replacement map."""

    def __call__(self, arg: object) -> Dict[str, str]:
        """Make instance behave as a simple function."""
        if isinstance(arg, dict):
            replacement_map = arg
        elif isinstance(arg, str):
            page = bsiconsbot.page.Page(self.site, arg)
            replacement_map = page.get_json()(require_dict)
        else:
            raise TypeError(f"{arg!r} is not an object or string.")
        for value in replacement_map.values():
            if not isinstance(value, str):
                raise TypeError(f"{value!r} is not a string.")
        return replacement_map


class ToBSTemplatesConfig(_SiteJSONValueMapper):
    """Convert to BS temapltes config."""

    def __call__(self, arg: object) -> Dict[str, Set[pywikibot.Page]]:
        """Make instance behave as a simple function."""
        if isinstance(arg, str):
            value = {"": [arg]}
        elif isinstance(arg, list):
            value = {"": arg}
        elif isinstance(arg, dict):
            value = arg
        else:
            raise TypeError(f"{value!r} is not a string, array, or object.")
        tpl_map = {}
        for prefix, templates in value.items():
            if isinstance(templates, str):
                templates = [templates]
            elif not isinstance(templates, list):
                raise TypeError(f"{templates!r} is not a string or array.")
            tpl_map[prefix] = bsiconsbot.page.get_template_pages(
                [pywikibot.Page(self.site, tpl, 10) for tpl in templates]
            )
        return tpl_map


class ToTemplatesConfig(_SiteJSONValueMapper):
    """Convert to templates config."""

    def __call__(self, value: object) -> Set[pywikibot.Page]:
        """Make instance behave as a simple function."""
        if isinstance(value, str):
            value = [value]
        elif not isinstance(value, list):
            raise TypeError(f"{value!r} is not a string or array.")
        return bsiconsbot.page.get_template_pages(
            [pywikibot.Page(self.site, tpl, 10) for tpl in value]
        )

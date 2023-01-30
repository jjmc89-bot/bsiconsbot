"""Replace BSicons."""
# Author : JJMC89
# License: MIT
from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable  # pylint: disable=no-name-in-module
from dataclasses import dataclass
from itertools import chain
from re import Pattern
from typing import Any, TypedDict

import jsoncfg
import mwparserfromhell
import pywikibot
import pywikibot.pagegenerators
from jsoncfg.config_classes import ConfigJSONObject
from jsoncfg.value_mappers import require_list, require_string
from pywikibot.bot import (
    ExistingPageBot,
    FollowRedirectPageBot,
    MultipleSitesBot,
)
from pywikibot.textlib import removeDisabledParts
from pywikibot_extensions.page import Page

import bsiconsbot
import bsiconsbot.textlib
from bsiconsbot.options_classes import (
    GenToPages,
    ToBSTemplatesConfig,
    ToReplacementMap,
    ToTemplatesConfig,
)
from bsiconsbot.page import BSiconPage, load_config


HTML_COMMENT = re.compile(r"<!--.*?-->", flags=re.S)
ROUTEMAP_BSICON = re.compile(
    r"(?=((?:\n|! !|!~|\\)[ \t]*)((?:[^\\~\n]|~(?!~))+?)([ \t]*"
    r"(?:\n|!~|~~|!@|__|!_|\\)))"
)


class LocalConfig(TypedDict):
    """Local configuration."""

    bs_templates: dict[str, list[str]]
    railway_track_templates: list[str]
    routemap_templates: list[str]
    summary_prefix: str


@dataclass(frozen=True)
class SiteConfig:
    """Site configuration."""

    bs_templates: dict[str, set[pywikibot.Page]]
    file_regex: Pattern[str]
    railway_track_templates: set[pywikibot.Page]
    routemap_templates: set[pywikibot.Page]
    summary_prefix: str


@dataclass(frozen=True)
class Replacement:
    """A BSicon replacement."""

    old: BSiconPage
    new: BSiconPage

    def __str__(self) -> str:
        """Represent as a string."""
        return f"{self.old.name}\u2192{self.new.name}"


def process_local_config(config: ConfigJSONObject) -> LocalConfig:
    """Process the local config."""
    return LocalConfig(
        bs_templates=config.BS_templates({}),
        railway_track_templates=config.railway_track_templates([]),
        routemap_templates=config.routemap_templates([]),
        summary_prefix=config.summary_prefix("", require_string),
    )


def process_global_config(
    config: ConfigJSONObject, site: pywikibot.site.APISite
) -> tuple[
    Iterable[pywikibot.Page], dict[BSiconPage, BSiconPage], LocalConfig
]:
    """Process the global config."""
    redirects = config.redirects(set(), require_list, GenToPages(site))
    disallowlist = config.blacklist(set(), require_list, GenToPages(site))
    allowlist = config.whitelist(set(), require_list, GenToPages(site))
    bsicons_map = {}
    gen: Iterable[pywikibot.Page] = chain()
    for page in redirects - (disallowlist - allowlist):
        # Must be a redirect, and both must be BSicons.
        try:
            page = BSiconPage(page)
            bsicons_map[page] = BSiconPage(page.getRedirectTarget())
        except (ValueError, pywikibot.exceptions.IsNotRedirectPageError) as e:
            pywikibot.warning(e)
        else:
            gen = chain(gen, page.globalusage(), page.using_pages())  # T199398
    replacement_map = config.replacement_map({}, ToReplacementMap(site))
    for key, value in replacement_map.items():
        # Both must be BSicons.
        try:
            page = BSiconPage(site, key)
            bsicons_map[page] = BSiconPage(site, value)
        except ValueError as e:
            pywikibot.warning(e)
        else:
            gen = chain(gen, page.globalusage(), page.using_pages())  # T199398
    local_config = process_local_config(config)
    return gen, bsicons_map, local_config


def process_site_config(
    config: ConfigJSONObject, site: pywikibot.site.APISite
) -> SiteConfig:
    """Process the site config."""
    file_namespaces = "|".join(site.namespaces.FILE)
    site_config = SiteConfig(
        bs_templates=config.bs_templates(ToBSTemplatesConfig(site)),
        file_regex=re.compile(
            bsiconsbot.textlib.FILE_LINK_REGEX.format(file_namespaces),
            flags=re.I | re.X,
        ),
        railway_track_templates=config.railway_track_templates(
            ToTemplatesConfig(site)
        ),
        routemap_templates=config.routemap_templates(ToTemplatesConfig(site)),
        summary_prefix=config.summary_prefix(),
    )
    if not (
        site_config.bs_templates
        or site_config.railway_track_templates
        or site_config.routemap_templates
    ):
        raise ValueError("Missing templtes.")
    return site_config


class BSiconsReplacer(
    MultipleSitesBot, FollowRedirectPageBot, ExistingPageBot
):
    """Bot to replace BSicons."""

    update_options = {
        "bsicons_map": {},
        "config": {},
        "local_config": "",
    }

    def __init__(self, **kwargs: Any) -> None:
        """Initialize."""
        super().__init__(**kwargs)
        self._config: dict[pywikibot.site.APISite, SiteConfig | None] = {}
        self._disabled_sites: set[pywikibot.site.APISite] = set()

    @property
    def site_disabled(self) -> bool:
        """Return True if the task is disabled on the site."""
        site = self.current_page.site
        if site in self._disabled_sites:
            return True
        if not site.logged_in():
            site.login()
        class_name = self.__class__.__name__
        page = Page(
            site,
            f"User:{site.user()}/shutoff/{class_name}.json",
        )
        if page.exists():
            content = page.get(force=True).strip()
            if content:
                pywikibot.warning(
                    f"{class_name} disabled on {site}:\n{content}"
                )
                self._disabled_sites.add(site)
                return True
        return False

    @property
    def site_config(self) -> SiteConfig | None:
        """Return the site configuration."""
        site = self.current_page.site
        if site in self._config:
            return self._config[site]
        try:
            config_json = load_config(Page(site, self.opt.local_config))
            config_dict1 = process_local_config(config_json)
            config_dict2 = {k: v for k, v in config_dict1.items() if v}
            config_str = json.dumps({**self.opt.config, **config_dict2})
            config_json = jsoncfg.loads_config(config_str)
            self._config[site] = process_site_config(config_json, site)
        except (
            ValueError,
            jsoncfg.JSONConfigException,
            pywikibot.exceptions.Error,
        ) as e:
            pywikibot.error(f"Invalid config for {site}.")
            pywikibot.log(e)
            self._config[site] = None
        return self._config[site]

    def skip_page(self, page: pywikibot.Page) -> bool:
        """Sikp the page if it is in userspace."""
        if page.namespace().id in {2, 3}:
            pywikibot.warning(f"{page!r} is in userspace.")
            return True
        return super().skip_page(page)

    def treat_page(self) -> None:
        """Process one page."""
        if not self.site_config or self.site_disabled:
            return
        self.current_page.replacements = set()
        text, mask = bsiconsbot.textlib.mask_html_tags(self.current_page.text)
        text = self.replace_file_links(text)
        text = bsiconsbot.textlib.mask_pipe_mw(text)
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)
        self.replace_gallery_files(wikicode)
        self.replace_template_files(wikicode)
        self.put_current(
            bsiconsbot.textlib.unmask_text(str(wikicode), mask),
            summary=(
                f"{self.site_config.summary_prefix}: "
                f"{', '.join(map(str, self.current_page.replacements))}",
            ),
        )

    def replace_file_links(self, text: str) -> str:
        """
        Return text with file links replaced.

        :param text: Article text
        """
        assert self.site_config is not None
        for match in self.site_config.file_regex.finditer(
            removeDisabledParts(text)
        ):
            try:
                current_icon = BSiconPage(
                    self.current_page.site, match.group("filename")
                )
                current_icon.title()
            except (pywikibot.exceptions.Error, ValueError):
                continue
            new_icon = self.opt.bsicons_map.get(current_icon, None)
            if new_icon:
                text = text.replace(
                    match.group("filename"), new_icon.title(with_ns=False)
                )
                self.current_page.replacements.add(
                    Replacement(current_icon, new_icon)
                )
        return text

    def replace_gallery_files(
        self, wikicode: mwparserfromhell.wikicode.Wikicode
    ) -> None:
        """
        Replace files in <gallery>.

        :param wikicode: Parsed wikitext
        """
        for tag in wikicode.ifilter_tags():
            if tag.tag.lower() != "gallery":
                continue
            lines = str(tag.contents).splitlines()
            for i, line in enumerate(lines):
                title, sep, caption = removeDisabledParts(line).partition("|")
                if not title:
                    continue
                try:
                    current_icon = BSiconPage(self.current_page.site, title)
                    current_icon.title()
                except (pywikibot.exceptions.Error, ValueError):
                    continue
                new_icon = self.opt.bsicons_map.get(current_icon, None)
                if new_icon:
                    lines[i] = f"{new_icon.title()}{sep}{caption}"
                    self.current_page.replacements.add(
                        Replacement(current_icon, new_icon)
                    )
            if self.current_page.replacements:
                tag.contents = "\n".join(lines) + "\n"

    def replace_template_files(
        self, wikicode: mwparserfromhell.wikicode.Wikicode
    ) -> None:
        """
        Replace files in templates.

        :param wikicode: Parsed wikitext
        """
        assert self.site_config is not None
        for tpl in wikicode.ifilter_templates():
            try:
                template = Page(
                    self.current_page.site,
                    removeDisabledParts(str(tpl.name)),
                    ns=self.current_page.site.namespaces.TEMPLATE,
                )
                template.title()
            except (pywikibot.exceptions.Error, ValueError):
                continue
            if template in self.site_config.routemap_templates:
                self._replace_routemap_files(tpl)
            elif template in self.site_config.railway_track_templates:
                self._replace_rt_template_files(tpl)
            else:
                self._replace_bs_template_files(tpl, template)

    def _replace_routemap_files(
        self, tpl: mwparserfromhell.nodes.Template
    ) -> None:
        for param in tpl.params:
            if not re.search(r"^(?:map\d*|\d+)$", str(param.name).strip()):
                continue
            param_value = str(param.value)
            for match in ROUTEMAP_BSICON.findall(param_value):
                current_name = HTML_COMMENT.sub("", match[1]).strip()
                try:
                    current_icon = BSiconPage(
                        self.current_page.site, name=current_name
                    )
                    current_icon.title()
                except (pywikibot.exceptions.Error, ValueError):
                    continue
                new_icon = self.opt.bsicons_map.get(current_icon, None)
                if not new_icon:
                    continue
                param_value = param_value.replace(
                    "".join(match),
                    match[0]
                    + match[1].replace(current_name, new_icon.name)
                    + match[2],
                )
                self.current_page.replacements.add(
                    Replacement(current_icon, new_icon)
                )
            param.value = param_value

    def _replace_rt_template_files(
        self, tpl: mwparserfromhell.nodes.Template
    ) -> None:
        # Written for [[:cs:Template:Železniční trať]].
        for param in tpl.params:
            param_value = HTML_COMMENT.sub("", str(param.value)).strip()
            if param.name.matches("typ"):
                if param_value[:2] == "ex":
                    current_name = "exl" + param_value[2:]
                else:
                    current_name = "l" + param_value
            else:
                current_name = param_value
            try:
                current_icon = BSiconPage(
                    self.current_page.site, name=current_name
                )
                current_icon.title()
            except (pywikibot.exceptions.Error, ValueError):
                continue
            new_icon = self.opt.bsicons_map.get(current_icon, None)
            if not new_icon:
                continue
            if param.name.matches("typ"):
                if new_icon.name[:3] == "exl":
                    replacement = "ex" + new_icon.name[3:]
                elif new_icon.name[:1] == "l":
                    replacement = new_icon.name[1:]
                else:
                    pywikibot.log(f"{new_icon} cannot be used in |typ=.")
                    continue
            else:
                replacement = new_icon.name
            param.value = str(param.value).replace(param_value, replacement)
            self.current_page.replacements.add(
                Replacement(current_icon, new_icon)
            )

    def _replace_bs_template_files(
        self, tpl: mwparserfromhell.nodes.Template, template: pywikibot.Page
    ) -> None:
        assert self.site_config is not None
        for icon_prefix, templates in self.site_config.bs_templates.items():
            if template not in templates:
                continue
            for param in tpl.params:
                if param.name.matches("1"):
                    prefix = icon_prefix.strip()
                else:
                    prefix = ""
                param_value = HTML_COMMENT.sub("", str(param.value)).strip()
                try:
                    current_icon = BSiconPage(
                        self.current_page.site, name=prefix + param_value
                    )
                    current_icon.title()
                except (pywikibot.exceptions.Error, ValueError):
                    continue
                new_icon = self.opt.bsicons_map.get(current_icon, None)
                if not new_icon:
                    continue
                # The replacement must have the same prefix.
                if new_icon.name[: len(prefix)] == prefix:
                    param.value = str(param.value).replace(
                        param_value, new_icon.name[len(prefix) :]  # noqa: E203
                    )
                    self.current_page.replacements.add(
                        Replacement(current_icon, new_icon)
                    )


def transcluded_add_generator(
    generator: Iterable[pywikibot.Page],
) -> Iterable[pywikibot.Page]:
    """Add transcluded pages for pages from another generator."""
    seen = set()
    for page in generator:
        yield page
        for tpl in page.itertemplates():
            if tpl not in seen:
                seen.add(tpl)
                yield tpl


def main(*args: str) -> int:
    """
    Process command line arguments and invoke bot.

    :param args: command line arguments
    """
    local_args = pywikibot.handle_args(args, do_help=False)
    site = pywikibot.Site()
    gen_factory = pywikibot.pagegenerators.GeneratorFactory(site)
    script_args = gen_factory.handle_args(local_args)
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=bsiconsbot.PYWIKIBOT_GLOBAL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument(
        "config",
        help=(
            "page title that has the JSON config (object) on Wikimedia "
            "Commons.\nValues in the object can be overwritten by a value "
            "in the local config."
        ),
    )
    parser.add_argument(
        "--local-config",
        help=(
            "page title that has the JSON config (object) on the local site.\n"
            "Values in the object will overwrite the (global) config.\n"
            "defaults to the global config"
        ),
    )
    parser.add_argument(
        "--always",
        action="store_true",
        help="do not prompt to save changes",
    )
    parser.add_argument(
        "--transcluded",
        action="store_true",
        help="also work on transcluded pages",
    )
    parsed_args = parser.parse_args(args=script_args)
    site.login()
    json_config = load_config(Page(site, parsed_args.config))
    gen, bsicons_map, config = process_global_config(json_config, site)
    if parsed_args.transcluded:
        gen = transcluded_add_generator(gen)
    BSiconsReplacer(
        always=parsed_args.always,
        bsicons_map=bsicons_map,
        config=config,
        generator=gen_factory.getCombinedGenerator(gen=gen, preload=True),
        local_config=parsed_args.local_config or parsed_args.config,
    ).run()
    return 0

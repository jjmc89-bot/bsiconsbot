#!/usr/bin/env python3
"""
This script replaces BSicons.


The following arguments are required:

-config           The page title that has the JSON config (object).
                  This page must be on Wikimedia Commons. Any value in the
                  object can be overwritten by a value in the object from
                  -local_config.

The following arguments are supported:

-always           Don't prompt to save changes.

-local_config     The page title that has the JSON config (object).
                  Any value in the object will overwrite the corresponding
                  value in the object from -config.
                  If not provided, it will be the same as -config.

-transcluded      Also work on pages transcluded into the pages with BSicons.

&params;
"""
# Author : JJMC89
# License: MIT
# pylint: disable=too-many-branches
import copy
import re
from itertools import chain

import mwparserfromhell
import pywikibot
from pywikibot import pagegenerators
from pywikibot.bot import (
    ExistingPageBot,
    FollowRedirectPageBot,
    MultipleSitesBot,
)
from pywikibot.textlib import removeDisabledParts

import bsiconsbot.page
import bsiconsbot.textlib

docuReplacements = {  # pylint: disable=invalid-name
    "&params;": pagegenerators.parameterHelp
}
HTML_COMMENT = re.compile(r"<!--.*?-->", flags=re.S)
ROUTEMAP_BSICON = re.compile(
    r"(?=((?:\n|! !|!~|\\)[ \t]*)((?:[^\\~\n]|~(?!~))+?)([ \t]*"
    r"(?:\n|!~|~~|!@|__|!_|\\)))"
)


def process_options(options, site):
    """
    Process the options and return a generator of pages to work on.

    @param options: options to process
    @type options: dict
    @param site: site used during processing
    @type site: L{pywikibot.Site}

    @rtype: generator
    """
    bsicons_map = dict()
    gen = chain()
    for page in options["config"].pop("redirects"):
        # Must be a redirect, and both must be BSicons.
        try:
            page = bsiconsbot.page.BSiconPage(page)
            bsicons_map[page] = bsiconsbot.page.BSiconPage(
                page.getRedirectTarget()
            )
        except (pywikibot.exceptions.IsNotRedirectPageError, ValueError) as e:
            pywikibot.warning(e)
            continue
        gen = chain(gen, page.globalusage(), page.usingPages())  # T199398
    for key, value in options["config"].pop("replacement_map", dict()).items():
        # Both must be BSicons.
        try:
            page = bsiconsbot.page.BSiconPage(site, key)
            bsicons_map[page] = bsiconsbot.page.BSiconPage(site, value)
        except ValueError as e:
            pywikibot.warning(e)
            continue
        gen = chain(gen, page.globalusage(), page.usingPages())  # T199398
    options["bsicons_map"] = bsicons_map
    return gen


def transcluded_add_generator(generator):
    """
    Add transcluded pages for pages from another generator.

    @param generator: Pages to iterate over
    @type generator: iterable

    @rtype: generator
    """
    seen = set()
    for page in generator:
        yield page
        for tpl in page.itertemplates():
            if tpl not in seen:
                seen.add(tpl)
                yield tpl


def validate_config(config, site):
    """
    Validate the config and return bool.

    @param config: config to validate
    @type config: dict
    @param site: site used in the validation
    @type site: L{pywikibot.Site}

    @rtype: bool
    """
    pywikibot.log("Config:")
    required_keys = ["redirects"]
    has_keys = list()
    for key, value in config.items():
        pywikibot.log(f"-{key} = {value}")
        if key in required_keys:
            has_keys.append(key)
        if key in ("blacklist", "redirects", "whitelist"):
            if isinstance(value, str):
                config[key] = [value]
            elif not isinstance(value, list):
                pywikibot.log("Invalid type.")
                return False
        pywikibot.log(f"\u2192{key} = {config[key]}")
    if sorted(has_keys) != sorted(required_keys):
        pywikibot.log("Missing one more required keys.")
        return False
    for key in ("blacklist", "redirects", "whitelist"):
        if key in config:
            generator_factory = pagegenerators.GeneratorFactory(site)
            for item in config[key]:
                if not generator_factory.handle_arg(item):
                    pywikibot.log("Invalid generator.")
                    return False
            gen = generator_factory.getCombinedGenerator()
            config[key] = set(gen)
        else:
            config[key] = set()
    config["redirects"] = frozenset(
        config.pop("redirects")
        - (config.pop("blacklist") - config.pop("whitelist"))
    )
    replacement_map = config.pop("replacement_map", dict())
    if isinstance(replacement_map, str):
        page = bsiconsbot.page.Page(site, replacement_map)
        replacement_map = page.get_json()
    elif not isinstance(replacement_map, dict):
        replacement_map = dict()
    for value in replacement_map.values():
        if not isinstance(value, str):
            pywikibot.log("Invalid type.")
            return False
    config["replacement_map"] = replacement_map
    return True


def validate_local_config(config, site):
    """
    Validate the local config and return bool.

    @param config: config to validate
    @type config: dict
    @param site: site used in the validation
    @type site: L{pywikibot.Site}

    @rtype: bool
    """
    result = True
    pywikibot.log(f"Config for {site}:")
    required_keys = ["summary_prefix"]
    has_keys = list()
    for key, value in config.items():
        pywikibot.log(f"-{key} = {value}")
        if key in required_keys:
            has_keys.append(key)
        if key == "BS_templates":
            if isinstance(value, str):
                config[key] = {"": [value]}
            elif isinstance(value, list):
                config[key] = {"": value}
            elif not isinstance(value, dict):
                pywikibot.log("Invalid type.")
                result = False
            tpl_map = dict()
            for prefix, templates in config[key].items():
                if isinstance(templates, str):
                    templates = [templates]
                elif not isinstance(templates, list):
                    pywikibot.log("Invalid type.")
                    result = False
                tpl_map[prefix] = bsiconsbot.page.get_template_pages(
                    [
                        pywikibot.Page(site, tpl, site.namespaces.TEMPLATE)
                        for tpl in templates
                    ]
                )
            config[key] = tpl_map
        elif key in ("railway_track_templates", "routemap_templates"):
            if isinstance(value, str):
                config[key] = [value]
            elif not isinstance(value, list):
                pywikibot.log("Invalid type.")
                result = False
            config[key] = bsiconsbot.page.get_template_pages(
                [
                    pywikibot.Page(site, tpl, site.namespaces.TEMPLATE)
                    for tpl in config[key]
                ]
            )
        elif key == "summary_prefix":
            if not isinstance(value, str):
                pywikibot.log("Invalid type.")
                result = False
        pywikibot.log(f"\u2192{key} = {config[key]}")
    if sorted(has_keys) != sorted(required_keys):
        pywikibot.log("Missing one more required keys.")
        result = False
    if "BS_templates" not in config:
        config["BS_templates"] = dict()
    if "railway_track_templates" not in config:
        config["railway_track_templates"] = set()
    if "routemap_templates" not in config:
        config["routemap_templates"] = set()
    if not (
        config["BS_templates"]
        or config["railway_track_templates"]
        or config["routemap_templates"]
    ):
        pywikibot.log("Missing templates.")
        result = False
    return result


class Replacement:
    """A BSicon replacement."""

    def __init__(self, old, new):
        """Initializer."""
        for item in (old, new):
            if not isinstance(item, bsiconsbot.page.BSiconPage):
                raise ValueError(f"{item} is not a BSicon.")
        self._old = old
        self._new = new

    def __str__(self):
        """String representation."""
        return "\u2192".join([self.old.name, self.new.name])

    def __repr__(self):
        """Complete string representation."""
        return "{}({} with {})".format(
            self.__class__.__name__, repr(self.old), repr(self.new)
        )

    def __eq__(self, other):
        """Test if two replacements are equal."""
        return self.old == other.old and self.new == other.new

    def __hash__(self):
        """A stable identifier to used in hash tables."""
        return hash((self.old, self.new))

    @property
    def old(self):
        """Return the old BSicon."""
        return self._old

    @property
    def new(self):
        """Return the new BSicon."""
        return self._new


class BSiconsReplacer(
    MultipleSitesBot, FollowRedirectPageBot, ExistingPageBot
):
    """Bot to replace BSicons."""

    def __init__(self, generator, **kwargs):
        """
        Initializer.

        @param generator: the page generator that determines on which
            pages to work
        @type generator: generator
        """
        self.available_options.update(
            {"bsicons_map": dict(), "config": dict(), "local_config": None}
        )
        self.generator = generator
        super().__init__(**kwargs)
        self._config = dict()
        self._disabled = set()

    @property
    def site_disabled(self):
        """True if the task is disabled on the site."""
        site = self.current_page.site
        if site in self._disabled:
            return True
        if not site.logged_in():
            site.login()
        page = pywikibot.Page(
            site,
            "User:{username}/shutoff/{class_name}.json".format(
                username=site.user(), class_name=self.__class__.__name__
            ),
        )
        if page.exists():
            content = page.get(force=True).strip()
            if content:
                pywikibot.warning(
                    "{} disabled on {}:\n{}".format(
                        self.__class__.__name__, site, content
                    )
                )
                self._disabled.add(site)
                return True
        return False

    @property
    def site_config(self):
        """Return the site configuration."""
        site = self.current_page.site
        if site not in self._config:
            self._config[site] = copy.deepcopy(self.opt.config)
            self._config[site].update(
                bsiconsbot.page.Page(site, self.opt.local_config).get_json()
            )
            file_namespaces = "".join(
                [
                    "[" + c + c.swapcase() + "]" if c.isalpha() else c
                    for c in "|".join(site.namespaces.FILE)
                ]
            )
            self._config[site]["file_regex"] = re.compile(
                bsiconsbot.textlib.FILE_LINK_REGEX.format(file_namespaces),
                flags=re.X,
            )
            if not validate_local_config(self._config[site], site):
                pywikibot.error(f"Invalid config for {site}.")
                self._config[site] = None
        return self._config[site]

    def skip_page(self, page):
        """Sikp the page if it is in userspace."""
        if page.namespace().id in {2, 3}:
            pywikibot.warning(f"{page} is in userspace.")
            return True
        return super().skip_page(page)

    def treat_page(self):
        """Process one page."""
        if not self.site_config or self.site_disabled:
            return
        text, mask = bsiconsbot.textlib.mask_html_tags(self.current_page.text)
        text = self.replace_file_links(text)
        text = bsiconsbot.textlib.mask_pipe_mw(text)
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)
        self.replace_gallery_files(wikicode)
        self.replace_template_files(wikicode)
        self.put_current(
            bsiconsbot.textlib.unmask_text(str(wikicode), mask),
            summary="{}: {}".format(
                self.site_config["summary_prefix"],
                ", ".join(map(str, self.current_page.replacements)),
            ),
        )

    def replace_file_links(self, text):
        """
        Return text with file links replaced.

        @param text: Article text
        @type text: str

        @rtype: str
        """
        if not hasattr(self.current_page, "replacements"):
            self.current_page.replacements = set()
        for match in self.site_config["file_regex"].finditer(
            removeDisabledParts(text)
        ):
            try:
                current_icon = bsiconsbot.page.BSiconPage(
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

    def replace_gallery_files(self, wikicode):
        """
        Replaces files in <gallery>.

        @param wikicode: Parsed wikitext
        @type wikicode: L{mwparserfromhell.wikicode.Wikicode}
        """
        if not hasattr(self.current_page, "replacements"):
            self.current_page.replacements = set()
        for tag in wikicode.ifilter_tags():
            if tag.tag.lower() != "gallery":
                continue
            lines = str(tag.contents).splitlines()
            for i, line in enumerate(lines):
                title, sep, caption = removeDisabledParts(line).partition("|")
                if not title:
                    continue
                try:
                    current_icon = bsiconsbot.page.BSiconPage(
                        self.current_page.site, title
                    )
                    current_icon.title()
                except (pywikibot.exceptions.Error, ValueError):
                    continue
                new_icon = self.opt.bsicons_map.get(current_icon, None)
                if new_icon:
                    lines[i] = new_icon.title() + sep + caption
                    self.current_page.replacements.add(
                        Replacement(current_icon, new_icon)
                    )
            if self.current_page.replacements:
                tag.contents = "\n".join(lines) + "\n"

    def replace_template_files(self, wikicode):
        """
        Replace files in templates.

        @param wikicode: Parsed wikitext
        @type wikicode: L{mwparserfromhell.wikicode.Wikicode}
        """
        if not hasattr(self.current_page, "replacements"):
            self.current_page.replacements = set()
        for tpl in wikicode.ifilter_templates():
            try:
                template = pywikibot.Page(
                    self.current_page.site,
                    removeDisabledParts(str(tpl.name)),
                    ns=self.current_page.site.namespaces.TEMPLATE,
                )
                template.title()
            except (pywikibot.exceptions.Error, ValueError):
                continue
            if template in self.site_config["routemap_templates"]:
                self._replace_routemap_files(tpl)
            elif template in self.site_config["railway_track_templates"]:
                self._replace_rt_template_files(tpl)
            else:
                self._replace_bs_template_files(tpl, template)

    def _replace_routemap_files(self, tpl):
        """Helper method for replace_template_files()."""
        for param in tpl.params:
            if not re.search(r"^(?:map\d*|\d+)$", str(param.name).strip()):
                continue
            param_value = str(param.value)
            for match in ROUTEMAP_BSICON.findall(param_value):
                current_name = HTML_COMMENT.sub("", match[1]).strip()
                try:
                    current_icon = bsiconsbot.page.BSiconPage(
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

    def _replace_rt_template_files(self, tpl):
        """Helper method for replace_template_files()."""
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
                current_icon = bsiconsbot.page.BSiconPage(
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
                    pywikibot.log(
                        f"{new_icon} cannot be used in |typ=."
                    )
                    continue
            else:
                replacement = new_icon.name
            param.value = str(param.value).replace(param_value, replacement)
            self.current_page.replacements.add(
                Replacement(current_icon, new_icon)
            )

    def _replace_bs_template_files(self, tpl, template):
        """Helper method for replace_template_files()."""
        for icon_prefix, templates in self.site_config["BS_templates"].items():
            if template not in templates:
                continue
            for param in tpl.params:
                if param.name.matches("1"):
                    prefix = icon_prefix.strip()
                else:
                    prefix = ""
                param_value = HTML_COMMENT.sub("", str(param.value)).strip()
                try:
                    current_icon = bsiconsbot.page.BSiconPage(
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
                        param_value, new_icon.name[len(prefix) :]
                    )
                    self.current_page.replacements.add(
                        Replacement(current_icon, new_icon)
                    )


def main(*args):
    """
    Process command line arguments and invoke bot.

    @param args: command line arguments
    @type args: list of unicode
    """
    options = {"transcluded": False}
    local_args = pywikibot.handle_args(args)
    site = pywikibot.Site()
    site.login()
    gen_factory = pagegenerators.GeneratorFactory(site)
    script_args = gen_factory.handle_args(local_args)
    for arg in script_args:
        arg, _, value = arg.partition(":")
        arg = arg[1:]
        if arg in ("config", "local_config"):
            if not value:
                value = pywikibot.input(
                    f"Please enter a value for {arg}", default=None
                )
            options[arg] = value
        else:
            options[arg] = True
    if "config" not in options:
        pywikibot.bot.suggest_help(missing_parameters=["config"])
        return False
    if "local_config" not in options:
        options["local_config"] = options["config"]
    config = bsiconsbot.page.Page(site, options.pop("config")).get_json()
    if validate_config(config, site):
        options["config"] = config
    else:
        pywikibot.error("Invalid config.")
        return False
    gen = process_options(options, site)
    if options.pop("transcluded"):
        gen = transcluded_add_generator(gen)
    gen = gen_factory.getCombinedGenerator(gen=gen, preload=True)
    BSiconsReplacer(gen, **options).run()
    return True


if __name__ == "__main__":
    main()

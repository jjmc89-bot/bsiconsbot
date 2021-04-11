#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script generates BSicon reports.

    - Output changes to BSicons
    - List BSicon redirects
    - List large BSicons

The following parameters are required:

-config           The page title that has the JSON config (object).
                  Options set in the config override those provided when
                  running this script.

The following parameters are supported:

-changes_date     The table of changes is added for this date. The default
                  is yesterday.

-changes_page_prefix Title prefix of the page to save the file changes

-redirects_page   Title of the page to save the redirects list

-list_summary     Edit summary to use when updating one the lists

-large_size       Files over this size will be included in the large files
                  list

-large_page       Title of the page to save the large files list
"""
# Author : JJMC89
# License: MIT
# pylint: disable=too-many-branches
import datetime
import sys
from datetime import date, time, timedelta

import pywikibot
from pywikibot import pagegenerators

import bsiconsbot.page
from bsiconsbot.textlib import get_headers


def get_page_from_size(page, size=1e6):
    """Return a page based on the current page size."""
    i = 1
    title = page.title()
    while True:
        if not page.exists():
            break
        if len(page.text) < size:
            break
        i += 1
        page = pywikibot.Page(page.site, "{} ({:02d})".format(title, i))
    return page


def validate_options(options):
    """
    Validate the options and return bool.

    @param options: options to validate
    @type options: dict

    @rtype: bool
    """
    result = True
    pywikibot.log("Options:")
    required_keys = [
        "changes_date",
        "changes_page_prefix",
        "enabled",
        "list_summary",
        "large_page",
        "large_size",
        "redirects_page",
        "logs_page_prefix",
    ]
    has_keys = list()
    if "changes_date" in options:
        value = options["changes_date"]
        if isinstance(value, datetime.date):
            pass
        elif isinstance(value, str):
            try:
                value = datetime.datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                pywikibot.error("Date format must be YYYY-MM-DD.")
                return False
        else:
            return False
        options["changes_date"] = value
    else:
        return False
    for key, value in options.items():
        pywikibot.log("-{} = {}".format(key, value))
        if key in required_keys:
            has_keys.append(key)
        if key in ("changes_page_prefix", "list_summary", "logs_page_prefix"):
            if not isinstance(value, str):
                result = False
        elif key == "enabled":
            if not isinstance(value, bool):
                result = False
            elif value is not True:
                sys.exit("Task disabled.")
        elif key in ("large_page", "redirects_page"):
            if isinstance(value, str):
                options[key] = bsiconsbot.page.Page(options["site"], value)
            else:
                result = False
        elif key == "large_size":
            try:
                options[key] = int(value)
            except ValueError:
                result = False
    if sorted(has_keys) != sorted(required_keys):
        result = False
    return result


def save_list(page_list, page, summary):
    """
    Writes the given page_list to the given page.

    @param page_list: List of pages to output
    @type page_list: list of L{pywikibot.Page}
    @param page: Page to save to
    @type page: L{bsiconsbot.page.Page}
    @param summary: Edit summary
    @type summary: str
    """
    list_text = ""
    for item in sorted(page_list):
        list_text += "\n# {}".format(item.title(asLink=True, textlink=True))
    try:
        page.save_bot_start_end(list_text, summary=summary, force=True)
    except Exception as e:  # pylint: disable=broad-except
        pywikibot.exception(e, tb=True)


def output_log(logtype=None, options=None, bsicon_template_title="bsq2"):
    """
    Writes logevents to a page.

    @param logtype: The logtype to output
    @type logtype: str
    @param options: Validated options
    @type options: dict
    @param bsicon_template_title: Title of BSicon template to use
    @type bsicon_template_title: str
    """
    log_page = pywikibot.Page(
        options["site"],
        "{prefix}/{type}/{subpage}".format(
            prefix=options["logs_page_prefix"],
            type=logtype,
            subpage=options["changes_date"].strftime("%Y-%m"),
        ),
    )
    if options["changes_date"].isoformat() in get_headers(log_page.text):
        return
    log_page = get_page_from_size(log_page)
    if options["changes_date"].isoformat() in get_headers(log_page.text):
        return
    if not log_page.exists():
        log_page.save(
            text="{{{{nobots}}}}{{{{{prefix}}}}}".format(
                prefix=options["logs_page_prefix"]
            ),
            summary="Create log page",
        )
    log_text = ""
    for logevent in options["site"].logevents(
        logtype=logtype,
        namespace=options["site"].namespaces.FILE.id,
        start=options["start"],
        end=options["end"],
        reverse=True,
    ):
        try:
            bsicon = bsiconsbot.page.BSiconPage(logevent.page())
        except ValueError:
            continue
        log_text += (
            "\n|-\n| {{{{{tpl}|{name}}}}} || {r[logid]} || {r[timestamp]} "
            "|| {r[user]} || <nowiki>{r[comment]}</nowiki>".format(
                tpl=bsicon_template_title, name=bsicon.name, r=logevent.data
            )
        )
    if log_text:
        log_text = (
            '{{| class="wikitable sortable mw-collapsible mw-collapsed"'
            "\n! BSicon !! logid !! Date/time !! User !! Summary"
            "{body}\n|}}".format(body=log_text)
        )
    else:
        log_text = ": None"
    try:
        log_page.save(
            text=log_text,
            section="new",
            summary=options["changes_date"].isoformat(),
            minor=False,
            force=True,
        )
    except Exception as e:  # pylint: disable=broad-except
        pywikibot.exception(e, tb=True)


def output_move_log(options=None):
    """
    Writes move logevents to a page.

    @param options: Validated options
    @type options: dict
    """
    logtype = "move"
    log_page = pywikibot.Page(
        options["site"],
        "{prefix}/{type}/{subpage}".format(
            prefix=options["logs_page_prefix"],
            type=logtype,
            subpage=options["changes_date"].strftime("%Y-%m"),
        ),
    )
    if options["changes_date"].isoformat() in get_headers(log_page.text):
        return
    log_page = get_page_from_size(log_page)
    if options["changes_date"].isoformat() in get_headers(log_page.text):
        return
    if not log_page.exists():
        log_page.save(
            text="{{{{nobots}}}}{{{{{prefix}}}}}".format(
                prefix=options["logs_page_prefix"]
            ),
            summary="Create log page",
        )
    log_text = ""
    for logevent in options["site"].logevents(
        logtype=logtype,
        namespace=options["site"].namespaces.FILE.id,
        start=options["start"],
        end=options["end"],
        reverse=True,
    ):
        page = logevent.page()
        try:
            page = bsiconsbot.page.BSiconPage(page)
        except ValueError:
            is_bsicon = False
        else:
            is_bsicon = True
        target = logevent.target_page
        try:
            target = bsiconsbot.page.BSiconPage(target)
        except ValueError:
            target_is_bsicon = False
        else:
            target_is_bsicon = True
        if not (is_bsicon or target_is_bsicon):
            continue
        log_text += "\n|-\n| "
        if is_bsicon:
            log_text += "{{{{bsn|{name}}}}}".format(name=page.name)
        else:
            log_text += page.title(asLink=True, textlink=True)
        log_text += " || "
        if target_is_bsicon:
            log_text += "{{{{bsq2|{name}}}}}".format(name=target.name)
        else:
            log_text += target.title(asLink=True, textlink=True)
        log_text += (
            " || {r[logid]} || {r[timestamp]} || {r[user]} || "
            "<nowiki>{r[comment]}</nowiki>".format(r=logevent.data)
        )
    if log_text:
        log_text = (
            '{{| class="wikitable sortable mw-collapsible mw-collapsed"'
            "\n! Page !! Target !! logid !! Date/time !! User !! Summary"
            "{body}\n|}}".format(body=log_text)
        )
    else:
        log_text = ": None"
    try:
        log_page.save(
            text=log_text,
            section="new",
            summary=options["changes_date"].isoformat(),
            minor=False,
            force=True,
        )
    except Exception as e:  # pylint: disable=broad-except
        pywikibot.exception(e, tb=True)


def output_edits(options=None):
    """
    Writes edits to a page.

    @param options: Validated options
    @type options: dict
    """
    changes_page = pywikibot.Page(
        options["site"],
        "{prefix}/{subpage}".format(
            prefix=options["changes_page_prefix"],
            subpage=options["changes_date"].strftime("%Y-%m"),
        ),
    )
    if options["changes_date"].isoformat() in get_headers(changes_page.text):
        return
    changes_page = get_page_from_size(changes_page)
    if options["changes_date"].isoformat() in get_headers(changes_page.text):
        return
    if not changes_page.exists():
        changes_page.save(
            text="{{{{nobots}}}}{{{{{prefix}}}}}".format(
                prefix=options["changes_page_prefix"]
            ),
            summary="Create changes page",
        )
    file_changes = ""
    for recent_change in options["site"].recentchanges(
        start=options["start"],
        end=options["end"],
        reverse=True,
        namespaces=options["site"].namespaces.FILE,
        changetype="edit|new",
    ):
        try:
            file = bsiconsbot.page.BSiconPage(
                options["site"], recent_change["title"]
            )
        except (KeyError, ValueError):
            continue
        if not file.exists():
            continue
        # Fill in placeholders for hidden keys.
        for prop in ("comment", "user"):
            if prop + "hidden" in recent_change:
                recent_change[prop] = "({} hidden)".format(prop)
        file_changes += (
            "\n|-\n| {{{{bsq2|{name}}}}} || {rc[revid]} || {rc[timestamp]} || "
            "{rc[user]} || <nowiki>{rc[comment]}</nowiki>".format(
                name=file.name, rc=recent_change
            )
        )
    if file_changes:
        file_changes = (
            '{{| class="wikitable sortable mw-collapsible mw-collapsed"'
            "\n! BSicon !! revid !! Date/time !! User !! Summary"
            "{body}\n|}}".format(body=file_changes)
        )
    else:
        file_changes = ": No changes"
    try:
        changes_page.save(
            text=file_changes,
            section="new",
            summary=options["changes_date"].isoformat(),
            minor=False,
            force=True,
        )
    except Exception as e:  # pylint: disable=broad-except
        pywikibot.exception(e, tb=True)


def main(*args):
    """
    Process command line arguments and invoke bot.

    @param args: command line arguments
    @type args: list of unicode
    """
    options = {
        "enabled": False,
        "changes_date": date.today() - timedelta(days=1),
        "large_size": 1000,
        "list_summary": "Updating list",
    }
    local_args = pywikibot.handle_args(args)
    options["site"] = pywikibot.Site()
    options["site"].login()
    gen_factory = pagegenerators.GeneratorFactory()
    script_args = gen_factory.handle_args(local_args)
    for arg in script_args:
        arg, _, value = arg.partition(":")
        arg = arg[1:]
        if arg in (
            "config",
            "changes_date",
            "changes _page_prefix",
            "redirects_page",
            "large_size",
            "large_page",
            "list_summary",
            "logs_page_prefix",
        ):
            if not value:
                value = pywikibot.input(
                    "Please enter a value for {}".format(arg), default=None
                )
            options[arg] = value
        else:
            options[arg] = True
    if "config" in options:
        options.update(
            bsiconsbot.page.Page(
                options["site"], options.pop("config")
            ).get_json()
        )
    else:
        pywikibot.bot.suggest_help(missing_parameters=["config"])
        return False
    if not validate_options(options):
        pywikibot.error("Invalid options.")
        return False
    file_redirects = pagegenerators.MySQLPageGenerator(
        "select page_namespace, page_title "
        "from page "
        "where page_namespace = 6 "
        'and page_title like "{prefix}%{suffix}" '
        "and page_is_redirect = 1 "
        "order by page_title".format(
            prefix=bsiconsbot.page.BSiconPage.PREFIX,
            suffix=bsiconsbot.page.BSiconPage.SUFFIX,
        ),
        site=options["site"],
    )
    save_list(
        file_redirects,
        options["redirects_page"],
        summary=options["list_summary"],
    )
    options["start"] = datetime.datetime.combine(
        options["changes_date"], time.min
    )
    options["end"] = datetime.datetime.combine(
        options["changes_date"], time.max
    )
    output_log(logtype="upload", options=options)
    output_log(logtype="delete", options=options, bsicon_template_title="bsn")
    output_move_log(options=options)
    output_edits(options=options)
    large_files = pagegenerators.MySQLPageGenerator(
        "select 6, img_name "
        "from image "
        'where img_name like "{prefix}%{suffix}" '
        "and img_size > {large_size} "
        "order by img_name".format(
            prefix=bsiconsbot.page.BSiconPage.PREFIX,
            suffix=bsiconsbot.page.BSiconPage.SUFFIX,
            large_size=options["large_size"],
        ),
        site=options["site"],
    )
    save_list(
        large_files, options["large_page"], summary=options["list_summary"]
    )
    return True


if __name__ == "__main__":
    main()

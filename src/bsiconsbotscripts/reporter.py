"""
Generate BSicon reports.

    - Output changes to BSicons
    - List BSicon redirects
    - List large BSicons
"""
from __future__ import annotations

import argparse
import datetime
from typing import Any

import pywikibot
import pywikibot.pagegenerators
from jsoncfg.value_mappers import require_bool
from pywikibot_extensions.page import Page

import bsiconsbot
from bsiconsbot.options_classes import TitleToPage
from bsiconsbot.page import BSiconPage, load_config
from bsiconsbot.textlib import get_headers


def get_page_from_size(page: pywikibot.Page) -> pywikibot.Page:
    """Return a page based on the current page size."""
    i = 1
    title = page.title()
    while True:
        if not page.exists():
            break
        if len(page.text) < 1e6:
            break
        i += 1
        page = Page(page.site, f"{title} ({i:02d})")
    return page


def save_list(page_list: list[pywikibot.Page], page: Page) -> None:
    """
    Write the given page_list to the given page.

    :param page_list: List of pages to output
    :param page: Page to save to
    """
    list_text = ""
    for item in sorted(page_list):
        list_text += f"\n# {item.title(as_link=True, textlink=True)}"
    try:
        page.save_bot_start_end(list_text, summary="Updating list", force=True)
    except pywikibot.exceptions.Error:
        pywikibot.exception()


def _handle_hidden(data: dict[str, Any]) -> None:
    """Fill in placeholders for hidden keys."""
    for prop in ("comment", "user"):
        if f"{prop}hidden" in data:
            data[prop] = f"({prop} hidden)"


def output_log(
    *,
    site: pywikibot.site.APISite,
    logtype: str,
    start: datetime.datetime,
    end: datetime.datetime,
    prefix: str,
    bsicon_template_title: str = "bsq2",
) -> None:
    """Write logevents to a page."""
    log_page = Page(
        site,
        f"{prefix}/{logtype}/{start.strftime('%Y-%m')}",
    )
    if start.date().isoformat() in get_headers(log_page.text):
        return
    log_page = get_page_from_size(log_page)
    if start.date().isoformat() in get_headers(log_page.text):
        return
    if not log_page.exists():
        log_page.save(
            text=f"{{{{nobots}}}}{{{{{prefix}}}}}",
            summary="Create log page",
        )
    log_text = ""
    for logevent in site.logevents(
        logtype=logtype,
        namespace=6,
        start=start,
        end=end,
        reverse=True,
    ):
        try:
            bsicon = BSiconPage(logevent.page())
        except ValueError:
            continue
        _handle_hidden(logevent.data)
        log_text += (
            "\n|-\n| {{{{{tpl}|{name}}}}} || {r[logid]} || {r[timestamp]} "
            "|| {r[user]} || <nowiki>{r[comment]}</nowiki>".format(
                tpl=bsicon_template_title, name=bsicon.name, r=logevent.data
            )
        )
    if log_text:
        log_text = (
            f'{{| class="wikitable sortable mw-collapsible mw-collapsed"'
            f"\n! BSicon !! logid !! Date/time !! User !! Summary"
            f"{log_text}\n|}}"
        )
    else:
        log_text = ": None"
    try:
        log_page.save(
            text=log_text,
            section="new",
            summary=start.date().isoformat(),
            minor=False,
            force=True,
        )
    except pywikibot.exceptions.Error:
        pywikibot.exception()


def output_move_log(
    *,
    site: pywikibot.site.APISite,
    start: datetime.datetime,
    end: datetime.datetime,
    prefix: str,
) -> None:
    """Write move logevents to a page."""
    logtype = "move"
    log_page = Page(
        site,
        f"{prefix}/{logtype}/{start.strftime('%Y-%m')}",
    )
    if start.date().isoformat() in get_headers(log_page.text):
        return
    log_page = get_page_from_size(log_page)
    if start.date().isoformat() in get_headers(log_page.text):
        return
    if not log_page.exists():
        log_page.save(
            text=f"{{{{nobots}}}}{{{{{prefix}}}}}",
            summary="Create log page",
        )
    log_text = ""
    for logevent in site.logevents(
        logtype=logtype,
        namespace=6,
        start=start,
        end=end,
        reverse=True,
    ):
        page = logevent.page()
        row_text = "\n|-\n| "
        try:
            page = BSiconPage(page)
        except ValueError:
            row_text += page.title(as_link=True, textlink=True)
        else:
            row_text += f"{{{{bsn|{page.name}}}}}"
        row_text += " || "
        target = logevent.target_page
        try:
            target = BSiconPage(target)
        except ValueError:
            row_text += target.title(as_link=True, textlink=True)
        else:
            row_text += f"{{{{bsq2|{target.name}}}}}"
        if not (
            isinstance(page, BSiconPage) or isinstance(target, BSiconPage)
        ):
            continue
        log_text += row_text
        _handle_hidden(logevent.data)
        log_text += (
            " || {r[logid]} || {r[timestamp]} || {r[user]} || "
            "<nowiki>{r[comment]}</nowiki>".format(r=logevent.data)
        )
    if log_text:
        log_text = (
            f'{{| class="wikitable sortable mw-collapsible mw-collapsed"'
            f"\n! Page !! Target !! logid !! Date/time !! User !! Summary"
            f"{log_text}\n|}}"
        )
    else:
        log_text = ": None"
    try:
        log_page.save(
            text=log_text,
            section="new",
            summary=start.date().isoformat(),
            minor=False,
            force=True,
        )
    except pywikibot.exceptions.Error:
        pywikibot.exception()


def output_edits(
    *,
    site: pywikibot.site.APISite,
    start: datetime.datetime,
    end: datetime.datetime,
    prefix: str,
) -> None:
    """Write edits to a page."""
    changes_page = Page(
        site,
        f"{prefix}/{start.strftime('%Y-%m')}",
    )
    if start.date().isoformat() in get_headers(changes_page.text):
        return
    changes_page = get_page_from_size(changes_page)
    if start.date().isoformat() in get_headers(changes_page.text):
        return
    if not changes_page.exists():
        changes_page.save(
            text=f"{{{{nobots}}}}{{{{{prefix}}}}}",
            summary="Create changes page",
        )
    file_changes = ""
    for recent_change in site.recentchanges(
        start=start,
        end=end,
        reverse=True,
        namespaces=6,
        changetype="edit|new",
    ):
        try:
            file = BSiconPage(site, recent_change["title"])
        except (KeyError, ValueError):
            continue
        if not file.exists():
            continue
        _handle_hidden(recent_change)
        file_changes += (
            "\n|-\n| {{{{bsq2|{name}}}}} || {rc[revid]} || {rc[timestamp]} || "
            "{rc[user]} || <nowiki>{rc[comment]}</nowiki>".format(
                name=file.name, rc=recent_change
            )
        )
    if file_changes:
        file_changes = (
            f'{{| class="wikitable sortable mw-collapsible mw-collapsed"'
            f"\n! BSicon !! revid !! Date/time !! User !! Summary"
            f"{file_changes}\n|}}"
        )
    else:
        file_changes = ": No changes"
    try:
        changes_page.save(
            text=file_changes,
            section="new",
            summary=start.date().isoformat(),
            minor=False,
            force=True,
        )
    except pywikibot.exceptions.Error:
        pywikibot.exception()


def main(*args: str) -> int:
    """
    Process command line arguments and invoke bot.

    :param args: command line arguments
    """
    local_args = pywikibot.handle_args(args, do_help=False)
    site = pywikibot.Site()
    title_to_page = TitleToPage(site)
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=bsiconsbot.PYWIKIBOT_GLOBAL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument(
        "config",
        type=title_to_page,
        help="page title that has the JSON config (object)",
    )
    parser.add_argument(
        "changes_page_prefix",
        help="prefix of the page title to output the changes",
        metavar="changes-page-prefix",
    )
    parser.add_argument(
        "large_page",
        type=title_to_page,
        help="page title to output the list of large files",
        metavar="large-page",
    )
    parser.add_argument(
        "logs_page_prefix",
        help="prefix of the page title to output logs",
        metavar="logs-page-prefix",
    )
    parser.add_argument(
        "redirects_page",
        type=title_to_page,
        help="page title to output the list of redirects",
        metavar="redirects-page",
    )
    parser.add_argument(
        "--large-size",
        default=1000,
        type=int,
        help="maximum size for non-large files (default: %(default)s)",
    )
    parser.add_argument(
        "--date",
        default=site.server_time().date() - datetime.timedelta(days=1),
        type=datetime.date.fromisoformat,
        help="list changes/logs on this date (default: %(default)s)",
        metavar="YYYY-MM-DD",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="force enable",
        dest="enabled",
    )
    parsed_args = parser.parse_args(args=local_args)
    site.login()
    config_json = load_config(parsed_args.config)
    if not (parsed_args.enabled or config_json.enabled(False, require_bool)):
        pywikibot.error("Task disabled.")
        return 1
    file_redirects = pywikibot.pagegenerators.MySQLPageGenerator(
        "select page_namespace, page_title "
        "from page "
        "where page_namespace = 6 "
        f"and page_title like '{BSiconPage.PREFIX}%{BSiconPage.SUFFIX}' "  # nosec  # noqa: E501
        "and page_is_redirect = 1 "
        "order by page_title",
        site=site,
    )
    save_list(file_redirects, parsed_args.redirects_page)
    start = datetime.datetime.combine(parsed_args.date, datetime.time.min)
    end = datetime.datetime.combine(parsed_args.date, datetime.time.max)
    output_log(
        site=site,
        logtype="upload",
        start=start,
        end=end,
        prefix=parsed_args.logs_page_prefix,
    )
    output_log(
        site=site,
        logtype="delete",
        start=start,
        end=end,
        prefix=parsed_args.logs_page_prefix,
        bsicon_template_title="bsn",
    )
    output_move_log(
        site=site, start=start, end=end, prefix=parsed_args.logs_page_prefix
    )
    output_edits(
        site=site, start=start, end=end, prefix=parsed_args.changes_page_prefix
    )
    large_files = pywikibot.pagegenerators.MySQLPageGenerator(
        "select 6, img_name "
        "from image "
        f"where img_name like '{BSiconPage.PREFIX}%{BSiconPage.SUFFIX}' "  # nosec  # noqa: E501
        f"and img_size > {parsed_args.large_size} "
        "order by img_name",
        site=site,
    )
    save_list(large_files, parsed_args.large_page)
    return 0

# -*- coding: utf-8 -*-
"""
Objects representing various MediaWiki pages.

This module extends pywikibot.page.
"""
import json
import re
import pywikibot


def get_template_pages(templates):
    """
    Given an iterable of templates, return a set of pages.

    @param templates: iterable of templates (L{pywikibot.Page})
    @type templates: iterable

    @rtype: set
    """
    pages = set()
    for template in templates:
        if template.isRedirectPage():
            template = template.getRedirectTarget()
        if not template.exists():
            continue
        pages.add(template)
        for tpl in template.backlinks(filterRedirects=True):
            pages.add(tpl)
    return pages


class Page(pywikibot.Page):
    """Represents a MediaWiki page."""

    bot_start_end = re.compile(
        r'^(.*?<!--\s*bot start\s*-->).*?(<!--\s*bot end\s*-->.*)$',
        flags=re.S | re.I
    )

    def get_json(self, **kwargs):
        """
        Return JSON from the page.

        @rtype: dict
        """
        if self.isRedirectPage():
            pywikibot.log('{} is a redirect.'.format(self.title()))
            page = self.getRedirectTarget()
        else:
            page = self
        if not page.exists():
            pywikibot.log('{} does not exist.'.format(page.title()))
            return dict()
        try:
            return json.loads(page.get(**kwargs).strip())
        except ValueError:
            pywikibot.error('{} does not contain valid JSON.'.format(page))
            raise
        except pywikibot.PageRelatedError:
            return dict()

    def save_bot_start_end(self, text, minor=False, botflag=False, **kwargs):
        """
        Writes text to the specified area of a given page.

        See pywikibot.Page.save() for arguments.
        """
        if self.exists():
            text = text.strip()
            if self.__class__.bot_start_end.match(self.text):
                self.text = self.__class__.bot_start_end.sub(
                    r'\1\n{}\2'.format(text),
                    self.text
                )
            else:
                self.text = text
            self.save(minor=minor, botflag=botflag, **kwargs)
        else:
            pywikibot.error('{} does not exist. Skipping.'
                            .format(self.title()))

    def title_regex(self, **kwargs):
        """
        Return a regex to match title of the page.

        @rtype: str
        """
        title = self.title(underscore=True, **kwargs)
        title = re.escape(title)
        title = title.replace('_', '[ _]+')
        if self.site.siteinfo['case'] == 'first-letter':
            char1 = title[:1]
            if char1.isalpha():
                # The first letter is not case sensative.
                char1 = '[{}{}]'.format(char1, char1.swapcase())
                title = char1 + title[1:]
        return title

    def titles_regex(self, **kwargs):
        """
        Return a regex to match titles of the page, including redirects.

        @rtype: str
        """
        titles = set()
        titles.add(self.title_regex(**kwargs))
        try:
            redirects = self.backlinks(filter_redirects=True)
        except pywikibot.CircularRedirect:
            pass
        else:
            for redirect in redirects:
                titles.add(Page(redirect).title_regex(**kwargs))
        return '|'.join(titles)


class BSiconPage(Page, pywikibot.FilePage):
    """Represents a BSicon file description page."""

    prefix = 'BSicon_'
    suffix = '.svg'

    def __init__(self, source, title='', name=''):
        """Initializer."""
        if not title and name:
            title = '{prefix}{name}{suffix}'.format(
                prefix=self.__class__.prefix,
                name=name,
                suffix=self.__class__.suffix
            )
        super().__init__(source, title)
        title = self.title(underscore=True, with_ns=False)
        if not (title.startswith(self.__class__.prefix)
                and title.endswith(self.__class__.suffix)):
            raise ValueError('{} is not a BSicon.'.format(self))

    @property
    def name(self):
        """BSicon name."""
        return (self.title(underscore=True, with_ns=False)
                [len(self.__class__.prefix):-len(self.__class__.suffix)])

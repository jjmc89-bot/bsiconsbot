"""Initialize."""
import re

from pywikibot.bot import _GLOBAL_HELP


PYWIKIBOT_GLOBAL_HELP = re.sub(
    r"\n\n?-help +.+?(\n\n-|\s*$)", r"\1", _GLOBAL_HELP, flags=re.S
)

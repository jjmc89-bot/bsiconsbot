#!/bin/bash
set -euo pipefail

source ~/.venvs/bsiconsbot/bin/activate

if [ $(date +"%u") -eq 6 ]; then tpl='--transcluded'; else tpl=''; fi

bsicons-replacer -lang:commons -family:commons -ns:not:2,3 User:JJMC89_bot/config/BSiconsReplacer/global --local-config User:JJMC89_bot/config/BSiconsReplacer --always $tpl

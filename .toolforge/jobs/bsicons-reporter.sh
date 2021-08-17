#!/bin/bash
set -euo pipefail

source ~/.venvs/bsiconsbot/bin/activate

bsicons-reporter -lang:commons -family:commons User:JJMC89_bot/config/BSicons User:JJMC89_bot/report/BSicons/changes User:JJMC89_bot/report/BSicons/large User:JJMC89_bot/report/BSicons/logs User:JJMC89_bot/report/BSicons/redirects

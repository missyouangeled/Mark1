#!/usr/bin/env bash
set -euo pipefail
cd /home/missyouangeled/.openclaw/workspace
mkdir -p .run
exec php -S 0.0.0.0:8093 -t /home/missyouangeled/.openclaw/workspace/pulsenest-php

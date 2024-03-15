#!/usr/bin/env bash

set -eo pipefail

sed -i "" "s/\(-accepted.*localutm\) \\\\$/\1,$XSV_AUD \\\\/" ./build/dev/startup/core_service.sh

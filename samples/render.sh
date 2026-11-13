#!/usr/bin/env bash
# Turns each sample HTML file into a PNG using headless Google Chrome.
# Run from anywhere: ./samples/render.sh
# You can also open any .html file in a browser and take a screenshot yourself.
set -euo pipefail

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
DIR="$(cd "$(dirname "$0")" && pwd)"

render() {
  local name="$1" size="$2"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --allow-file-access-from-files --window-size="$size" \
    --screenshot="$DIR/$name.png" "file://$DIR/$name.html" 2>/dev/null
  echo "rendered $name.png"
}

render 01_electricity_bill_kn 820,1060
render 02_electricity_bill_hi 820,790
render 03_bank_letter_en 820,830
render 04_bank_sms_screenshot 420,620
render 05_property_tax_notice_kn 820,680
# Must run after 01, because the blurry photo is made from 01's PNG.
render 06_blurry_photo 820,1100

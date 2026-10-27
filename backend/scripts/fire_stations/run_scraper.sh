#!/usr/bin/env bash
# Scrape Gujarat fire stations from Google Maps with gosom/google-maps-scraper
# (https://github.com/gosom/google-maps-scraper). Needs Docker.
#
#   ./scripts/fire_stations/run_scraper.sh
#
# Writes output/gujarat_fire_stations.csv next to this script. Then load it:
#   python scripts/fire_stations/import_fire_stations.py scripts/fire_stations/output/gujarat_fire_stations.csv
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$HERE/output"

docker run --rm \
  -v gmaps-playwright-cache:/opt \
  -v "$HERE/queries_gujarat.txt:/queries.txt:ro" \
  -v "$HERE/output:/out" \
  gosom/google-maps-scraper \
  -input /queries.txt \
  -results /out/gujarat_fire_stations.csv \
  -depth 3 \
  -c 4 \
  -lang en \
  -exit-on-inactivity 3m

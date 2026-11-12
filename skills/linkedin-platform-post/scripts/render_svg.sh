#!/usr/bin/env bash
# Render an SVG poster to PNG. Does not write into a git repository.
set -euo pipefail

src="${1:?usage: render_svg.sh <svg> <png>}"
out="${2:?usage: render_svg.sh <svg> <png>}"

case "$out" in
  *"/open-data-platform/"*)
    echo "refusing to write inside the open-data-platform repo: $out" >&2
    exit 1
    ;;
esac

mkdir -p "$(dirname "$out")"
uv run --with cairosvg python -c '
import cairosvg, sys
cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2])
' "$src" "$out"
echo "$out"

#!/usr/bin/env bash
# Render an SVG poster to PNG.
# Refuses a destination inside a git checkout unless ALLOW_IN_REPO=1.
set -euo pipefail

src="${1:?usage: render_svg.sh <svg> <png>}"
out="${2:?usage: render_svg.sh <svg> <png>}"

mkdir -p "$(dirname "$out")"

if [[ "${ALLOW_IN_REPO:-}" != 1 ]] && command -v git >/dev/null 2>&1; then
  if git -C "$(dirname "$out")" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "refusing to write inside a git checkout: $out" >&2
    echo "set ALLOW_IN_REPO=1 when that path was requested" >&2
    exit 1
  fi
fi

uv run --with cairosvg python -c '
import cairosvg, sys
cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2])
' "$src" "$out"
echo "$out"

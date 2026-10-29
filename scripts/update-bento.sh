#!/bin/sh
# Pin Hoist to a Bento MADR release: copies the kit files from a tag of
# github.com/leadui/bento-madr into site/vendor/bento-madr/.
# Usage: scripts/update-bento.sh v0.2.0
set -eu
TAG="${1:?usage: scripts/update-bento.sh <tag, e.g. v0.2.0>}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/site/vendor/bento-madr"
BASE="https://raw.githubusercontent.com/leadui/bento-madr/$TAG"
mkdir -p "$DIR"
for f in bento-kit.js bento-kit.css LICENSE; do
  curl -fsSL "$BASE/$f" -o "$DIR/$f.tmp"
  mv "$DIR/$f.tmp" "$DIR/$f"
done
printf 'Bento MADR %s\nhttps://github.com/leadui/bento-madr/tree/%s\nUpdate with scripts/update-bento.sh <tag>; do not edit these files here.\n' "$TAG" "$TAG" > "$DIR/VERSION"
echo "Pinned Bento MADR $TAG in site/vendor/bento-madr"

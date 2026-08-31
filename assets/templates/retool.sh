#!/usr/bin/env bash
# Round-trip the ToolScript between this workspace and the Retool instance.
#
#   ./retool.sh pack            -> build/<NAME>.zip  (import this)
#   ./retool.sh unpack <zip>    -> replaces app/ with a Retool export
#
# The whole point of the app/ split: pack READS ONLY app/, unpack WRITES ONLY
# app/ and app.bak/. docs/, migrations/ and this script are never in scope, so
# an export can never clobber them.
#
# Template from retool-classic-apps-skill. To adopt: set NAME to your app's
# name and drop this at the workspace root next to app/.
set -euo pipefail
cd "$(dirname "$0")"

NAME="My App"   # <-- the one thing to edit
VALIDATE="$HOME/.claude/skills/retool-classic-apps-skill/scripts/validate_app.py"

case "${1:-}" in
pack)
  [ -f app/main.rsx ] || { echo "app/main.rsx missing — nothing to pack"; exit 1; }
  if [ -f "$VALIDATE" ]; then python3 "$VALIDATE" app; fi

  # FLAT zip: main.rsx / metadata.json at the ARCHIVE ROOT, no wrapper folder.
  # Retool's own "Export to ZIP" produces exactly that layout, and a wrapped
  # zip can import as NOTHING, silently. The app's display name comes from the
  # import dialog, not from the archive.
  mkdir -p build
  rm -f "build/$NAME.zip"
  (cd app && zip -qr "../build/$NAME.zip" . -x '*.DS_Store' -x '.DS_Store')
  echo "packed: build/$NAME.zip"
  ;;

unpack)
  ZIP="${2:?usage: ./retool.sh unpack <export.zip>}"
  [ -f "$ZIP" ] || { echo "no such zip: $ZIP"; exit 1; }

  rm -rf .tmp-unpack && mkdir .tmp-unpack
  unzip -q "$ZIP" -d .tmp-unpack
  # Retool exports are flat; tolerate a wrapped zip too.
  SRC=".tmp-unpack"
  if [ ! -f "$SRC/main.rsx" ]; then
    SRC=$(find .tmp-unpack -maxdepth 2 -name main.rsx -print -quit)
    SRC="${SRC%/main.rsx}"
  fi
  [ -n "$SRC" ] && [ -f "$SRC/main.rsx" ] || { rm -rf .tmp-unpack; echo "no main.rsx inside $ZIP"; exit 1; }

  # app.bak/ is the undo — keep exactly one previous version around.
  rm -rf app.bak
  if [ -d app ]; then mv app app.bak; fi
  mkdir app && cp -Rp "$SRC"/. app/
  rm -rf .tmp-unpack
  echo "app/ replaced from $ZIP (previous version in app.bak/)"
  ;;

*)
  echo "usage: $0 pack | unpack <export.zip>"; exit 1
  ;;
esac

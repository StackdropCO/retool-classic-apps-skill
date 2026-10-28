#!/usr/bin/env bash
# zip_app.sh — Creates a zip file for Retool import.
#
# Usage:
#   bash zip_app.sh <app-dir> [output-path]
#
# The script validates the app directory structure, then creates a zip file
# excluding OS junk files and Python bytecode.
#
# If output-path is omitted, the zip is placed next to the app directory
# as <app-name>.zip.

set -euo pipefail

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
if [ $# -lt 1 ]; then
    echo "Usage: $0 <app-dir> [output-path]"
    echo "Creates a zip file for Retool import."
    exit 1
fi

APP_DIR="$1"
APP_NAME=$(basename "$APP_DIR")
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---------------------------------------------------------------------------
# Validate directory
# ---------------------------------------------------------------------------
if [ ! -d "$APP_DIR" ]; then
    echo "Error: $APP_DIR is not a directory"
    exit 1
fi

# ---------------------------------------------------------------------------
# Check required files. Only the two every layout has: a multi-page app has no
# functions.rsx / .positions.json (validate_app.py checks the layout-specific files).
# ---------------------------------------------------------------------------
MISSING=0
for f in main.rsx metadata.json; do
    if [ ! -f "$APP_DIR/$f" ]; then
        echo "Error: Missing required file: $f"
        MISSING=1
    fi
done
if [ "$MISSING" -eq 1 ]; then
    exit 1
fi

# ---------------------------------------------------------------------------
# Run validation (if validate_app.py exists)
# ---------------------------------------------------------------------------
if [ -f "$SCRIPT_DIR/validate_app.py" ]; then
    echo "=== Running validation ==="
    if ! python3 "$SCRIPT_DIR/validate_app.py" "$APP_DIR"; then
        echo ""
        echo "Error: Validation failed. Fix errors before zipping."
        exit 1
    fi
    echo ""
else
    echo "=== Skipping validation (validate_app.py not found) ==="
    echo ""
fi

# ---------------------------------------------------------------------------
# Determine output path
# ---------------------------------------------------------------------------
if [ $# -ge 2 ]; then
    OUTPUT="$2"
    # Absolutize: the zip step cds into APP_DIR, where a relative output path
    # would land inside the app (and try to zip itself).
    case "$OUTPUT" in
        /*) ;;
        *) OUTPUT="$(pwd)/$OUTPUT" ;;
    esac
else
    OUTPUT="$(cd "$(dirname "$APP_DIR")" && pwd)/${APP_NAME}.zip"
fi

# Remove existing zip to avoid appending to stale archive
if [ -f "$OUTPUT" ]; then
    rm "$OUTPUT"
fi

# ---------------------------------------------------------------------------
# Create zip
# ---------------------------------------------------------------------------
echo "=== Creating zip ==="
# FLAT zip: main.rsx / metadata.json at the ARCHIVE ROOT, no wrapper folder.
# Retool's own "Export to ZIP" is flat, and a wrapped zip can import as
# NOTHING, silently. The app's name comes from the import dialog, not from a
# folder inside the archive.
# `zip -r .` includes dot-files and dot-directories, so a multi-page app's
# .positions/.<page>.positions.json files are in the archive (checked on a probe zip).
(
    cd "$APP_DIR"
    zip -r "$OUTPUT" . \
        -x ".DS_Store" \
        -x "**/.DS_Store" \
        -x "__pycache__/*" \
        -x "**/__pycache__/*" \
        -x "**/*.pyc"
)

echo ""
echo "Created: $OUTPUT"
echo "Size: $(du -h "$OUTPUT" | cut -f1)"
echo ""
echo "Import into Retool. Importing into an existing app REPLACES it in place;"
echo "Create-new makes a separate app. A failed import is SILENT (no error,"
echo "no change) - verify with a probe marker. See references/SILENT-FAILURES.md."

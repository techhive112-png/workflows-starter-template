#!/bin/bash
# Cloud sessions: install Tesseract OCR and the spectakeoff package so its full test
# suite runs (the OCR / drawing tests are skipped when Tesseract is missing).
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

langs="$(tesseract --list-langs 2>/dev/null || true)"
if ! grep -qx eng <<<"$langs" || ! grep -qx lav <<<"$langs" || ! grep -qx osd <<<"$langs"; then
  export DEBIAN_FRONTEND=noninteractive
  if ! apt-get install -y -q tesseract-ocr tesseract-ocr-eng tesseract-ocr-lav >/dev/null; then
    apt-get update -q >/dev/null
    apt-get install -y -q tesseract-ocr tesseract-ocr-eng tesseract-ocr-lav >/dev/null
  fi
fi

python -m pip install -q --disable-pip-version-check -e "$CLAUDE_PROJECT_DIR/spectakeoff[dev,llm]"

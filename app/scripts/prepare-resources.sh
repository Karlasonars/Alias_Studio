#!/bin/bash
# Stage the Python pipeline + a uv binary into src-tauri/resources for
# bundling. Packaged builds run: resources/bin/uv --directory
# resources/pipeline run publikclip — the env bootstraps on first launch.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_DIR="$(cd "$APP_DIR/.." && pwd)"
RES="$APP_DIR/src-tauri/resources"

mkdir -p "$RES/bin"

# Pipeline source, minus env/caches/tests. wav2vec2_checkpoints is a stray
# HF cache a dev machine may carry — 700+ MB that must never ride into the app.
rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'tests' \
  --exclude 'wav2vec2_checkpoints' \
  "$REPO_DIR/pipeline/" "$RES/pipeline/"

# uv: copy the host binary (same arch as the build machine/dmg target).
UV_BIN="$(command -v uv)"
cp "$UV_BIN" "$RES/bin/uv"
chmod +x "$RES/bin/uv"

echo "resources staged: $(du -sh "$RES" | cut -f1)"

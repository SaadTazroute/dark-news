#!/bin/bash
# Build the AgentCore deployment zip.
# Run this before terraform apply.
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
STAGING=$(mktemp -d)

echo "Building agent zip..."
cp -r "$ROOT/src" "$STAGING/src"
cp -r "$ROOT/templates" "$STAGING/templates"
cp "$ROOT/agentcore/agent.py" "$STAGING/agent.py"
cp "$ROOT/agentcore/requirements.txt" "$STAGING/requirements.txt"

cd "$STAGING"
uv pip install -r requirements.txt --target . -q

mkdir -p "$ROOT/dist"
zip -r "$ROOT/dist/agent.zip" . -x "*.pyc" -x "__pycache__/*" > /dev/null

rm -rf "$STAGING"
echo "Done: dist/agent.zip"

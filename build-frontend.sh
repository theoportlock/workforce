#!/bin/bash
# Build frontend and deploy to static assets

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Building frontend..."
cd frontend
npm run build

cd ../workforce/web/static

# Get the new JS filename
NEW_JS=$(ls -t "$SCRIPT_DIR/frontend/dist/assets/index-"*.js | head -1 | xargs basename)
NEW_CSS=$(ls -t "$SCRIPT_DIR/frontend/dist/assets/index-"*.css | head -1 | xargs basename)

echo "Cleaning old assets..."
rm -f assets/index-*.js assets/index-*.css

echo "Copying $NEW_JS to assets/"
cp "$SCRIPT_DIR/frontend/dist/assets/$NEW_JS" assets/
echo "Copying $NEW_CSS to assets/"
cp "$SCRIPT_DIR/frontend/dist/assets/$NEW_CSS" assets/

echo "Updating manifest.json..."
cat > assets/manifest.json << EOF
{
  "entry": {
    "js": "assets/$NEW_JS",
    "css": "assets/$NEW_CSS"
  }
}
EOF

echo "Updating index.html..."
python3 - <<PY
from pathlib import Path
import re

path = Path("index.html")
text = path.read_text()

text = re.sub(r'assets/index-[^"\']+\\.js', f'assets/$NEW_JS', text)
text = re.sub(r'assets/index-[^"\']+\\.css', f'assets/$NEW_CSS', text)

path.write_text(text)
PY

rm -f index.html.backup

echo "Done! Frontend deployed."

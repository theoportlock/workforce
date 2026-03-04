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

echo "Copying $NEW_JS to assets/"
cp "$SCRIPT_DIR/frontend/dist/assets/$NEW_JS" assets/

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
sed -i "s|index-[a-zA-Z0-9]*.js|$NEW_JS|" index.html
sed -i "s|index-[a-zA-Z0-9]*.css|$NEW_CSS|" index.html

echo "Done! Frontend deployed."

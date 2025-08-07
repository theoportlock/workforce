#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Define file paths and input SVG
SVG_FILE="docs/images/icon.svg"
OUTPUT_DIR="docs/images"
ICON_WIN="${OUTPUT_DIR}/icon.ico"
ICON_MAC="${OUTPUT_DIR}/icon.icns"
ICON_LINUX="${OUTPUT_DIR}/icon.xbm"

# Ensure the output directory exists
mkdir -p "${OUTPUT_DIR}"

# -----------------------------------------------------------
#  1. Generate Windows .ico file (multi-size)
# -----------------------------------------------------------
echo "Generating Windows icon: ${ICON_WIN}"
convert -density 384 -background none "${SVG_FILE}" \
    \( -clone 0 -resize 256x256 \) \
    \( -clone 0 -resize 48x48 \) \
    \( -clone 0 -resize 32x32 \) \
    \( -clone 0 -resize 16x16 \) \
    -delete 0 -colors 256 "${ICON_WIN}"

# -----------------------------------------------------------
#  2. Generate macOS .icns file
#     This part of the script requires `iconutil` and will only run on macOS.
# -----------------------------------------------------------
if [ "$(uname)" = "Darwin" ]; then
    echo "Generating macOS icon: ${ICON_MAC}"
    ICONSET_DIR="${OUTPUT_DIR}/icon.iconset"
    mkdir -p "${ICONSET_DIR}"

    convert -density 384 -background none "${SVG_FILE}" -resize 16x16 "${ICONSET_DIR}/icon_16x16.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 32x32 "${ICONSET_DIR}/icon_16x16@2x.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 32x32 "${ICONSET_DIR}/icon_32x32.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 64x64 "${ICONSET_DIR}/icon_32x32@2x.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 128x128 "${ICONSET_DIR}/icon_128x128.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 256x256 "${ICONSET_DIR}/icon_128x128@2x.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 256x256 "${ICONSET_DIR}/icon_256x256.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 512x512 "${ICONSET_DIR}/icon_256x256@2x.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 512x512 "${ICONSET_DIR}/icon_512x512.png"
    convert -density 384 -background none "${SVG_FILE}" -resize 1024x1024 "${ICONSET_DIR}/icon_512x512@2x.png"

    # Compile the iconset into a single .icns file
    iconutil -c icns "${ICONSET_DIR}" -o "${ICON_MAC}"
    # Clean up the intermediate directory
    rm -rf "${ICONSET_DIR}"
else
    echo "Skipping macOS icon generation (not a macOS system)."
fi

# -----------------------------------------------------------
#  3. Generate Linux .xbm file (monochrome)
# -----------------------------------------------------------
echo "Generating Linux icon: ${ICON_LINUX}"
convert -density 384 -background none "${SVG_FILE}" -resize 32x32 -monochrome "${ICON_LINUX}"

# -----------------------------------------------------------
#  4. Generate individual PNG files
# -----------------------------------------------------------
echo "Generating individual PNG files..."
convert -density 384 -background none "${SVG_FILE}" -resize 256x256 "${OUTPUT_DIR}/icon-256.png"
convert -density 384 -background none "${SVG_FILE}" -resize 48x48 "${OUTPUT_DIR}/icon-48.png"
convert -density 384 -background none "${SVG_FILE}" -resize 32x32 "${OUTPUT_DIR}/icon-32.png"
convert -density 384 -background none "${SVG_FILE}" -resize 16x16 "${OUTPUT_DIR}/icon-16.png"

echo "All icons have been exported successfully."

#!/usr/bin/env bash
# Environment setup for fellowship project

# Export version
export VERSION=${VERSION:-$(git describe --tags --first-parent --abbrev=7 --long --dirty --always | sed -e "s/^v//g")}
echo $VERSION

# Add project paths to PATH
export PATH="workforce/:$PATH"

# Activate Python virtual environment
if [ -f venv/bin/activate ]; then
    . venv/bin/activate
else
    echo "No venv found at venv/bin/activate"
fi


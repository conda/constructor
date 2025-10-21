#!/bin/bash
set -euxo pipefail
echo "Added by test-install script" > "$PREFIX/test_install_sentinel.txt"

missing=false

if [ ! -f "$PREFIX/more_data/README.md" ]; then
    echo "Missing: $PREFIX/more_data/README.md"
    missing=true
fi

if [ ! -f "$PREFIX/something2.txt" ]; then
    echo "Missing: $PREFIX/something2.txt"
    missing=true
fi

# Ideally we should test the .pkg and .sh installers separately since
# the current behavior for .sh-installers is to include but also rename the license file to LICENSE.txt,
# but for .pkg the name of the provided license file remains unchanged.
if [ "$INSTALLER_TYPE" = "SH" ]; then
    if [ ! -f "$PREFIX/LICENSE.txt" ]; then
        echo "Missing: $PREFIX/LICENSE.txt"
        missing=true
    fi
else  # .pkg
    if [ ! -f "$PREFIX/TEST_LICENSE.txt" ]; then
        echo "Missing: $PREFIX/TEST_LICENSE.txt"
        missing=true
    fi
fi

if [ "$missing" = true ]; then
    exit 1
fi

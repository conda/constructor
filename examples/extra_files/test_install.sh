#!/bin/bash
set -euxo pipefail
echo "Added by test-install script" > "$PREFIX/test_install_sentinel.txt"

missing=false
test -f "$PREFIX/more_data/README.md" || { echo "Missing: $PREFIX/more_data/README.md"; missing=true; }
test -f "$PREFIX/something2.txt" || { echo "Missing: $PREFIX/something2.txt"; missing=true; }

# Ideally we should test the .pkg and .sh installers separately since
# the current behavior for .sh-installers is to include but also rename the license file to LICENSE.txt,
# but for macOS the name of the provided license file remains unchanged.
if [ "$INSTALLER_TYPE" = "SH" ]; then
    test -f "$PREFIX/LICENSE.txt" || { echo "Missing: $PREFIX/LICENSE.txt"; missing=true; }
else # .pkg
    test -f "$PREFIX/TEST_LICENSE.txt" || { echo "Missing: $PREFIX/TEST_LICENSE.txt"; missing=true; }
fi

if [ "$missing" = true ]; then
    exit 1
fi

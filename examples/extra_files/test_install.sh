#!/bin/bash
set -euxo pipefail
echo "Added by test-install script" > "$PREFIX/test_install_sentinel.txt"

test -f "$PREFIX/more_data/README.md"
test -f "$PREFIX/something2.txt"
# Ideally we should test the .pkg and .sh installers separately since
# the current behavior for .sh-installers is to include but also rename the license file to LICENSE.txt,
# but for macOS the name of the provided license file remains unchanged.

if [ "$INSTALLER_TYPE" = "SH" ]; then
    test -f "$PREFIX/LICENSE.txt"
else # .pkg
    test -f "$PREFIX/TEST_LICENSE.txt"
fi

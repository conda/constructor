#!/bin/bash
set -euxo pipefail
echo "Added by test-install script" > "$PREFIX/test_install_sentinel.txt"

test -f "$PREFIX/more_data/README.md"
test -f "$PREFIX/something2.txt"

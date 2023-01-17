#!/bin/bash
set -euxo pipefail
echo "Added by post-install script" > "$PREFIX/post_install_sentinel.txt"

test -f "$PREFIX/more_data/README.md"
test -f "$PREFIX/something2.txt"

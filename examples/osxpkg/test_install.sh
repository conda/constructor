#!/bin/sh
set -eux

echo "Added by post-install script" > "$PREFIX/post_install_sentinel.txt"
printenv >> "$PREFIX/post_install_sentinel.txt"

# Some tests
# default_location_pkg
[ "$(basename "$(dirname "$PREFIX")")" = "Library" ] || exit 1
# pkg_name
[ "$(basename "$PREFIX")" = "osx-pkg-test" ] || exit 1

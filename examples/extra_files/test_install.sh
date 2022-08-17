#!/bin/bash
set -ex

# if PREFIX is not defined (or empty), then this was called from an OSX PKG installer
# $2 is the install location, ($HOME by default)
if [ -z "${PREFIX:-}" ]; then
    PREFIX=$(echo "$2/__NAME_LOWER__" | sed -e 's,//,/,g')
    PREFIX=$(cd "$PREFIX"; pwd)
fi

test -f "$PREFIX/more_data/README.md"
test -f "$PREFIX/something2.txt"

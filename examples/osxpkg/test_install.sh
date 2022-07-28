#!/bin/bash
set -ex

# $2 is the install location, ($HOME by default)
if [ xxx$PREFIX == 'xxx' ]; then
    PREFIX=$(cd "$2/__NAME_LOWER__"; pwd)
fi

echo '## Hello from Post_install script ' > $HOME/postinstall.txt
printenv >> $HOME/postinstall.txt

# Some tests
# default_location_pkg
[[ $(basename $(dirname $PREFIX)) == "Library" ]] || exit 1
# pkg_name
[[ $(basename $PREFIX) == "osx-pkg-test" ]] || exit 1

#!/bin/sh

set -eux

# $2 is the install location, which is ~ by default
# but which the user can change.
PREFIX="$2/{{ pkg_name_lower }}"
PREFIX=$(cd "$PREFIX"; pwd)

# If the UI selected the "Create shortcuts" option
# we create a sentinel file that will be checked for existence
# during run_installation.sh
# If it doesn't exist, it means that this script never ran
# due to (A) the user deselected the option, or (B) the installer
# was created with menu_packages=[], which disables shortcuts altogether,
# or (C) the installer was created with an incompatible --conda-exe.
touch "$PREFIX/pkgs/user_wants_shortcuts"

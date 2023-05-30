#!/bin/sh
# Copyright (c) 2012-2020 Anaconda, Inc.
# All rights reserved.

# $2 is the install location, which is ~ by default
# but which the user can change.
set -eux

PREFIX="$2/__NAME_LOWER__"
PREFIX=$(cd "$PREFIX"; pwd)
rm -rf "$PREFIX/pkgs"

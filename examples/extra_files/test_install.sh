#!/bin/bash
set -euxo pipefail

test -f "$PREFIX/more_data/README.md"
test -f "$PREFIX/something2.txt"

#!/bin/bash

set -eo pipefail
echo "Added by test-install script" > "$PREFIX/test_install_sentinel.txt"

echo "sourcing..."
# shellcheck disable=SC1091
source "$PREFIX/etc/profile.d/conda.sh"

conda activate "$PREFIX"

echo "+ conda info"
conda info -v

echo "+ conda config"
conda config --show-sources

echo "+ Testing channels"
conda config --show --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['channels'] == ['conda-forge'], info"
echo "  OK"

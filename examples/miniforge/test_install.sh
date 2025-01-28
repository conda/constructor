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

echo "+ Testing conda channels"
conda config --show --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert 'conda-forge' in info['channels'], info"
echo "  OK"

echo "+ Testing mamba installation"
mamba --version
echo "  OK"

echo "+ mamba info"
mamba info

echo "+ Testing mamba version"
mamba --version | grep mamba | cut -d' ' -f2 | grep -q 1.5.12
mamba --version | grep conda | cut -d' ' -f2 | grep -q 24.11.2

mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['mamba_version'] == '1.5.12', info"
echo "  OK"

echo "+ Testing mamba channels"
mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert any('conda-forge' in c for c in info['channels']), info"
echo "  OK"

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

EXPECTED_MAMBA_VERSION="1.5.12"

# Get versions with conda
MAMBA_VERSION=$(conda list "^mamba$" --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); print(info[0]['version'])")
LIBMAMBA_VERSION=$(conda list "^libmamba$" --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); print(info[0]['version'])")
LIBMAMBAPY_VERSION=$(conda list "^libmambapy$" --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); print(info[0]['version'])")

if [ "$MAMBA_VERSION" != "$EXPECTED_MAMBA_VERSION" ]; then
    echo "ERROR: Mamba version mismatch: expected $EXPECTED_MAMBA_VERSION, got $MAMBA_VERSION"
    exit 1
fi

if [ "$LIBMAMBA_VERSION" != "$EXPECTED_MAMBA_VERSION" ]; then
    echo "ERROR: libmamba version mismatch: expected $EXPECTED_MAMBA_VERSION, got $LIBMAMBA_VERSION"
    exit 1
fi

if [ "$LIBMAMBAPY_VERSION" != "$EXPECTED_MAMBA_VERSION" ]; then
    echo "ERROR: libmambapy version mismatch: expected $EXPECTED_MAMBA_VERSION, got $LIBMAMBAPY_VERSION"
    exit 1
fi

echo "+ Testing mamba 1 installation"
mamba --version

echo "+ mamba info"
mamba info

echo "+ Testing mamba version"
mamba --version | grep mamba | cut -d' ' -f2 | grep -q "$EXPECTED_MAMBA_VERSION"
mamba --version | grep conda | cut -d' ' -f2 | grep -q 24.11.2

mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['mamba_version'] == '$EXPECTED_MAMBA_VERSION', info"

echo "+ Testing mamba channels"
mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert any('conda-forge' in c for c in info['channels']), info"
echo "  OK"

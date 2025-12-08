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

EXPECTED_MAMBA_VERSION="2.0.8"

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

echo "+ Testing mamba 2 installation"
mamba --version | grep -q "$EXPECTED_MAMBA_VERSION"

echo "+ mamba info"
mamba info

echo "+ mamba config sources"
mamba config sources

echo "+ mamba config list"
mamba config list

echo "+ Testing mamba 2 version"
mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['mamba version'] == '$EXPECTED_MAMBA_VERSION', info"

echo "+ Testing libmambapy 2 version"
python -c "import libmambapy; assert libmambapy.__version__ == '$EXPECTED_MAMBA_VERSION', f'libmamba version got: {libmambapy.__version__}; expected: ${EXPECTED_MAMBA_VERSION}'"

echo "+ Testing mamba channels"
mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert any('conda-forge' in c for c in info['channels']), info"
echo "  OK"

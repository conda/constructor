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

# Get versions with conda
MAMBA_VERSION=$(conda list "^mamba$" --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); print(info[0]['version'])")
LIBMAMBA_VERSION=$(conda list "^libmamba$" --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); print(info[0]['version'])")
LIBMAMBAPY_VERSION=$(conda list "^libmambapy$" --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); print(info[0]['version'])")

# Assert that their are all equal to CONSTRUCTOR_TEST_MAMBA_VERSION
if [ "$MAMBA_VERSION" != "$CONSTRUCTOR_TEST_MAMBA_VERSION" ]; then
    echo "ERROR: Mamba version mismatch: expected $CONSTRUCTOR_TEST_MAMBA_VERSION, got $MAMBA_VERSION"
    exit 1
fi

if [ "$LIBMAMBA_VERSION" != "$CONSTRUCTOR_TEST_MAMBA_VERSION" ]; then
    echo "ERROR: libmamba version mismatch: expected $CONSTRUCTOR_TEST_MAMBA_VERSION, got $LIBMAMBA_VERSION"
    exit 1
fi

if [ "$LIBMAMBAPY_VERSION" != "$CONSTRUCTOR_TEST_MAMBA_VERSION" ]; then
    echo "ERROR: libmambapy version mismatch: expected $CONSTRUCTOR_TEST_MAMBA_VERSION, got $LIBMAMBAPY_VERSION"
    exit 1
fi

MAMBA_MAJOR_VERSION=$(echo "$MAMBA_VERSION" | cut -d'.' -f1)

# The commands and output are slightly different between mamba 1 and 2,
# so we need to test them separately.
if [ "$MAMBA_MAJOR_VERSION" -eq "1" ]; then
    echo "+ Testing mamba 1 installation"
    mamba --version

    echo "+ mamba info"
    mamba info

    echo "+ Testing mamba version"
    mamba --version | grep mamba | cut -d' ' -f2 | grep -q "$MAMBA_VERSION"
    mamba --version | grep conda | cut -d' ' -f2 | grep -q 24.11.2

    mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['mamba_version'] == '$MAMBA_VERSION', info"

    echo "+ Testing mamba channels"
    mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert any('conda-forge' in c for c in info['channels']), info"
    echo "  OK"
else
    echo "+ Testing mamba 2 installation"
    mamba --version | grep -q "$MAMBA_VERSION"

    echo "+ mamba info"
    mamba info

    echo "+ mamba config sources"
    mamba config sources

    echo "+ mamba config list"
    mamba config list

    echo "+ Testing mamba 2 version"
    mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['mamba version'] == '$MAMBA_VERSION', info"

    echo "+ Testing libmambapy 2 version"
    python -c "import libmambapy; assert libmambapy.__version__ == '$MAMBA_VERSION', f'libmamba version got: {libmambapy.__version__}; expected: {MAMBA_VERSION}'"

    echo "+ Testing mamba channels"
    mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert any('conda-forge' in c for c in info['channels']), info"
    echo "  OK"
fi

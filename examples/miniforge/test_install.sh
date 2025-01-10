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

echo "+ mamba config sources"
mamba config sources

echo "+ mamba config list"
mamba config list

echo "+ Testing mamba 2 version"
mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['mamba version'] == '2.0.5', info"
echo "  OK"

echo "+ Testing libmambapy 2 version"
python -c "import libmambapy; assert libmambapy.__version__ == '2.0.5', f'libmamba version got: {libmambapy.__version__}; expected: 2.0.5'"
echo "  OK"

echo "+ Testing mamba channels"
mamba info --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert any('conda-forge' in c for c in info['channels']), info"
echo "  OK"

#!/bin/bash

set -exo pipefail
echo "Added by test-install script" > "$PREFIX/test_install_sentinel.txt"

# shellcheck disable=SC1091
source "$PREFIX/etc/profile.d/conda.sh"
conda activate "$PREFIX"
conda info
conda config --show-sources
python -c "from conda.base.context import context as c; assert len(c.channels) == 1 and c.channels[0] == 'conda-forge', c.channels"
#!/bin/bash

set -exo pipefail
echo "Added by test-install script" > "$PREFIX/test_install_sentinel.txt"

# shellcheck disable=SC1091
source "$PREFIX/etc/profile.d/conda.sh"
conda activate "$PREFIX"
conda install -yq jq
conda config --show-sources
test "$(conda config --json --show | jq -r '.channels[0]')" = "conda-forge"

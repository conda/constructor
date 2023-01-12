#!/bin/bash

set -euxo pipefail

source "$PREFIX/etc/profile.d/conda.sh"
conda activate "$PREFIX"
conda install -yq jq
conda config --show-sources
test "$(conda config --json --show | jq -r '.channels[0]')" = "conda-forge"

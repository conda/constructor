#!/bin/bash

set -eu pipefail

mamba activate "$PREFIX"

condarc_file="$PREFIX/.condarc"

test -f "$condarc_file"

expected_content="
channels:
  - conda-forge
mirrored_channels:
  conda-forge:
    - https://prefix.dev/conda-forge
    - https://conda.anaconda.org/conda-forge
"

actual_content=$(cat "$condarc_file")

# Normalize the content by removing newlines and spaces for comparison
expected_content=$(echo "$expected_content" | tr -d '\n ' )
actual_content=$(echo "$actual_content" | tr -d '\n ' )

if [[ "$actual_content" = "$expected_content" ]]; then
    echo ".condarc file matches expected content."
else
    echo "Error: .condarc file does not match expected content"
    exit 1
fi

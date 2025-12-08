#!/bin/bash
set -euxo pipefail

echo "Hello: PREFIX='$PREFIX'"
echo "LD_LIBRARY_PATH: ${LD_LIBRARY_PATH:-}"

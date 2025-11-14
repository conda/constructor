_conda constructor --prefix . --extract-conda-pkgs

set CONDA_PROTECT_FROZEN_ENVS=0
set CONDA_ROOT_PREFIX=%cd%
set CONDA_SAFETY_CHECKS=disabled
set CONDA_EXTRA_SAFETY_CHECKS=no
set CONDA_PKGS_DIRS=%cd%\pkgs

_conda install --offline --file conda-meta\initial-state.explicit.txt -yp .

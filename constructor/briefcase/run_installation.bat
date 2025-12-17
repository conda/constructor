set PREFIX=%cd%
_conda constructor --prefix %PREFIX% --extract-conda-pkgs

set CONDA_PROTECT_FROZEN_ENVS=0
set CONDA_ROOT_PREFIX=%PREFIX%
set CONDA_SAFETY_CHECKS=disabled
set CONDA_EXTRA_SAFETY_CHECKS=no
set CONDA_PKGS_DIRS=%PREFIX%\pkgs

_conda install --offline --file %PREFIX%\conda-meta\initial-state.explicit.txt -yp %PREFIX%

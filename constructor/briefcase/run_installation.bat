set CONDA_PROTECT_FROZEN_ENVS=0
set CONDA_ROOT_PREFIX=%cd%
set CONDA_SAFETY_CHECKS=disabled
set CONDA_EXTRA_SAFETY_CHECKS=no
set CONDA_PKGS_DIRS=%cd%\pkgs

%CONDA_ROOT_PREFIX%\_conda constructor --prefix . --extract-conda-pkgs


%CONDA_ROOT_PREFIX%\_conda install --offline --file conda-meta\initial-state.explicit.txt -yp .

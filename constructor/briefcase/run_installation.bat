set "PREFIX=%cd%"
set "BASE_PATH=%PREFIX%\base"
"%PREFIX%\_conda" constructor --prefix "%BASE_PATH%" --extract-conda-pkgs

set CONDA_PROTECT_FROZEN_ENVS=0
set "CONDA_ROOT_PREFIX=%PREFIX%"
set CONDA_SAFETY_CHECKS=disabled
set CONDA_EXTRA_SAFETY_CHECKS=no
set CONDA_PKGS_DIRS=%BASE_PATH%\pkgs

"%PREFIX%\_conda" install --offline --file "%BASE_PATH%\conda-meta\initial-state.explicit.txt" -yp "%BASE_PATH%"

set "INSTDIR=%cd%"
set "BASE_PATH=%INSTDIR%\base"
set "PREFIX=%BASE_PATH%"
set "CONDA_EXE=%INSTDIR%\_conda.exe"

"%INSTDIR%\_conda.exe" constructor --prefix "%BASE_PATH%" --extract-conda-pkgs

set CONDA_PROTECT_FROZEN_ENVS=0
set "CONDA_ROOT_PREFIX=%BASE_PATH%"
set CONDA_SAFETY_CHECKS=disabled
set CONDA_EXTRA_SAFETY_CHECKS=no
set "CONDA_PKGS_DIRS=%BASE_PATH%\pkgs"

"%INSTDIR%\_conda.exe" install --offline --file "%BASE_PATH%\conda-meta\initial-state.explicit.txt" -yp "%BASE_PATH%"

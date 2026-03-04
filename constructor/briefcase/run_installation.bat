@echo {{ 'on' if add_debug else 'off' }}
setlocal

{% macro error_block(message, code) %}
echo [ERROR] {{ message }}
>> "%LOG%" echo [ERROR] {{ message }}
exit /b {{ code }}
{% endmacro %}

rem Assign INSTDIR and normalize the path
set "INSTDIR=%~dp0.."
for %%I in ("%INSTDIR%") do set "INSTDIR=%%~fI"

set "BASE_PATH=%INSTDIR%\base"
set "PREFIX=%BASE_PATH%"
set "CONDA_EXE=%INSTDIR%\{{ conda_exe_name }}"
set "PAYLOAD_TAR=%INSTDIR%\{{ archive_name }}"

set CONDA_EXTRA_SAFETY_CHECKS=no
set CONDA_PROTECT_FROZEN_ENVS=0
set CONDA_REGISTER_ENVS={{ register_envs }}
set CONDA_SAFETY_CHECKS=disabled
set "CONDA_ROOT_PREFIX=%BASE_PATH%"
set "CONDA_PKGS_DIRS=%BASE_PATH%\pkgs"

rem Get the name of the install directory
for %%I in ("%INSTDIR%") do set "APPNAME=%%~nxI"
set "LOG=%INSTDIR%\install.log"

{%- if add_debug %}
echo ==== run_installation start ==== >> "%LOG%"
echo SCRIPT=%~f0 >> "%LOG%"
echo CWD=%CD% >> "%LOG%"
echo INSTDIR=%INSTDIR% >> "%LOG%"
echo BASE_PATH=%BASE_PATH% >> "%LOG%"
echo CONDA_EXE=%CONDA_EXE% >> "%LOG%"
echo PAYLOAD_TAR=%PAYLOAD_TAR% >> "%LOG%"
{%- endif %}

rem Consistency checks
if not exist "%CONDA_EXE%" (
  {{ error_block('CONDA_EXE not found: "%CONDA_EXE%"', 10) }}
)
if not exist "%PAYLOAD_TAR%" (
  {{ error_block('PAYLOAD_TAR not found: "%PAYLOAD_TAR%"', 11) }}
)

echo Unpacking payload...
"%CONDA_EXE%" --log-file "%LOG%" constructor extract --prefix "%INSTDIR%" --tar-from-stdin < "%PAYLOAD_TAR%"
if errorlevel 1 ( exit /b %errorlevel% )

"%CONDA_EXE%" --log-file "%LOG%" constructor extract --prefix "%BASE_PATH%" --conda-pkgs
if errorlevel 1 ( exit /b %errorlevel% )

if not exist "%BASE_PATH%" (
  {{ error_block('"%BASE_PATH%" not found!', 12) }}
)

"%CONDA_EXE%" --log-file "%LOG%" install --offline --file "%BASE_PATH%\conda-meta\initial-state.explicit.txt" -yp "%BASE_PATH%"
if errorlevel 1 ( exit /b %errorlevel% )

rem Delete the payload to save disk space.
rem A truncated placeholder of 0 bytes is recreated during uninstall
rem because MSI expects the file to be there to clean the registry.
del "%PAYLOAD_TAR%"
if errorlevel 1 ( exit /b %errorlevel% )

exit /b 0

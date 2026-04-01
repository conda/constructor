@echo {{ 'on' if add_debug else 'off' }}
rem enabledelayedexpansion is required for !VAR! expansion inside for /f loops
rem and for building UNINST_ARGS dynamically. Note that this is NOT inherited
rem from run_pre_uninstall.bat even though it sets enabledelayedexpansion there,
rem because setlocal in this script creates a new scope.
setlocal enabledelayedexpansion

{% macro error_block(message, code) %}
echo [ERROR] {{ message }}
>> "%LOG%" echo [ERROR] {{ message }}
exit /b {{ code }}
{% endmacro %}

{%- macro tee(message) -%}
echo {{ message }}
>> "%LOG%" echo {{ message }}
{%- endmacro %}

rem Assign INSTDIR and normalize the path
set "INSTDIR=%~dp0.."
for %%I in ("%INSTDIR%") do set "INSTDIR=%%~fI"

set "BASE_PATH=%INSTDIR%\base"
set "PREFIX=%BASE_PATH%"
set "CONDA_EXE=%INSTDIR%\{{ conda_exe_name }}"
set "PAYLOAD_TAR=%INSTDIR%\{{ archive_name }}"
set "CONDA_ROOT_PREFIX=%BASE_PATH%"

rem Get the name of the install directory
for %%I in ("%INSTDIR%") do set "APPNAME=%%~nxI"
set "LOG=%INSTDIR%\uninstall.log"

{%- if script_env_variables %}
rem User-defined environment variables for pre/post install scripts
{%- for key, val in script_env_variables.items() %}
set "{{ key }}={{ val }}"
{%- endfor %}
{%- endif %}

rem Installer metadata for pre-uninstall script
set "INSTALLER_NAME={{ installer_name }}"
set "INSTALLER_VER={{ installer_version }}"
set "INSTALLER_PLAT={{ installer_platform }}"
set "INSTALLER_TYPE=MSI"
rem INSTALLER_UNATTENDED is not available for MSI installers.
rem Detecting silent mode requires UILevel from WiX, which would need
rem changes to the briefcase-windows-app-template to pass to this script.

rem Determine install mode from .nonadmin marker file written at install time
if exist "%BASE_PATH%\.nonadmin" (
    set "REG_HIVE=HKCU"
) else (
    set "REG_HIVE=HKLM"
)

{%- if add_debug %}
>> "%LOG%" echo ==== pre_uninstall start ====
>> "%LOG%" echo SCRIPT=%~f0
>> "%LOG%" echo CWD=%CD%
>> "%LOG%" echo INSTDIR=%INSTDIR%
>> "%LOG%" echo BASE_PATH=%BASE_PATH%
>> "%LOG%" echo CONDA_EXE=%CONDA_EXE%
>> "%LOG%" echo PAYLOAD_TAR=%PAYLOAD_TAR%
>> "%LOG%" echo CONDA_ROOT_PREFIX=%CONDA_ROOT_PREFIX%
>> "%LOG%" echo REG_HIVE=%REG_HIVE%
>> "%LOG%" echo ALLUSERS=%ALLUSERS%
>> "%LOG%" echo OPTION_REMOVE_USER_DATA=%OPTION_REMOVE_USER_DATA%
>> "%LOG%" echo OPTION_REMOVE_CACHES=%OPTION_REMOVE_CACHES%
>> "%LOG%" echo OPTION_REMOVE_CONFIG_FILES=%OPTION_REMOVE_CONFIG_FILES%
"%CONDA_EXE%" --version >> "%LOG%" 2>&1
{%- endif %}

rem Consistency checks
if not exist "%CONDA_EXE%" (
  {{ error_block('CONDA_EXE not found: "%CONDA_EXE%"', 10) }}
)
if "%ALLUSERS%"=="0" (
  if not exist "%BASE_PATH%\.nonadmin" (
    {{ error_block('Insufficient permissions. Please re-run the uninstallation as administrator.', 11) }}
  )
)

rem Recreate an empty payload tar. This file was deleted during installation but the
rem MSI installer expects it to exist.
type nul > "%PAYLOAD_TAR%"
if errorlevel 1 (
  {{ error_block('Failed to create "%PAYLOAD_TAR%"', '%errorlevel%') }}
)

{%- if has_pre_uninstall %}
rem Run user-supplied pre-uninstall script
{{ tee("Running pre-uninstall script...") }}
call "%BASE_PATH%\pkgs\user_pre_uninstall.bat"
if errorlevel 1 ( exit /b %errorlevel% )
{%- endif %}

rem Remove PATH entries only for user-scoped installs (mirrors NSIS .nonadmin check)
{%- set pathflag = "--condabin" if initialize_conda == "condabin" else "--classic" %}
if exist "%BASE_PATH%\.nonadmin" (
    {{ tee("Removing from PATH...") }}
    "%CONDA_EXE%" constructor windows path --remove=user --prefix "%INSTDIR%" {{ pathflag }} --log-file "%LOG%"
    if errorlevel 1 ( exit /b %errorlevel% )
)

{%- if has_python %}
rem Remove Python registry entries only if InstallPath matches BASE_PATH.
{{ tee("Checking Python registry entries...") }}
call :remove_python_registry "%REG_HIVE%" "%BASE_PATH%"
goto :after_remove_python_registry

:remove_python_registry
set "REG_HIVE_ARG=%~1"
set "BASE_PATH_ARG=%~2"
rem REG64 forces the 64-bit registry view since the MSI engine runs as a 32-bit process.
set "REG64=/reg:64"
rem Enumerate all subkeys under PythonCore (e.g. 3.11, 3.12, ...)
for /f "tokens=*" %%K in ('reg query "%REG_HIVE_ARG%\Software\Python\PythonCore" %REG64% 2^>nul') do (
    rem Read the InstallPath default value for each subkey
    for /f "tokens=2*" %%A in ('reg query "%%K\InstallPath" /ve %REG64% 2^>nul') do (
        rem Only delete if InstallPath matches our installation directory
        if /i "%%B"=="%BASE_PATH_ARG%" (
            echo Removing Python registry key: %%K
            >> "%LOG%" echo Removing Python registry key: %%K
            reg delete "%%K" /f %REG64% >> "%LOG%" 2>&1
            if errorlevel 1 ( exit /b %errorlevel% )
        )
    )
)
exit /b 0

:after_remove_python_registry
{%- endif %}

rem Run constructor uninstall, conditionally passing optional flags
set "UNINST_ARGS="
if "%OPTION_REMOVE_USER_DATA%"=="1" (
    set "UNINST_ARGS=!UNINST_ARGS! --remove-user-data"
)
if "%OPTION_REMOVE_CACHES%"=="1" (
    set "UNINST_ARGS=!UNINST_ARGS! --remove-caches"
)
if "%OPTION_REMOVE_CONFIG_FILES%"=="1" (
    rem User installs (.nonadmin marker exists) only remove user config files.
    rem Admin installs remove both user and system config files.
    if exist "%BASE_PATH%\.nonadmin" (
        set "UNINST_ARGS=!UNINST_ARGS! --remove-config-files=user"
    ) else (
        set "UNINST_ARGS=!UNINST_ARGS! --remove-config-files=all"
    )
)
{{ tee("Running constructor uninstall...") }}
"%CONDA_EXE%" constructor uninstall --prefix "%BASE_PATH%"!UNINST_ARGS! --log-file "%LOG%"
if errorlevel 1 ( exit /b %errorlevel% )

rem If we reached this far without any errors, remove any log files.
if exist "%INSTDIR%\install.log" del "%INSTDIR%\install.log"
if exist "%INSTDIR%\uninstall.log" del "%INSTDIR%\uninstall.log"

exit /b 0

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

rem Assign INSTDIR and normalize the path
set "INSTDIR=%~dp0.."
for %%I in ("%INSTDIR%") do set "INSTDIR=%%~fI"

set "BASE_PATH=%INSTDIR%\base"
set "PREFIX=%BASE_PATH%"
set "CONDA_EXE=%INSTDIR%\{{ conda_exe_name }}"
set "PAYLOAD_TAR=%INSTDIR%\{{ archive_name }}"

rem Get the name of the install directory
for %%I in ("%INSTDIR%") do set "APPNAME=%%~nxI"
set "LOG=%INSTDIR%\uninstall.log"

rem Determine install mode from .nonadmin marker file written at install time
if exist "%INSTDIR%\.nonadmin" (
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
>> "%LOG%" echo REG_HIVE=%REG_HIVE%
>> "%LOG%" echo OPTION_REMOVE_USER_DATA=%OPTION_REMOVE_USER_DATA%
>> "%LOG%" echo OPTION_REMOVE_CACHES=%OPTION_REMOVE_CACHES%
"%CONDA_EXE%" --version >> "%LOG%" 2>&1
{%- endif %}

rem Consistency checks
if not exist "%CONDA_EXE%" (
  {{ error_block('CONDA_EXE not found: "%CONDA_EXE%"', 10) }}
)

rem Recreate an empty payload tar. This file was deleted during installation but the
rem MSI installer expects it to exist.
type nul > "%PAYLOAD_TAR%"
if errorlevel 1 (
  {{ error_block('Failed to create "%PAYLOAD_TAR%"', '%errorlevel%') }}
)

rem Remove shortcuts unconditionally
echo Removing shortcuts...
>> "%LOG%" echo Removing shortcuts...
"%CONDA_EXE%" constructor --prefix "%BASE_PATH%" --rm-menus --log-file "%LOG%"
if errorlevel 1 ( exit /b %errorlevel% )

rem Remove PATH entries only for user-scoped installs (mirrors NSIS .nonadmin check)
{%- set pathflag = "--condabin" if initialize_conda == "condabin" else "--classic" %}
if "%REG_HIVE%"=="HKCU" (
    echo Removing from PATH...
    >> "%LOG%" echo Removing from PATH...
    "%CONDA_EXE%" constructor windows path --remove=user --prefix "%INSTDIR%" {{ pathflag }} --log-file "%LOG%"
    if errorlevel 1 ( exit /b %errorlevel% )
)

{%- if has_python %}
rem Remove Python registry entries only if InstallPath matches BASE_PATH.
rem /reg:64 ensures we query the 64-bit registry view regardless of MSI process bitness.
echo Checking Python registry entries...
>> "%LOG%" echo Checking Python registry entries...
call :remove_python_registry "%REG_HIVE%" "%BASE_PATH%"
goto :after_remove_python_registry

:remove_python_registry
set "REG_HIVE_ARG=%~1"
set "BASE_PATH_ARG=%~2"
rem REG64 forces the 64-bit registry view since the MSI engine runs as a 32-bit process.
set "REG64=/reg:64"
rem Enumerate all subkeys under PythonCore (e.g. 3.11, 3.13)
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

rem Remove .nonadmin marker file if it exists
if exist "%INSTDIR%\.nonadmin" (
    echo Removing .nonadmin marker file...
    >> "%LOG%" echo Removing .nonadmin marker file...
    del "%INSTDIR%\.nonadmin"
    if errorlevel 1 ( exit /b %errorlevel% )
)

rem Run constructor uninstall, conditionally passing optional flags
set "UNINST_ARGS="
if "%OPTION_REMOVE_USER_DATA%"=="1" (
    set "UNINST_ARGS=!UNINST_ARGS! --remove-user-data"
)
if "%OPTION_REMOVE_CACHES%"=="1" (
    set "UNINST_ARGS=!UNINST_ARGS! --remove-caches"
)
echo Running constructor uninstall...
>> "%LOG%" echo Running constructor uninstall...
"%CONDA_EXE%" constructor uninstall --prefix "%BASE_PATH%"!UNINST_ARGS! --log-file "%LOG%"
if errorlevel 1 ( exit /b %errorlevel% )

rem If we reached this far without any errors, remove any log files.
if exist "%INSTDIR%\install.log" del "%INSTDIR%\install.log"
if exist "%INSTDIR%\uninstall.log" del "%INSTDIR%\uninstall.log"

exit /b 0

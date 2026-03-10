@echo {{ 'on' if add_debug else 'off' }}
rem enabledelayedexpansion is required for !REG_HIVE! expansion when
rem registering Python, and because setlocal creates a new scope that
rem does not inherit enabledelayedexpansion from the calling script.
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
>> "%LOG%" echo ==== run_installation start ====
>> "%LOG%" echo SCRIPT=%~f0
>> "%LOG%" echo CWD=%CD%
>> "%LOG%" echo INSTDIR=%INSTDIR%
>> "%LOG%" echo BASE_PATH=%BASE_PATH%
>> "%LOG%" echo CONDA_EXE=%CONDA_EXE%
>> "%LOG%" echo PAYLOAD_TAR=%PAYLOAD_TAR%
>> "%LOG%" echo ALLUSERS=%ALLUSERS%
>> "%LOG%" echo OPTION_ENABLE_SHORTCUTS=%OPTION_ENABLE_SHORTCUTS%
>> "%LOG%" echo OPTION_INITIALIZE_CONDA=%OPTION_INITIALIZE_CONDA%
{%- if has_python %}
>> "%LOG%" echo OPTION_REGISTER_PYTHON=%OPTION_REGISTER_PYTHON%
{%- endif %}
>> "%LOG%" echo OPTION_CLEAR_PACKAGE_CACHE=%OPTION_CLEAR_PACKAGE_CACHE%
{%- endif %}

rem Consistency checks
if not exist "%CONDA_EXE%" (
  {{ error_block('CONDA_EXE not found: "%CONDA_EXE%"', 10) }}
)
if not exist "%PAYLOAD_TAR%" (
  {{ error_block('PAYLOAD_TAR not found: "%PAYLOAD_TAR%"', 11) }}
)

{{ tee("Unpacking payload...") }}
"%CONDA_EXE%" constructor extract --prefix "%INSTDIR%" --tar-from-stdin --log-file "%LOG%" < "%PAYLOAD_TAR%"
if errorlevel 1 ( exit /b %errorlevel% )

"%CONDA_EXE%" constructor extract --prefix "%BASE_PATH%" --conda-pkgs --log-file "%LOG%"
if errorlevel 1 ( exit /b %errorlevel% )

if not exist "%BASE_PATH%" (
  {{ error_block('"%BASE_PATH%" not found!', 12) }}
)

rem Create .nonadmin marker file for user-scoped installs inside BASE_PATH.
rem This is used by the uninstaller (and menuinst) to determine the install mode.
if "%ALLUSERS%"=="0" (
    echo. > "%BASE_PATH%\.nonadmin"
    if errorlevel 1 ( exit /b %errorlevel% )
)

rem Install packages, conditionally creating shortcuts
if "%OPTION_ENABLE_SHORTCUTS%"=="1" (
    {{ tee("Installing packages with shortcuts...") }}
    "%CONDA_EXE%" install --offline -yp "%BASE_PATH%" --file "%BASE_PATH%\conda-meta\initial-state.explicit.txt" {{ shortcuts }} {{ no_rcs_arg }} --log-file "%LOG%"
) else (
    {{ tee("Installing packages...") }}
    "%CONDA_EXE%" install --offline -yp "%BASE_PATH%" --file "%BASE_PATH%\conda-meta\initial-state.explicit.txt" --no-shortcuts {{ no_rcs_arg }} --log-file "%LOG%"
)
if errorlevel 1 ( exit /b %errorlevel% )

rem Delete the payload to save disk space.
rem A truncated placeholder of 0 bytes is recreated during uninstall
rem because MSI expects the file to be there to clean the registry.
del "%PAYLOAD_TAR%"
if errorlevel 1 ( exit /b %errorlevel% )

rem Add to PATH / run conda init if the option was selected
{%- set pathflag = "--condabin" if initialize_conda == "condabin" else "--classic" %}
if "%OPTION_INITIALIZE_CONDA%"=="1" (
    {{ tee("Adding to PATH...") }}
    "%CONDA_EXE%" constructor windows path --prepend=user --prefix "%INSTDIR%" {{ pathflag }} --log-file "%LOG%"
    if errorlevel 1 ( exit /b %errorlevel% )
)

{%- if has_python %}
rem Register as system Python if the option was selected
if "%OPTION_REGISTER_PYTHON%"=="1" (
    {{ tee("Registering as system Python...") }}
    if "%ALLUSERS%"=="1" (
        set "REG_HIVE=HKLM"
    ) else (
        set "REG_HIVE=HKCU"
    )
    rem PY_REG is the base registry path for this Python version.
    rem /v sets a named value, /ve sets the default (unnamed) value, /d sets the data,
    rem /f forces overwrite without prompting.
    rem REG64 forces the 64-bit registry view since the MSI engine runs as a 32-bit process.
    set "REG64=/reg:64"
    set "PY_REG=!REG_HIVE!\Software\Python\PythonCore\{{ pyver_components[:2] | join(".") }}"
    reg add "!PY_REG!\Help\Main Python Documentation" /v "Main Python Documentation" /d "%BASE_PATH%\Doc\python{{ pyver_components | join("") }}.chm" /f !REG64! >> "%LOG%" 2>&1
    if errorlevel 1 ( exit /b %errorlevel% )
    reg add "!PY_REG!\InstallPath" /ve /d "%BASE_PATH%" /f !REG64! >> "%LOG%" 2>&1
    if errorlevel 1 ( exit /b %errorlevel% )
    reg add "!PY_REG!\InstallPath" /v "ExecutablePath" /d "%BASE_PATH%\python.exe" /f !REG64! >> "%LOG%" 2>&1
    if errorlevel 1 ( exit /b %errorlevel% )
    reg add "!PY_REG!\InstallPath" /v "InstallGroup" /d "Python {{ pyver_components[:2] | join(".") }}" /f !REG64! >> "%LOG%" 2>&1
    if errorlevel 1 ( exit /b %errorlevel% )
    reg add "!PY_REG!\Modules" /ve /d "" /f !REG64! >> "%LOG%" 2>&1
    if errorlevel 1 ( exit /b %errorlevel% )
    reg add "!PY_REG!\PythonPath" /ve /d "%BASE_PATH%\Lib;%BASE_PATH%\DLLs" /f !REG64! >> "%LOG%" 2>&1
    if errorlevel 1 ( exit /b %errorlevel% )
)
{%- endif %}

rem Clear the package cache if the option was selected
if "%OPTION_CLEAR_PACKAGE_CACHE%"=="1" (
    {{ tee("Clearing package cache...") }}
    "%CONDA_EXE%" clean --all --force-pkgs-dirs --yes {{ no_rcs_arg }} --log-file "%LOG%"
    if errorlevel 1 ( exit /b %errorlevel% )
)

exit /b 0

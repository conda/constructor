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

rem Get the name of the install directory
for %%I in ("%INSTDIR%") do set "APPNAME=%%~nxI"
set "LOG=%INSTDIR%\uninstall.log"

{%- if add_debug %}
echo ==== pre_uninstall start ==== >> "%LOG%"
echo SCRIPT=%~f0 >> "%LOG%"
echo CWD=%CD% >> "%LOG%"
echo INSTDIR=%INSTDIR% >> "%LOG%"
echo BASE_PATH=%BASE_PATH% >> "%LOG%"
echo CONDA_EXE=%CONDA_EXE% >> "%LOG%"
echo PAYLOAD_TAR=%PAYLOAD_TAR% >> "%LOG%"
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

"%CONDA_EXE%" --log-file "%LOG%" constructor uninstall --prefix "%BASE_PATH%"
if errorlevel 1 ( exit /b %errorlevel% )

rem If we reached this far without any errors, remove any log-files.
if exist "%INSTDIR%\install.log" del "%INSTDIR%\install.log"
if exist "%INSTDIR%\uninstall.log" del "%INSTDIR%\uninstall.log"

exit /b 0

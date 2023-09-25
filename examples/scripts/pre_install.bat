if not "%INSTALLER_NAME%" == "Scripts" exit 1
if not "%INSTALLER_VER%" == "X" exit 1
if not "%INSTALLER_PLAT%" == "win-64" exit 1
if not "%INSTALLER_TYPE%" == "EXE" exit 1
if "%PREFIX%" == "" exit 1
if not "%CUSTOM_VARIABLE_1%" == "FIR$T CUSTOM STRING WITH SPACES AND @*! CHARACTERS" exit 1
if not "%CUSTOM_VARIABLE_2%" == "$ECOND CUSTOM STRING WITH SPACES AND @*! CHARACTERS" exit 1
echo Added by pre-install script > "%PREFIX%\pre_install_sentinel.txt"

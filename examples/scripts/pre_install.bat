if not "%INSTALLER_NAME%" == "Scripts" exit 1
if not "%INSTALLER_VER%" == "X" exit 1
if not "%INSTALLER_PLAT%" == "win-64" exit 1
if not "%INSTALLER_TYPE%" == "EXE" exit 1
echo Added by pre-install script > "%PREFIX%\pre_install_sentinel.txt"

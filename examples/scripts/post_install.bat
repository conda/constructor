if not "%INSTALLER_NAME%" == "Scripts" exit 1
if not "%INSTALLER_VER%" == "X" exit 1
if not "%INSTALLER_PLAT%" == "win-64" exit 1
if not "%INSTALLER_TYPE%" == "EXE" exit 1
if "%PREFIX%" == "" exit 1
if not exist "%PREFIX%\pre_install_sentinel.txt" exit 1
echo Added by post-install script > "%PREFIX%\post_install_sentinel.txt"

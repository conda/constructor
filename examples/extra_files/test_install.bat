echo Added by post-install script > "%PREFIX%\post_install_sentinel.txt"

if not exist "%PREFIX%\more_data\README.md" exit 1
if not exist "%PREFIX%\something2.txt" exit 1

echo Added by test-install script > "%PREFIX%\test_install_sentinel.txt"

if not exist "%PREFIX%\more_data\README.md" exit 1
if not exist "%PREFIX%\something2.txt" exit 1
if not exist "%PREFIX%\TEST_LICENSE.txt" exit 1

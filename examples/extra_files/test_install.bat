echo [DEBUG] test_install.bat starting
echo [DEBUG] PREFIX=%PREFIX%
echo [DEBUG] Listing PREFIX directory:
dir "%PREFIX%" 2>&1
echo [DEBUG] Listing PREFIX\more_data directory:
dir "%PREFIX%\more_data" 2>&1

echo Added by test-install script > "%PREFIX%\test_install_sentinel.txt"

if not exist "%PREFIX%\more_data\README.md" (
    echo [ERROR] Missing: %PREFIX%\more_data\README.md
    exit /b 1
)
if not exist "%PREFIX%\something2.txt" (
    echo [ERROR] Missing: %PREFIX%\something2.txt
    exit /b 2
)
if not exist "%PREFIX%\TEST_LICENSE.txt" (
    echo [ERROR] Missing: %PREFIX%\TEST_LICENSE.txt
    exit /b 3
)
echo [DEBUG] All files found, test_install.bat completed successfully

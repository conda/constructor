echo Added by test-install script > "%PREFIX%\test_install_sentinel.txt"

:: base env has python 3.10
if not exist "%PREFIX%\conda-meta\history" exit 1
"%PREFIX%\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 10)" || goto :error

:: extra env named 'py311' has python 3.11
if not exist "%PREFIX%\envs\py311\conda-meta\history" exit 1
"%PREFIX%\envs\py311\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 11)" || goto :error

:: extra env named 'dav1d' only contains dav1d, no python
if not exist "%PREFIX%\envs\dav1d\conda-meta\history" exit 1
if exist "%PREFIX%\envs\dav1d\python.exe" exit 1
"%PREFIX%\envs\dav1d\Library\bin\dav1d.exe" --version || goto :error

goto :EOF

:error
echo Failed with error #%errorlevel%.
exit %errorlevel%

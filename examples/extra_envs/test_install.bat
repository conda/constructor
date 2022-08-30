:: base env
if not exist "%PREFIX%\conda-meta\history" exit 1
"%PREFIX%\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 7)" || goto :error

:: extra env named 'py38'
if not exist "%PREFIX%\envs\py38\conda-meta\history" exit 1
"%PREFIX%\envs\py38\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 8)" || goto :error

:: extra env named 'dav1d' only contains dav1d, no python
if not exist "%PREFIX%\envs\dav1d\conda-meta\history" exit 1
if exist "%PREFIX%\envs\dav1d\python.exe" exit 1
"%PREFIX%\envs\dav1d\Library\bin\dav1d.exe" --version || goto :error

echo "This is an error on purpose"
exit 1

goto :EOF

:error
echo Failed with error #%errorlevel%.
exit %errorlevel%

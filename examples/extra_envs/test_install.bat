:: base env has python 3.9
if not exist "%PREFIX%\conda-meta\history" exit 1
"%PREFIX%\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 9)" || goto :error

:: extra env named 'py310' has python 3.10
if not exist "%PREFIX%\envs\py310\conda-meta\history" exit 1
"%PREFIX%\envs\py310\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 10)" || goto :error

:: extra env named 'dav1d' only contains dav1d, no python
if not exist "%PREFIX%\envs\dav1d\conda-meta\history" exit 1
if exist "%PREFIX%\envs\dav1d\python.exe" exit 1
"%PREFIX%\envs\dav1d\Library\bin\dav1d.exe" --version || goto :error

goto :EOF

:error
echo Failed with error #%errorlevel%.
exit %errorlevel%

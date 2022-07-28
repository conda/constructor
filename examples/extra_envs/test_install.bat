:: base env
if not exist "%PREFIX%\conda-meta\history" exit 1
"%PREFIX%\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 7)" || goto :error

:: extra env named 'py38'
if not exist "%PREFIX%\envs\py38\conda-meta\history" exit 1
"%PREFIX%\envs\py38\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 8)" || goto :error

:: extra env named 'py39'
if not exist "%PREFIX%\envs\py39\conda-meta\history" exit 1
"%PREFIX%\envs\py39\python.exe" -c "from sys import version_info; assert version_info[:2] == (3, 9)" || goto :error

goto :EOF

:error
echo Failed with error #%errorlevel%.
exit %errorlevel%

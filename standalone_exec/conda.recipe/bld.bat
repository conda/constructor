COPY conda_src\conda\core\path_actions.py %SP_DIR%\conda\core\path_actions.py
COPY conda_src\conda\utils.py %SP_DIR%\conda\utils.py

COPY menuinst_src\menuinst\__init__.py %SP_DIR%\menuinst\__init__.py
COPY menuinst_src\menuinst\win32.py %SP_DIR%\menuinst\win32.py

:: -F is to create a single file
pyinstaller -F -n conda.exe conda.exe.py
MKDIR %PREFIX%\standalone_conda
MOVE dist\conda.exe %PREFIX%\standalone_conda\conda.exe
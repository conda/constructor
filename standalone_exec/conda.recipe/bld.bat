:: -F is to create a single file

pyinstaller -F -n conda.exe conda.exe.py
MOVE work/dist/conda.exe %PREFIX%/conda-%conda_version%.exe
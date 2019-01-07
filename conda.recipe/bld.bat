pyinstaller constructor\install.py --onefile -n constructor_install
COPY dist\constructor_install.exe %LIBRARY_BIN%\bin

python setup.py install --single-version-externally-managed --record=record.txt
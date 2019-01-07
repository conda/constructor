pyinstaller constructor/install.py --onefile -n constructor_install
cp dist/constructor_install $PREFIX/bin

python setup.py install --single-version-externally-managed --record=record.txt

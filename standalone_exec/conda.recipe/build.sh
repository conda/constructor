rsync -avz --update --existing conda_src/conda $SP_DIR/conda
rsync -avz --update --existing menuinst_src/menuinst $SP_DIR/menuinst
# -F is to create a single file
# -s strips executables and libraries
pyinstaller -F -s -n conda.exe conda.exe.py
mv dist/conda.exe $PREFIX/conda-${CONDA_VERSION}.exe
# clean up .pyc files that pyinstaller creates
rm -rf $PREFIX/lib

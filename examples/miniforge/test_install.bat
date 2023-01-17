echo Added by test-install script > "%PREFIX%\test_install_sentinel.txt"
SetLocal EnableDelayedExpansion

@ECHO ON
call "%PREFIX%\Scripts\activate.bat
conda info || exit 1
conda config --show-sources || exit 1
python -c "from conda.base.context import context as c; assert len(c.channels) == 1 and c.channels[0] == 'conda-forge', c.channels"

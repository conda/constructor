echo Added by test-install script > "%PREFIX%\test_install_sentinel.txt"
SetLocal EnableDelayedExpansion

@ECHO ON
call "%PREFIX%\Scripts\activate.bat
conda info || exit 1
conda config --show-sources || exit 1
conda config --show --json | python -c "import sys, json; info = json.loads(sys.stdin.read()); assert info['channels'] == ['conda-forge'], info"

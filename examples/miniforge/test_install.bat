echo Added by post-install script > "%PREFIX%\post_install_sentinel.txt"

@ECHO ON
call "%PREFIX%\Scripts\activate.bat
conda install -yq jq || exit 1
conda config --show-sources || exit 1
conda config --json --show | jq -r ".channels[0]" > temp.txt
set /p OUTPUT=<temp.txt
if not "%OUTPUT%" == "conda-forge" exit 1

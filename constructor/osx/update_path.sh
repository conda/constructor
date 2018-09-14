#!/bin/sh
# Copyright (c) 2012-2017 Anaconda, Inc.
# All rights reserved.

# $2 is the install location, which is ~ by default, but which the user can
# change.
PREFIX=$(echo "$2/__NAME_LOWER__" | sed -e 's,//,/,g')

# Logic borrowed from the official Python Mac OS X installer
if [ -e "${HOME}/.bash_profile" ]; then
    BASH_RC="${HOME}/.bash_profile"
elif [ -e "${HOME}/.bash_login" ]; then
    BASH_RC="${HOME}/.bash_login"
elif [ -e "${HOME}/.profile" ]; then
    BASH_RC="${HOME}/.profile"
else
    BASH_RC="${HOME}/.bash_profile"
fi

BASH_RC_BAK="${BASH_RC}-__NAME_LOWER__.bak"

cp -fp $BASH_RC ${BASH_RC_BAK}

echo "
Initializing __NAME__ in $BASH_RC

For this change to become active, you have to open a new terminal."

cat <<EOF >> "$BASH_RC"
# added by __NAME__ __VERSION__ installer
# >>> conda init >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="\$(CONDA_REPORT_ERRORS=false '$PREFIX/bin/conda' shell.bash hook 2> /dev/null)"
if [ \$? -eq 0 ]; then
    \\eval "\$__conda_setup"
else
    if [ -f "$PREFIX/etc/profile.d/conda.sh" ]; then
        . "$PREFIX/etc/profile.d/conda.sh"
        CONDA_CHANGEPS1=false conda activate base
    else
        \\export PATH="$PREFIX/bin:\$PATH"
    fi
fi
unset __conda_setup
# <<< conda init <<<
EOF

chown "$USER" "$BASH_RC" "$BASH_RC_BAK"
exit 0

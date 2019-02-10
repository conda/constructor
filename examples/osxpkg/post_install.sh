#!/bin/bash

# $2 is the install location, ($HOME by default)
if [ xxx$PREFIX == 'xxx' ]; then
    PREFIX=$(echo "$2/__NAME_LOWER__" | sed -e 's,//,/,g')
fi

echo '## Hello from Post_install script ' > $HOME/postinstall.txt
printenv >> $HOME/postinstall.txt

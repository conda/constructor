#!/bin/bash

if [[ -e "$2/__NAME_LOWER__" ]]; then
    # The OS X installer provides no way to send a message to the user if this
    # script fails. So we use AppleScript to do it.

    # By default, osascript doesn't allow user interaction, so we have to work
    # around it.  http://stackoverflow.com/a/11874852/161801
    (osascript -e "try
tell application \"Installer\"
display alert \"Path $2/__NAME_LOWER__ already exists. Please, relaunch the installer and choose another location in the Destination Select step.\" buttons {\"OK\"} default button {\"OK\"}
end
activate app (path to frontmost application as text)
answer
end")
    exit 1
fi

# Check if the path has spaces
case "$2" in
     *\ * )
           (osascript -e "try
tell application \"Installer\"
display alert \"__NAME__ cannot be installed in $2 because the path contains spaces. Please, relaunch the installer and choose another location in the Destination Select step.\" buttons {\"OK\"} default button {\"OK\"}
end
activate app (path to frontmost application as text)
answer
end")
           exit 1
          ;;
       *)

           ;;
esac

#!/bin/bash
# Perform some checks before the actual installation starts.

# You might be tempted to use Distribution.xml's `volume-check` and `installer-check`
# tags with some of the limited JavaScript, but querying the user directory requires
# additional permissions and that grants a very scary message (this installer wants
# to run some code that can harm your computer!). Interestingly, preinstall.sh is not
# affected by those restrictions, but it's only executed once the installer has begun
# so the only way to prevent an action is to abort and start again from the beginning.
set -euo pipefail

PREFIX="$2/{{ pkg_name_lower }}"
echo "PREFIX=$PREFIX"

if [[ -e "$PREFIX" ]]; then
    # The OS X installer provides no way to send a message to the user if this
    # script fails. So we use AppleScript to do it.

    # By default, osascript doesn't allow user interaction, so we have to work
    # around it.  http://stackoverflow.com/a/11874852/161801
    logger -p "install.info" "ERROR: __PATH_EXISTS_ERROR_TEXT__" || echo "ERROR: __PATH_EXISTS_ERROR_TEXT__"
    (osascript -e "try
tell application (path to frontmost application as text)
set theAlertText to \"Chosen path already exists!\"
set theAlertMessage to \"__PATH_EXISTS_ERROR_TEXT__\"
display alert theAlertText message theAlertMessage as critical buttons {\"OK\"} default button {\"OK\"}
end
activate app (path to frontmost application as text)
answer
end")
    exit 1
fi

#if check_path_spaces is True
# Check if the path has spaces
case "$PREFIX" in
    *\ * )
        logger -p "install.info" "ERROR: '$PREFIX' contains spaces!" || echo "ERROR: '$PREFIX' contains spaces!"
        (osascript -e "try
tell application (path to frontmost application as text)
set theAlertText to \"Chosen path contain spaces!\"
set theAlertMessage to \"'$PREFIX' contains spaces. Please, relaunch the installer and choose another location in the Destination Select step.\"
display alert theAlertText message theAlertMessage as critical buttons {\"OK\"} default button {\"OK\"}
end
activate app (path to frontmost application as text)
answer
end")
        exit 1
        ;;
    *)

        ;;
esac
#endif

exit 0

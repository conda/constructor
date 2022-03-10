#!/bin/bash
# Perform some checks before the actual installation starts.

# You might be tempted to use Distribution.xml's `volume-check` and `installer-check`
# tags with some of the limited JavaScript, but querying the user directory requires
# additional permissions and that grants a very scary message (this installer wants
# to run some code that can harm your computer!). Interestingly, preinstall.sh is not
# affected by those restrictions, but it's only executed once the installer has begun
# so the only way to prevent an action is to abort and start again from the beginning.

if [[ -e "$2/__NAME_LOWER__" ]]; then
    # The OS X installer provides no way to send a message to the user if this
    # script fails. So we use AppleScript to do it.

    # By default, osascript doesn't allow user interaction, so we have to work
    # around it.  http://stackoverflow.com/a/11874852/161801
    (osascript -e "try
tell application (path to frontmost application as text)
set theAlertText to \"Chosen path already exists!\"
set theAlertMessage to \"'$2/__NAME_LOWER__' already exists. Please, relaunch the installer and choose another location in the Destination Select step.\"
display alert theAlertText message theAlertMessage as critical buttons {\"OK\"} default button {\"OK\"}
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
tell application (path to frontmost application as text)
set theAlertText to \"Chosen path contain spaces!\"
set theAlertMessage to \"'$2/__NAME_LOWER__' contains spaces. Please, relaunch the installer and choose another location in the Destination Select step.\"
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

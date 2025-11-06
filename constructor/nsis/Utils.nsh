# Miscellaneous helpers.

; Slightly modified version of http://nsis.sourceforge.net/IsWritable
Function IsWritable
  !define IsWritable `!insertmacro IsWritableCall`

  !macro IsWritableCall _PATH _RESULT
    Push `${_PATH}`
    Call IsWritable
    Pop ${_RESULT}
  !macroend

  Exch $R0
  Push $R1

start:
  # Checks if $R0 is not empty.
  StrLen $R1 $R0
  StrCmp $R1 0 exit
  # Checks if $R0 exists and is a directory.
  ${GetFileAttributes} $R0 "DIRECTORY" $R1
  StrCmp $R1 1 direxists
  # $R0 doesn't exist, getting parent.
  ${GetParent} $R0 $R0
  Goto start

direxists:
  # Checks if $R0 is a directory.
  ${GetFileAttributes} $R0 "DIRECTORY" $R1
  StrCmp $R1 0 nook

  # The directory exists. Try creating a file
  ClearErrors
  FileOpen $R2 $R0\.can_file_be_written.dat w
  FileClose $R2
  Delete $R0\.can_file_be_written.dat
  ${If} ${Errors}
    StrCpy $R1 1
  ${Else}
    StrCpy $R1 0
  ${EndIf}
  Goto exit

nook:
  StrCpy $R1 0

exit:
  Exch
  Pop $R0
  Exch $R1

FunctionEnd

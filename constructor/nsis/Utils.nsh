# Miscellaneous helpers.

# We're not using RIndexOf at the moment, so ifdef it out for now (which
# prevents the compiler warnings about an unused function).
!ifdef INDEXOF
Function IndexOf
    Exch $R0
    Exch
    Exch $R1
    Push $R2
    Push $R3

    StrCpy $R3 $R0
    StrCpy $R0 -1
    IntOp $R0 $R0 + 1

    StrCpy $R2 $R3 1 $R0
    StrCmp $R2 "" +2
    StrCmp $R2 $R1 +2 -3

    StrCpy $R0 -1

    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

!macro IndexOf Var Str Char
    Push "${Char}"
    Push "${Str}"
    Call IndexOf
    Pop "${Var}"
    !macroend
!define IndexOf "!insertmacro IndexOf"

Function RIndexOf
    Exch $R0
    Exch
    Exch $R1
    Push $R2
    Push $R3

    StrCpy $R3 $R0
    StrCpy $R0 0
    IntOp $R0 $R0 + 1
    StrCpy $R2 $R3 1 -$R0
    StrCmp $R2 "" +2
    StrCmp $R2 $R1 +2 -3

    StrCpy $R0 -1

    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

!macro RIndexOf Var Str Char
    Push "${Char}"
    Push "${Str}"
    Call RIndexOf
    Pop "${Var}"
!macroend

!define RIndexOf "!insertmacro RIndexOf"
!endif

!macro StrStr
    Exch $R1 ; st=haystack,old$R1, $R1=needle
    Exch     ; st=old$R1,haystack
    Exch $R2 ; st=old$R1,old$R2, $R2=haystack
    Push $R3
    Push $R4
    Push $R5
    StrLen $R3 $R1
    StrCpy $R4 0
    ; $R1=needle
    ; $R2=haystack
    ; $R3=len(needle)
    ; $R4=cnt
    ; $R5=tmp
    loop:
        StrCpy $R5 $R2 $R3 $R4
        StrCmp $R5 $R1 done
        StrCmp $R5 "" done
        IntOp $R4 $R4 + 1
        Goto loop
     done:
     StrCpy $R1 $R2 "" $R4
     Pop $R5
     Pop $R4
     Pop $R3
     Pop $R2
     Exch $R1
!macroend

!macro GetShortPathName
    Pop $0
    # Return the 8.3 short path name for $0.  We ensure $0 exists by calling
    # SetOutPath first (kernel32::GetShortPathName() fails otherwise).
    SetOutPath $0
    Push $0
    Push ' '
    Call StrStr
    Pop $1
    ${If} $1 != ""
        # Our installation directory has a space, so use the short name from
        # here in.  (This ensures no directories with spaces are written to
        # registry values or configuration files.)  After GetShortPathName(),
        # $0 will have the new name and $1 will have the length (if it's 0,
        # assume an error occurred and leave $INSTDIR as it is).
        System::Call "kernel32::GetShortPathName(\
                        t'$RootDir', \
                        t.R0, \
                        i${NSIS_MAX_STRLEN}) i.R1"

        ${If} $R1 > 0
            Push $R0
        ${EndIf}
    ${Else}
        Push $0
    ${EndIf}
!macroend

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

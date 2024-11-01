var UninstCustomOptions
var UninstCustomOptions.RemoveCondaRcs_User
var UninstCustomOptions.RemoveCondaRcs_System
var UninstCustomOptions.RemoveCaches
var UninstCustomOptions.CondaClean

# These are the checkbox states, to be used by the uninstaller
var UninstRemoveCondaRcs_User_State
var UninstRemoveCondaRcs_System_State
var UninstRemoveCaches_State
var UninstCondaClean_State

Function un.UninstCustomOptions_InitDefaults
    StrCpy $UninstRemoveCondaRcs_User_State ${BST_UNCHECKED}
    StrCpy $UninstRemoveCondaRcs_System_State ${BST_UNCHECKED}
    StrCpy $UninstRemoveCaches_State ${BST_UNCHECKED}
    StrCpy $UninstCondaClean_State ${BST_UNCHECKED}
FunctionEnd

Function un.UninstCustomOptions_Show
    ${If} $UninstCondaClean_State == ""
        Abort
    ${EndIf}
    # Create dialog
    nsDialogs::Create 1018
    Pop $UninstCustomOptions
    ${If} $UninstCustomOptions == error
        Abort
    ${EndIf}

    !insertmacro MUI_HEADER_TEXT \
	"Advanced uninstallation options" \
       	"Remove configuration and cache files"

    # We will use $5 as the y axis accumulator, starting at 0
    # We sum the the number of 'u' units added by 'NSD_Create*' functions
    IntOp $5 0 + 0

    # Option to remove .condarc files
    ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove user configuration files."
    IntOp $5 $5 + 11
    Pop $UninstCustomOptions.RemoveCondaRcs_User
    ${NSD_SetState} $UninstCustomOptions.RemoveCondaRcs_User $UninstRemoveCondaRcs_User_State
    ${NSD_OnClick} $UninstCustomOptions.RemoveCondaRcs_User un.UninstRemoveCondarcs_User_Onclick
    ${NSD_CreateLabel} 5% "$5u" 90% 10u \
        "This removes .condarc files in the Users directory."
    IntOp $5 $5 + 10

    ${If} ${UAC_IsAdmin}
        ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove system-wide configuration files."
        IntOp $5 $5 + 11
        Pop $UninstCustomOptions.RemoveCondaRcs_System
        ${NSD_SetState} $UninstCustomOptions.RemoveCondaRcs_System $UninstRemoveCondaRcs_System_State
        ${NSD_OnClick} $UninstCustomOptions.RemoveCondaRcs_System un.UninstRemoveCondarcs_System_Onclick
        ${NSD_CreateLabel} 5% "$5u" 90% 10u \
            "This removes .condarc files in the ProgramData directory."
        IntOp $5 $5 + 10
    ${EndIf}

    # Option to remove cache files
    ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove cache files."
    IntOp $5 $5 + 11
    Pop $UninstCustomOptions.RemoveCaches
    ${NSD_SetState} $UninstCustomOptions.RemoveCaches $UninstRemoveCaches_State
    ${NSD_OnClick} $UninstCustomOptions.RemoveCaches un.UninstRemoveCaches_Onclick
    ${NSD_CreateLabel} 5% "$5u" 90% 10u \
        "This removes the .conda directory in the user folder and conda system cache files."
    IntOp $5 $5 + 10

    # Option to run conda --clean
    ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove index and package files."
    IntOp $5 $5 + 11
    Pop $UninstCustomOptions.CondaClean
    ${NSD_SetState} $UninstCustomOptions.CondaClean $UninstCondaClean_State
    ${NSD_OnClick} $UninstCustomOptions.CondaClean un.UninstCondaClean_Onclick
    ${NSD_CreateLabel} 5% "$5u" 90% 20u \
        "This removes index and unused package files by running conda clean --all. \
        Only useful if pkgs_dirs is set in a .condarc file."
    IntOp $5 $5 + 20

    IntOp $5 $5 + 5
    ${NSD_CreateLabel} 0 "$5u" 100% 10u \
        "These options are not recommended if multiple conda installations exist on the same system."
    IntOp $5 $5 + 10
    Pop $R0
    SetCtlColors $R0 ff0000 transparent

    nsDialogs::Show
FunctionEnd

Function un.UninstRemoveCondarcs_User_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstRemoveCondarcs_User_State
FunctionEnd

Function un.UninstRemoveCondarcs_System_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstRemoveCondarcs_System_State
FunctionEnd

Function un.UninstRemoveCaches_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstRemoveCaches_State
FunctionEnd

Function un.UninstCondaClean_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstCondaClean_State
FunctionEnd

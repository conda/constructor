var UninstCustomOptions
var UninstCustomOptions.RemoveConfigFiles_User
var UninstCustomOptions.RemoveConfigFiles_System
var UninstCustomOptions.RemoveUserData
var UninstCustomOptions.RemoveCaches

# These are the checkbox states, to be used by the uninstaller
var UninstRemoveConfigFiles_User_State
var UninstRemoveConfigFiles_System_State
var UninstRemoveUserData_State
var UninstRemoveCaches_State

Function un.UninstCustomOptions_InitDefaults
    StrCpy $UninstRemoveConfigFiles_User_State ${BST_UNCHECKED}
    StrCpy $UninstRemoveConfigFiles_System_State ${BST_UNCHECKED}
    StrCpy $UninstRemoveUserData_State ${BST_UNCHECKED}
    StrCpy $UninstRemoveCaches_State ${BST_UNCHECKED}
FunctionEnd

Function un.UninstCustomOptions_Show
    ${If} $UninstRemoveCaches_State == ""
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
            "Remove configuration, data, and cache files"

    # We will use $5 as the y axis accumulator, starting at 0
    # We sum the the number of 'u' units added by 'NSD_Create*' functions
    IntOp $5 0 + 0

    # Option to remove configuration files
    ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove user configuration files."
    IntOp $5 $5 + 11
    Pop $UninstCustomOptions.RemoveConfigFiles_User
    ${NSD_SetState} $UninstCustomOptions.RemoveConfigFiles_User $UninstRemoveConfigFiles_User_State
    ${NSD_OnClick} $UninstCustomOptions.RemoveConfigFiles_User un.UninstRemoveConfigFiles_User_Onclick
    ${NSD_CreateLabel} 5% "$5u" 90% 10u \
        "This removes configuration files such as .condarc files in the Users directory."
    IntOp $5 $5 + 10

    ${If} ${UAC_IsAdmin}
        ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove system-wide configuration files."
        IntOp $5 $5 + 11
        Pop $UninstCustomOptions.RemoveConfigFiles_System
        ${NSD_SetState} $UninstCustomOptions.RemoveConfigFiles_System $UninstRemoveConfigFiles_System_State
        ${NSD_OnClick} $UninstCustomOptions.RemoveConfigFiles_System un.UninstRemoveConfigFiles_System_Onclick
        ${NSD_CreateLabel} 5% "$5u" 90% 10u \
            "This removes configuration files such as .condarc files in the ProgramData directory."
        IntOp $5 $5 + 10
    ${EndIf}

    # Option to remove user data files
    ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove user data."
    IntOp $5 $5 + 11
    Pop $UninstCustomOptions.RemoveUserData
    ${NSD_SetState} $UninstCustomOptions.RemoveUserData $UninstRemoveUserData_State
    ${NSD_OnClick} $UninstCustomOptions.RemoveUserData un.UninstRemoveUserData_Onclick
    ${NSD_CreateLabel} 5% "$5u" 90% 10u \
        "This removes user data files such as the .conda directory inside the Users folder."
    IntOp $5 $5 + 10

    # Option to remove caches
    ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Remove caches."
    IntOp $5 $5 + 11
    Pop $UninstCustomOptions.RemoveCaches
    ${NSD_SetState} $UninstCustomOptions.RemoveCaches $UninstRemoveCaches_State
    ${NSD_OnClick} $UninstCustomOptions.RemoveCaches un.UninstRemoveCaches_Onclick
    ${NSD_CreateLabel} 5% "$5u" 90% 10u \
        "This removes cache directories such as package caches and notices."
    IntOp $5 $5 + 20

    IntOp $5 $5 + 5
    ${NSD_CreateLabel} 0 "$5u" 100% 10u \
        "These options are not recommended if multiple conda installations exist on the same system."
    IntOp $5 $5 + 10
    Pop $R0
    SetCtlColors $R0 ff0000 transparent

    nsDialogs::Show
FunctionEnd

Function un.UninstRemoveConfigFiles_User_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstRemoveConfigFiles_User_State
FunctionEnd

Function un.UninstRemoveConfigFiles_System_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstRemoveConfigFiles_System_State
FunctionEnd

Function un.UninstRemoveUserData_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstRemoveUserData_State
FunctionEnd

Function un.UninstRemoveCaches_OnClick
    Pop $0
    ${NSD_GetState} $0 $UninstRemoveCaches_State
FunctionEnd

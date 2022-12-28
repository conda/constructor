/*
    Custom Options Dialog
*/

;--------------------------------
;Page interface settings and variables

Var mui_AnaCustomOptions
Var mui_AnaCustomOptions.AddToPath
Var mui_AnaCustomOptions.RegisterSystemPython
Var mui_AnaCustomOptions.PostInstall
Var mui_AnaCustomOptions.PreInstall
Var mui_AnaCustomOptions.ClearPkgCache
Var mui_AnaCustomOptions.CreateShortcuts

# These are the checkbox states, to be used by the installer
Var Ana_AddToPath_State
Var Ana_RegisterSystemPython_State
Var Ana_PostInstall_State
Var Ana_PreInstall_State
Var Ana_ClearPkgCache_State
Var Ana_CreateShortcuts_State

Var Ana_AddToPath_Label
Var Ana_RegisterSystemPython_Label
Var Ana_ClearPkgCache_Label
Var Ana_PostInstall_Label
Var Ana_PreInstall_Label

Function mui_AnaCustomOptions_InitDefaults
    # Initialize defaults
    ${If} $Ana_AddToPath_State == ""
        StrCpy $Ana_AddToPath_State ${BST_UNCHECKED}
        # Default whether to register as system python as:
        #   Enabled - if no system python is registered, OR
        #             a system python which does not exist is registered.
        #   Disabled - If a system python which exists is registered.
        ReadRegStr $2 SHCTX "Software\Python\PythonCore\${PY_VER}\InstallPath" ""
        ${If} "$2" != ""
        ${AndIf} ${FileExists} "$2\Python.exe"
            StrCpy $Ana_RegisterSystemPython_State ${BST_UNCHECKED}
        ${Else}
            StrCpy $Ana_RegisterSystemPython_State ${BST_CHECKED}
        ${EndIf}
	${If} $Ana_CreateShortcuts_State == ""
        StrCpy $Ana_CreateShortcuts_State ${BST_CHECKED}
    ${EndIf}
    ${EndIf}
FunctionEnd

;--------------------------------
;Page functions

Function mui_AnaCustomOptions_Show
    ; Enforce that the defaults were initialized
    ${If} $Ana_AddToPath_State == ""
        Abort
    ${EndIf}

    ;Create dialog
    nsDialogs::Create 1018
    Pop $mui_AnaCustomOptions
    ${If} $mui_AnaCustomOptions == error
        Abort
    ${EndIf}

    !insertmacro MUI_HEADER_TEXT \
        "Advanced Installation Options" \
        "Customize how ${NAME} integrates with Windows"

    # We will use $5 as the y axis accumulator, starting at 0
    # We sum the the number of 'u' units added by 'NSD_Create*' functions

    ${NSD_CreateCheckbox} 0 0u 100% 11u "Create start menu shortcuts (supported packages only)."
    IntOp $5 0 + 11
    Pop $mui_AnaCustomOptions.CreateShortcuts
    ${NSD_SetState} $mui_AnaCustomOptions.CreateShortcuts $Ana_CreateShortcuts_State
    ${NSD_OnClick} $mui_AnaCustomOptions.CreateShortcuts CreateShortcuts_OnClick

    ${If} "${SHOW_ADD_TO_PATH}" == "yes"
        # AddToPath is only an option for JustMe installations; it is disabled for AllUsers
        # installations. (Addresses CVE-2022-26526)
        ${If} $InstMode = ${JUST_ME}
            ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Add ${NAME} to my &PATH environment variable"
            IntOp $5 $5 + 11
            Pop $mui_AnaCustomOptions.AddToPath
            ${NSD_SetState} $mui_AnaCustomOptions.AddToPath $Ana_AddToPath_State
            ${NSD_OnClick} $mui_AnaCustomOptions.AddToPath AddToPath_OnClick
            ${NSD_CreateLabel} 5% "$5u" 90% 20u \
                "NOT recommended. This can lead to conflicts with other applications. Instead, use \
                the Commmand Prompt and Powershell menus added to the Windows Start Menu."
            IntOp $5 $5 + 20
            Pop $Ana_AddToPath_Label
        ${EndIf}
    ${EndIf}

    ${If} "${SHOW_REGISTER_PYTHON}" == "yes"
        ${If} $InstMode = ${JUST_ME}
            StrCpy $1 "my default"
        ${Else}
            StrCpy $1 "the system"
        ${EndIf}
        ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "&Register ${NAME} as $1 Python ${PY_VER}"
        IntOp $5 $5 + 11
        Pop $mui_AnaCustomOptions.RegisterSystemPython
        ${NSD_SetState} $mui_AnaCustomOptions.RegisterSystemPython $Ana_RegisterSystemPython_State
        ${NSD_OnClick} $mui_AnaCustomOptions.RegisterSystemPython RegisterSystemPython_OnClick
        ${NSD_CreateLabel} 5% "$5u" 90% 20u \
            "Recommended. Allows other programs, such as VSCode, PyCharm, etc. to automatically \
            detect ${NAME} as the primary Python ${PY_VER} on the system."
        IntOp $5 $5 + 20
        Pop $Ana_RegisterSystemPython_Label
    ${EndIf}


    ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Clear the package cache upon completion"
    IntOp $5 $5 + 12
    Pop $mui_AnaCustomOptions.ClearPkgCache
    ${NSD_SetState} $mui_AnaCustomOptions.ClearPkgCache $Ana_ClearPkgCache_State
    ${NSD_OnClick} $mui_AnaCustomOptions.ClearPkgCache ClearPkgCache_OnClick
    ${NSD_CreateLabel} 5% "$5u" 90% 11u \
        "Recommended. Recovers some disk space without harming functionality."
    IntOp $5 $5 + 11
    Pop $Ana_ClearPkgCache_Label

    ${If} "${PRE_INSTALL_DESC}" != ""
        ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Run the pre-install script"
        IntOp $5 $5 + 11
        Pop $mui_AnaCustomOptions.PreInstall
        ${NSD_SetState} $mui_AnaCustomOptions.PreInstall $Ana_PreInstall_State
        ${NSD_OnClick} $mui_AnaCustomOptions.PreInstall PreInstall_OnClick
        ${NSD_CreateLabel} 5% "$5u" 90% 20u "${PRE_INSTALL_DESC}"
        IntOp $5 $5 + 20
        Pop $Ana_PreInstall_Label
    ${EndIf}

    ${If} "${POST_INSTALL_DESC}" != ""
        ${NSD_CreateCheckbox} 0 "$5u" 100% 11u "Run the post-install script"
        IntOp $5 $5 + 11
        Pop $mui_AnaCustomOptions.PostInstall
        ${NSD_SetState} $mui_AnaCustomOptions.PostInstall $Ana_PostInstall_State
        ${NSD_OnClick} $mui_AnaCustomOptions.PostInstall PostInstall_OnClick
        ${NSD_CreateLabel} 5% "$5u" 90% 20u "${POST_INSTALL_DESC}"
        IntOp $5 $5 + 20
        Pop $Ana_PostInstall_Label
    ${EndIf}

    nsDialogs::Show
FunctionEnd

Function AddToPath_OnClick
    Pop $0

    ShowWindow $Ana_AddToPath_Label ${SW_HIDE}
    ${NSD_GetState} $0 $Ana_AddToPath_State
    ${If} $Ana_AddToPath_State == ${BST_UNCHECKED}
        SetCtlColors $Ana_AddToPath_Label 000000 transparent
    ${Else}
        SetCtlColors $Ana_AddToPath_Label ff0000 transparent
    ${EndIf}
    ShowWindow $Ana_AddToPath_Label ${SW_SHOW}
FunctionEnd

Function RegisterSystemPython_OnClick
    Pop $0

    ShowWindow $Ana_RegisterSystemPython_Label ${SW_HIDE}
    ${NSD_GetState} $0 $Ana_RegisterSystemPython_State
    ${If} $Ana_RegisterSystemPython_State == ${BST_UNCHECKED}
        SetCtlColors $Ana_RegisterSystemPython_Label ff0000 transparent
    ${Else}
        SetCtlColors $Ana_RegisterSystemPython_Label 000000 transparent
    ${EndIf}
    ShowWindow $Ana_RegisterSystemPython_Label ${SW_SHOW}

    # If the button was checked, make sure we're not conflicting
    # with another system installed Python
    ${If} $Ana_RegisterSystemPython_State == ${BST_CHECKED}
        # Check if a Python of the version we're installing
        # already exists, in which case warn the user before
        # proceeding.
        ReadRegStr $2 SHCTX "Software\Python\PythonCore\${PY_VER}\InstallPath" ""
        ${If} "$2" != ""
        ${AndIf} ${FileExists} "$2\Python.exe"
            MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION|MB_DEFBUTTON2 \
                "A version of Python ${PY_VER} (${ARCH}) is already at$\n\
                $2$\n\
                We recommend that if you want ${NAME} registered as your $\n\
                system Python, you unregister this Python first. If you really$\n\
                know this is what you want, click OK, otherwise$\n\
                click cancel to continue.$\n$\n\
                NOTE: Anaconda 1.3 and earlier lacked an uninstall, if$\n\
                you are upgrading an old Anaconda, please delete the$\n\
                directory manually." \
                IDOK KeepSettingLabel
        # If they don't click OK, uncheck it
        StrCpy $Ana_RegisterSystemPython_State ${BST_UNCHECKED}
        ${NSD_SetState} $0 $Ana_RegisterSystemPython_State
KeepSettingLabel:

        ${EndIf}
    ${EndIf}
FunctionEnd

Function PostInstall_OnClick
    Pop $0

    ShowWindow $Ana_PostInstall_Label ${SW_HIDE}
    ${NSD_GetState} $0 $Ana_PostInstall_State
    ${If} $Ana_PostInstall_State == ${BST_CHECKED}
        SetCtlColors $Ana_PostInstall_Label 000000 transparent
    ${Else}
        SetCtlColors $Ana_PostInstall_Label ff0000 transparent
    ${EndIf}
    ShowWindow $Ana_PostInstall_Label ${SW_SHOW}
FunctionEnd

Function PreInstall_OnClick
    Pop $0

    ShowWindow $Ana_PreInstall_Label ${SW_HIDE}
    ${NSD_GetState} $0 $Ana_PreInstall_State
    ${If} $Ana_PreInstall_State == ${BST_CHECKED}
        SetCtlColors $Ana_PreInstall_Label 000000 transparent
    ${Else}
        SetCtlColors $Ana_PreInstall_Label ff0000 transparent
    ${EndIf}
    ShowWindow $Ana_PreInstall_Label ${SW_SHOW}
FunctionEnd

Function ClearPkgCache_OnClick
    Pop $0

    ShowWindow $Ana_ClearPkgCache_Label ${SW_HIDE}
    ${NSD_GetState} $0 $Ana_ClearPkgCache_State
    ${If} $Ana_ClearPkgCache_State == ${BST_CHECKED}
        SetCtlColors $Ana_ClearPkgCache_Label 000000 transparent
    ${Else}
        SetCtlColors $Ana_ClearPkgCache_Label ff0000 transparent
    ${EndIf}
    ShowWindow $Ana_ClearPkgCache_Label ${SW_SHOW}
FunctionEnd

Function CreateShortcuts_OnClick
    Pop $0
    ${NSD_GetState} $0 $Ana_CreateShortcuts_State

FunctionEnd

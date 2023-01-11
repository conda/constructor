

Page Custom muiExtraPages_Create

var IntroText
var InstallationLink
var ExampleImg
var ExampleImgCtl

Function muiExtraPages_Create
    Push $0

    !insertmacro MUI_HEADER_TEXT_PAGE \
        "${PRODUCT_NAME}" \
        "Extra Pages Example"

    nsDialogs::Create /NOUNLOAD 1018
    ${NSD_CreateLabel} 10u 10u 280u 40u "Extra Page 1.$\r$\n$\r$\n$\r$\nHere is a link to the conda Github organization:"
    Pop $IntroText

    ${NSD_CreateLink} 10u 55u 200u 10u "https://github.com/conda"
    Pop $InstallationLink
    ${NSD_OnClick} $InstallationLink LaunchLinkOne

    nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS}|${SS_BITMAP}|${SS_REALSIZECONTROL} 0 10u 90u 280u 40u ""
    Pop $ExampleImgCtl
    StrCpy $0 $PLUGINSDIR\ExtraPagesExampleImg.bmp
    System::Call 'user32::LoadImage(i 0, t r0, i ${IMAGE_BITMAP}, i 0, i 0, i ${LR_LOADFROMFILE}|${LR_LOADTRANSPARENT}|${LR_LOADMAP3DCOLORS}) i.s'
    Pop $ExampleImg
    SendMessage $ExampleImgCtl ${STM_SETIMAGE} ${IMAGE_BITMAP} $ExampleImg

    nsDialogs::Show

    System::Call 'gdi32:DeleteObject(i $ExampleImg)'

    Pop $0
FunctionEnd

!define MUI_FINISHPAGE_TEXT "Extra Page 2. $\r$\n$\r$\n\
Here are some checkboxes that, when selected, will open links to those resources.$\r$\n$\r$\n\"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "LinkTwo (constructor Github repository)"
!define MUI_FINISHPAGE_RUN_FUNCTION "LaunchLinkTwo"
!define MUI_PAGE_CUSTOMFUNCTION_SHOW MyFinishShow
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE MyFinishLeave

var CheckboxLinkThree

Function LaunchLinkOne
    ExecShell "open" "https://github.com/conda"
FunctionEnd

Function LaunchLinkTwo
    ExecShell "open" "https://github.com/conda/constructor"
FunctionEnd

Function MyFinishShow
    ${NSD_CreateCheckbox} 120u 110u 100% 10u "LinkThree (NSIS documentation)"
    Pop $CheckboxLinkThree
    ${NSD_Check} $CheckboxLinkThree
    SetCtlColors $CheckboxLinkThree "" "ffffff"
FunctionEnd

Function MyFinishLeave
${NSD_GetState} $CheckboxLinkThree $0
${If} $0 <> 0
    ExecShell "open" "https://nsis.sourceforge.io/Reference/File"
${EndIf}
FunctionEnd

!insertmacro MUI_PAGE_FINISH

# Below is an example of creating multiple pages after the welcome page of the installer.
#
# This file contains code that is inserted where the @CUSTOM_WELCOME_FILE@ is located
# in the main.nsi.tmpl. The main mechanism for extra pages occurs with the
# "Page Custom muiExtraPagesAfterWelcome_Create" line, which
# references the function "muiExtraPagesAfterWelcome_Create" for page creation.

!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipPageIfUACInnerInstance
!insertmacro MUI_PAGE_WELCOME

Page Custom muiExtraPagesAfterWelcome_Create

var IntroAfterWelcomeText
var InstallationAfterWelcomeLink
var ExampleAfterWelcomeImg
var ExampleImgAfterWelcomeCtl

Function muiExtraPagesAfterWelcome_Create
    Push $0

    !insertmacro MUI_HEADER_TEXT_PAGE \
        "${PRODUCT_NAME}" \
        "Extra Pages Example"

    nsDialogs::Create /NOUNLOAD 1018
    ${NSD_CreateLabel} 10u 10u 280u 40u "Extra Welcome Page 1.$\r$\n$\r$\n$\r$\nHere is a link to the conda Github organization:"
    Pop $IntroAfterWelcomeText

    ${NSD_CreateLink} 10u 55u 200u 10u "https://github.com/conda"
    Pop $InstallationAfterWelcomeLink
    ${NSD_OnClick} $InstallationAfterWelcomeLink LaunchLinkOne

    nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS}|${SS_BITMAP}|${SS_REALSIZECONTROL} 0 10u 90u 280u 40u ""
    Pop $ExampleImgAfterWelcomeCtl
    StrCpy $0 $PLUGINSDIR\ExtraPagesExampleImg.bmp
    System::Call 'user32::LoadImage(i 0, t r0, i ${IMAGE_BITMAP}, i 0, i 0, i ${LR_LOADFROMFILE}|${LR_LOADTRANSPARENT}|${LR_LOADMAP3DCOLORS}) i.s'
    Pop $ExampleAfterWelcomeImg
    SendMessage $ExampleImgAfterWelcomeCtl ${STM_SETIMAGE} ${IMAGE_BITMAP} $ExampleAfterWelcomeImg

    nsDialogs::Show

    System::Call 'gdi32:DeleteObject(i $ExampleAfterWelcomeImg)'

    Pop $0
FunctionEnd

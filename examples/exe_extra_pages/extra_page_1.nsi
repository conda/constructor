Function extraPage1
!insertmacro MUI_HEADER_TEXT "Extra Page 1" "This is extra page number 1"

nsDialogs::Create 1018
${NSD_CreateLabel} 0 0 100% 12u "Content of extra page 1"

${NSD_CreateText} 0 13u 100% "Lorem ipsum dolor sit amet"

nsDialogs::Show
FunctionEnd

Page custom extraPage1

Function extraPage2
!insertmacro MUI_HEADER_TEXT "Extra Page 2" "This is extra page number 2"

nsDialogs::Create 1018
${NSD_CreateLabel} 0 0 100% 12u "Content of extra page 2"

${NSD_CreateText} 0 13u 100% "consectetur adipiscing elit."

nsDialogs::Show
FunctionEnd

Page custom extraPage2

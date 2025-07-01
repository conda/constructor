SetLocal EnableDelayedExpansion

call "%PREFIX%\Scripts\activate.bat"

set "condarc_file=%PREFIX%\.condarc"

if not exist "%condarc_file%" (
    echo Error: .condarc file does not exist
    exit /b 1
)

set expected_content=^
channels:^
  - conda-forge^
mirrored_channels:^
  conda-forge:^
    - "https://conda.anaconda.org/conda-forge"^
    - "https://repo.prefix.dev/conda-forge"

set "actual_content="
for /f "usebackq delims=" %%A in ("%condarc_file%") do (
    set "line=%%A"
    set "line=!line: =!"
    set "actual_content=!actual_content!!line!"
)

set "actual_content=!actual_content: =!"
set "actual_content=!actual_content:^=!"
set "expected_content=%expected_content: =%"
set "expected_content=%expected_content:^=%"

if /i "!actual_content!"=="%expected_content%" (
    echo .condarc file matches expected content.
) else (
    echo Error: .condarc file does not match expected content
    exit /b 1
)

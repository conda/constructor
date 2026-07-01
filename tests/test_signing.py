import sys

import pytest

from constructor.signing import AzureSignTool


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_azure_verify_signature_quotes_path_with_spaces(mocker):
    """Test that installer paths containing spaces are quoted in the PowerShell command."""
    tool = AzureSignTool()
    installer = r"C:\Users\runner\Some Product\foo.msi"

    mocker.patch("constructor.signing.shutil.which", return_value="powershell")
    mock_run = mocker.patch("constructor.signing.run")
    mock_run.return_value.stderr = ""
    mock_run.return_value.stdout = "0\nSignature verified.\n"

    tool.verify_signature(installer)

    # argv passed to run() is ["powershell", "-c", command]
    command = mock_run.call_args.args[0][2]
    assert f"-LiteralPath '{installer}'" in command

import logging
import os
import shutil
from pathlib import Path
from subprocess import PIPE, STDOUT, check_call, run
from typing import Union

from .utils import win_str_esc

logger = logging.getLogger(__name__)


class SigningTool:
    def __init__(
        self,
        executable: Union[str, Path],
        certificate_file: Union[str, Path] = None,
    ):
        self.executable = str(executable)
        if certificate_file and not Path(certificate_file).exists():
            raise FileNotFoundError(f"Certificate file {certificate_file} does not exist.")
        self.certificate_file = certificate_file

    def _verify_tool_is_available(self):
        logger.info(f"Checking for {self.executable}...")
        if not shutil.which(self.executable):
            raise FileNotFoundError(
                f"Could not find {self.executable}. Verify that the file exists or is in PATH."
            )

    def verify_signing_tool(self):
        self._verify_tool_is_available()

    def get_signing_command(self):
        return self.executable

    def verify_signature(self):
        raise NotImplementedError("Signature verification not implemented for base class.")


class WindowsSignTool(SigningTool):
    def __init__(self, certificate_file=None):
        super().__init__(
            os.environ.get("CONSTRUCTOR_SIGNTOOL_PATH", "signtool"),
            certificate_file=certificate_file,
        )

    def get_signing_command(self) -> str:
        timestamp_server = os.environ.get(
            "CONSTRUCTOR_SIGNTOOL_TIMESTAMP_SERVER_URL",
            "http://timestamp.sectigo.com"
        )
        timestamp_digest = os.environ.get(
            "CONSTRUCTOR_SIGNTOOL_TIMESTAMP_DIGEST",
            "sha256"
        )
        file_digest = os.environ.get(
            "CONSTRUCTOR_SIGNTOOL_FILE_DIGEST",
            "sha256"
        )
        command = (
            f"{win_str_esc(self.executable)} sign /f {win_str_esc(self.certificate_file)} "
            f"/tr {win_str_esc(timestamp_server)} /td {timestamp_digest} /fd {file_digest}"
        )
        if "CONSTRUCTOR_PFX_CERTIFICATE_PASSWORD" in os.environ:
            # signtool can get the password from the env var on its own
            command += ' /p "%CONSTRUCTOR_PFX_CERTIFICATE_PASSWORD%"'
        return command

    def verify_signing_tool(self):
        self._verify_tool_is_available()
        if not Path(self.certificate_file).exists():
            raise FileNotFoundError(f"Could not find certificate file {self.certificate_file}.")
        check_call([self.executable, "/?"], stdout=PIPE, stderr=PIPE)

    def verify_signature(self, installer_file: Union[str, Path]):
        proc = run(
            [self.executable, "verify", "/v", str(installer_file)],
            stdout=PIPE,
            stderr=STDOUT,
            text=True,
        )
        logger.info(proc.stdout)
        if "SignTool Error: No signature found" in proc.stdout:
            # This is a signing error!
            proc.check_returncode()
        elif proc.returncode:
            # we had errors but maybe not critical ones
            logger.error(
                f"SignTool could find a signature in {installer_file} but detected errors. "
                "This is expected for untrusted (development) certificates. "
                "If it is supposed to be trusted, please check your certificate!"
            )

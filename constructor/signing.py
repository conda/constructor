"""
Common utilities to sign installers.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from plistlib import dump as plist_dump
from subprocess import PIPE, STDOUT, check_call, run
from tempfile import NamedTemporaryFile

from .utils import check_required_env_vars, explained_check_call, win_str_esc

logger = logging.getLogger(__name__)


class SigningTool:
    """Base class to sign installers.

    Attributes
    ----------
    executable: str | Path
        Path to the signing tool binary.
    certificate_file: str | Path
        Path to the certificate file
    """

    def __init__(
        self,
        executable: str | Path,
        certificate_file: str | Path | None = None,
    ):
        self.executable = str(executable)
        if certificate_file and not Path(certificate_file).exists():
            raise FileNotFoundError(f"Certificate file {certificate_file} does not exist.")
        self.certificate_file = certificate_file

    def _verify_tool_is_available(self):
        """Helper function to verify that the signing tool executable exists.

        This is a minimum verification step and should be done even if other steps are performed
        to verify the signing tool (e.g., signtool.exe /?) to receive better error messages.
        For example, using `signtool.exe /?` when the path does not exist, results in a misleading
        Permission Denied error.
        """
        logger.info(f"Checking for {self.executable}...")
        if not shutil.which(self.executable):
            raise FileNotFoundError(
                f"Could not find {self.executable}. Verify that the file exists or is in PATH."
            )

    def verify_signing_tool(self):
        """Verify that the signing tool is usable."""
        self._verify_tool_is_available()

    def get_signing_command(self):
        """Get the string of the signing command to be executed.

        For Windows, this command is inserted into the NSIS template.
        """
        return self.executable

    def verify_signature(self):
        """Verify the signed installer."""
        raise NotImplementedError("Signature verification not implemented for base class.")

    def sign(self, file_path: str | Path):
        """Sign the specified file."""
        raise NotImplementedError("Signing not implemented for base class.")


class WindowsSignTool(SigningTool):
    def __init__(self, certificate_file=None):
        super().__init__(
            os.environ.get("CONSTRUCTOR_SIGNTOOL_PATH", "signtool"),
            certificate_file=certificate_file,
        )

    def _get_signing_params(self):
        """Get signing parameters from environment."""
        return {
            "timestamp_server": os.environ.get(
                "CONSTRUCTOR_SIGNTOOL_TIMESTAMP_SERVER_URL", "http://timestamp.sectigo.com"
            ),
            "timestamp_digest": os.environ.get("CONSTRUCTOR_SIGNTOOL_TIMESTAMP_DIGEST", "sha256"),
            "file_digest": os.environ.get("CONSTRUCTOR_SIGNTOOL_FILE_DIGEST", "sha256"),
            "password": os.environ.get("CONSTRUCTOR_PFX_CERTIFICATE_PASSWORD"),
        }

    def get_signing_command(self) -> str:
        params = self._get_signing_params()
        command = (
            f"{win_str_esc(self.executable)} sign /f {win_str_esc(self.certificate_file)} "
            f"/tr {win_str_esc(params['timestamp_server'])} /td {params['timestamp_digest']} "
            f"/fd {params['file_digest']}"
        )
        if params["password"]:
            # signtool can get the password from the env var on its own
            command += ' /p "%CONSTRUCTOR_PFX_CERTIFICATE_PASSWORD%"'
        return command

    def sign(self, file_path: str | Path):
        """Sign a file using signtool."""
        params = self._get_signing_params()
        command = [
            self.executable,
            "sign",
            "/f",
            str(self.certificate_file),
            "/tr",
            params["timestamp_server"],
            "/td",
            params["timestamp_digest"],
            "/fd",
            params["file_digest"],
        ]
        if params["password"]:
            command.extend(["/p", params["password"]])
        command.append(str(file_path))
        check_call(command)

    def verify_signing_tool(self):
        super()._verify_tool_is_available()
        if not Path(self.certificate_file).exists():
            raise FileNotFoundError(f"Could not find certificate file {self.certificate_file}.")
        check_call([self.executable, "/?"], stdout=PIPE, stderr=PIPE)

    def verify_signature(self, installer_file: str | Path):
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


class AzureSignTool(SigningTool):
    def __init__(self):
        super().__init__(os.environ.get("AZURE_SIGNTOOL_PATH", "AzureSignTool"))

    def _get_signing_params(self):
        """Get signing parameters from environment."""
        required_env_vars = (
            "AZURE_SIGNTOOL_KEY_VAULT_URL",
            "AZURE_SIGNTOOL_KEY_VAULT_CERTIFICATE",
        )
        check_required_env_vars(required_env_vars)

        return {
            "key_vault_url": os.environ["AZURE_SIGNTOOL_KEY_VAULT_URL"],
            "key_vault_certificate": os.environ["AZURE_SIGNTOOL_KEY_VAULT_CERTIFICATE"],
            "timestamp_server": os.environ.get(
                "AZURE_SIGNTOOL_TIMESTAMP_SERVER_URL", "http://timestamp.sectigo.com"
            ),
            "timestamp_digest": os.environ.get("AZURE_SIGNTOOL_TIMESTAMP_DIGEST", "sha256"),
            "file_digest": os.environ.get("AZURE_SIGNTOOL_FILE_DIGEST", "sha256"),
            "access_token": os.environ.get("AZURE_SIGNTOOL_KEY_VAULT_ACCESSTOKEN"),
            "secret": os.environ.get("AZURE_SIGNTOOL_KEY_VAULT_SECRET"),
            "client_id": os.environ.get("AZURE_SIGNTOOL_KEY_VAULT_CLIENT_ID"),
            "tenant_id": os.environ.get("AZURE_SIGNTOOL_KEY_VAULT_TENANT_ID"),
        }

    def sign(self, file_path: str | Path):
        """Sign a file using AzureSignTool."""
        params = self._get_signing_params()
        command = [
            self.executable,
            "sign",
            "-v",
            "-kvu",
            params["key_vault_url"],
            "-kvc",
            params["key_vault_certificate"],
            "-tr",
            params["timestamp_server"],
            "-td",
            params["timestamp_digest"],
            "-fd",
            params["file_digest"],
        ]

        if params["access_token"]:
            logger.info("AzureSignTool: signing binary using access token.")
            command.extend(["-kva", params["access_token"]])
        elif params["secret"]:
            logger.info("AzureSignTool: signing binary using secret.")
            check_required_env_vars(
                (
                    "AZURE_SIGNTOOL_KEY_VAULT_CLIENT_ID",
                    "AZURE_SIGNTOOL_KEY_VAULT_TENANT_ID",
                )
            )
            command.extend(
                [
                    "-kvi",
                    params["client_id"],
                    "-kvt",
                    params["tenant_id"],
                    "-kvs",
                    params["secret"],
                ]
            )
        else:
            logger.info("AzureSignTool: signing binary using managed identity.")
            command.append("-kvm")

        command.append(str(file_path))
        check_call(command)

    def get_signing_command(self) -> str:
        required_env_vars = (
            "AZURE_SIGNTOOL_KEY_VAULT_URL",
            "AZURE_SIGNTOOL_KEY_VAULT_CERTIFICATE",
        )
        check_required_env_vars(required_env_vars)
        timestamp_server = os.environ.get(
            "AZURE_SIGNTOOL_TIMESTAMP_SERVER_URL", "http://timestamp.sectigo.com"
        )
        timestamp_digest = os.environ.get("AZURE_SIGNTOOL_TIMESTAMP_DIGEST", "sha256")
        file_digest = os.environ.get("AZURE_SIGNTOOL_FILE_DIGEST", "sha256")

        command = (
            f"{win_str_esc(self.executable)} sign -v"
            ' -kvu "%AZURE_SIGNTOOL_KEY_VAULT_URL%"'
            ' -kvc "%AZURE_SIGNTOOL_KEY_VAULT_CERTIFICATE%"'
            f' -tr "{timestamp_server}"'
            f" -td {timestamp_digest}"
            f" -fd {file_digest}"
        )
        # There are three ways to sign:
        #   1. Access token
        #   2. Secret (requires tenant ID)
        #   3. Managed identity (requires prior login to Azure)
        if "AZURE_SIGNTOOL_KEY_VAULT_ACCESSTOKEN" in os.environ:
            logger.info("AzureSignTool: signing binary using access token.")
            command += ' -kva "%AZURE_SIGNTOOL_KEY_VAULT_ACCESSTOKEN%"'
        elif "AZURE_SIGNTOOL_KEY_VAULT_SECRET" in os.environ:
            # Authentication via secret required client and tenant ID
            logger.info("AzureSignTool: signing binary using secret.")
            required_env_vars = (
                "AZURE_SIGNTOOL_KEY_VAULT_CLIENT_ID",
                "AZURE_SIGNTOOL_KEY_VAULT_TENANT_ID",
            )
            check_required_env_vars(required_env_vars)
            command += (
                ' -kvi "%AZURE_SIGNTOOL_KEY_VAULT_CLIENT_ID%"'
                ' -kvt "%AZURE_SIGNTOOL_KEY_VAULT_TENANT_ID%"'
                ' -kvs "%AZURE_SIGNTOOL_KEY_VAULT_SECRET%"'
            )
        else:
            # No token or secret found, assume managed identity
            logger.info("AzureSignTool: signing binary using managed identity.")
            command += " -kvm"
        return command

    def verify_signing_tool(self):
        self._verify_tool_is_available()
        check_call([self.executable, "--help"], stdout=PIPE, stderr=PIPE)

    def verify_signature(self, installer_file: str | Path):
        """Use Powershell to verify signature.

        For available statuses, see the Microsoft documentation:
        https://learn.microsoft.com/en-us/dotnet/api/system.management.automation.signaturestatus
        """
        if shutil.which("powershell") is None:
            logger.error("Could not verify signature: PowerShell not found.")
            return
        command = (
            f"$sig = Get-AuthenticodeSignature -LiteralPath {installer_file};"
            "$sig.Status.value__;"
            "$sig.StatusMessage"
        )
        proc = run(
            [
                "powershell",
                "-c",
                command,
            ],
            capture_output=True,
            text=True,
        )
        # The return code will always be 0,
        # but stderr will be non-empty on errors
        if proc.stderr:
            raise RuntimeError(f"Signature verification failed.\n{proc.stderr}")
        try:
            status, status_message = proc.stdout.strip().split("\n")
            status = int(status)
            if status > 1:
                # Includes missing signature
                raise RuntimeError(f"Error signing {installer_file}: {status_message}")
            elif status == 1:
                logger.error(
                    f"{installer_file} contains a signature that is either invalid or not trusted. "
                    "This is expected with development certificates. "
                    "If it is supposed to be trusted, please check your certificate!"
                )
        except ValueError:
            # Something else is in the output
            raise RuntimeError(f"Unexpected signature verification output: {proc.stdout}")


class CodeSign(SigningTool):
    def __init__(
        self,
        identity_name: str,
        prefix: str = None,
    ):
        # hardcode to system location to avoid accidental clobber in PATH
        super().__init__("/usr/bin/codesign")
        self.identity_name = identity_name
        self.prefix = prefix

    def get_signing_command(
        self,
        bundle: str | Path,
        entitlements: str | Path | None = None,
    ) -> list:
        command = [
            self.executable,
            "--sign",
            self.identity_name,
            "--force",
            "--options",
            "runtime",
        ]
        if self.prefix:
            command.extend(["--prefix", self.prefix])
        if entitlements:
            command.extend(["--entitlements", str(entitlements)])
        if logger.getEffectiveLevel() == logging.DEBUG:
            command.append("--verbose")
        command.append(str(bundle))
        return command

    def sign_bundle(
        self,
        bundle: str | Path,
        entitlements: str | Path | dict | None = None,
    ):
        if isinstance(entitlements, dict):
            with NamedTemporaryFile(suffix=".plist", delete=False) as ent_file:
                plist_dump(entitlements, ent_file)
            command = self.get_signing_command(bundle, entitlements=ent_file.name)
            explained_check_call(command)
            os.unlink(ent_file.name)
        else:
            command = self.get_signing_command(bundle, entitlements=entitlements)
            explained_check_call(command)


def create_windows_signing_tool(info: dict) -> SigningTool | None:
    """Create a Windows signing tool based on construct.yaml.

    Returns None if no signing is configured.
    """
    signing_tool_name = info.get("windows_signing_tool")
    if not signing_tool_name:
        return None

    if signing_tool_name == "signtool":
        signing_tool = WindowsSignTool(certificate_file=info.get("signing_certificate"))
    elif signing_tool_name == "azuresigntool":
        signing_tool = AzureSignTool()
    else:
        raise ValueError(f"Unknown signing tool: {signing_tool_name}")

    signing_tool.verify_signing_tool()
    return signing_tool

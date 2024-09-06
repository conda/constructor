import os
import subprocess
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).parent.parent
ON_CI = os.environ.get("CI")


@pytest.fixture
def self_signed_certificate_macos(tmp_path):
    default_keychain = subprocess.run(
         ["security", "default-keychain"],
         capture_output=True,
         text=True,
         check=True,
    )
    cert_root = tmp_path / "certs"
    cert_root.mkdir(parents=True, exist_ok=True)
    signing_identity = "testinstaller"
    signing_identity_password = "1234"
    notarization_identity = "testapplication"
    notarization_identity_password = "5678"
    keychain_password = "abcd"
    env = {
        "APPLICATION_SIGNING_ID": notarization_identity,
        "APPLICATION_SIGNING_PASSWORD": notarization_identity_password,
        "INSTALLER_SIGNING_ID": signing_identity,
        "INSTALLER_SIGNING_PASSWORD": signing_identity_password,
        "KEYCHAIN_PASSWORD": keychain_password,
        "ROOT_DIR": str(cert_root),
    }
    # Installer certificates must be trusted to be found in the keychain.
    # Users will be asked for authentication.
    # On GitHub runners, the system keychain does not require authentication,
    # which is why it is unsed on the CI.
    if ON_CI:
        keychain_path = "/Library/Keychains/System.keychain"
    else:
        keychain_path = str(cert_root / "constructor.keychain")
    env["KEYCHAIN_PATH"] = keychain_path
    p = subprocess.run(
        ["bash", REPO_DIR / "scripts" / "create_self_signed_certificates_macos.sh"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    cert_data = {
        "signing_identity": {
            "name": signing_identity,
            "sha256": "",
        },
        "notarization_identity": {
            "name": notarization_identity,
            "sha256": "",
        },
    }
    for line in p.stdout.split("\n"):
        if not line.startswith("SHA256"):
            continue
        identifier, sha256 = line.rsplit("=", 1)
        if signing_identity in identifier:
            cert_data["signing_identity"]["sha256"] = sha256.strip()
        elif notarization_identity in identifier:
            cert_data["notarization_identity"]["sha256"] = sha256.strip()
    subprocess.run
    yield cert_data
    # Clean up
    subprocess.run(
         ["security", "default-keychain", "-s", default_keychain],
         capture_output=True,
         text=True,
         check=True,
    )

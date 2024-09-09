import os
import subprocess
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).parent.parent


@pytest.fixture
def self_signed_application_certificate_macos(tmp_path):
    p = subprocess.run(
         ["security", "list-keychains", "-d", "user"],
         capture_output=True,
         text=True,
    )
    current_keychains = [keychain.strip(' "') for keychain in p.stdout.split("\n") if keychain]
    cert_root = tmp_path / "certs"
    cert_root.mkdir(parents=True, exist_ok=True)
    notarization_identity = "testapplication"
    notarization_identity_password = "5678"
    keychain_password = "abcd"
    env = os.environ.copy()
    env.update({
        "APPLICATION_SIGNING_ID": notarization_identity,
        "APPLICATION_SIGNING_PASSWORD": notarization_identity_password,
        "KEYCHAIN_PASSWORD": keychain_password,
        "ROOT_DIR": str(cert_root),
    })
    p = subprocess.run(
        ["bash", REPO_DIR / "scripts" / "create_self_signed_certificates_macos.sh"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    yield notarization_identity
    # Clean up
    subprocess.run(["security", "list-keychains", "-d", "user", "-s", *current_keychains])

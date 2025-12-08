#!/bin/bash

set -e

if [[ -z "${ROOT_DIR}" ]]; then
    ROOT_DIR=$(mktemp -d)
else
    mkdir -p "${ROOT_DIR}"
fi

# Array assignment may leave the first element empty, so run cut twice
openssl_lib=$(openssl version | cut -d' ' -f1)
openssl_version=$(openssl version | cut -d' ' -f2)
if [[ "${openssl_lib}" == "OpenSSL" ]] && [[ "${openssl_version}" == 3.* ]]; then
    legacy=-legacy
fi

APPLICATION_SIGNING_ID=${APPLICATION_SIGNING_ID:-${APPLICATION_ROOT}}

KEYCHAIN_PATH="${KEYCHAIN_PATH:-"${ROOT_DIR}/constructor.keychain"}"
security create-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"
security set-keychain-settings -lut 3600 "${KEYCHAIN_PATH}"
security unlock-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"

# Originally, this code contained code for creating certificates for installer signing:
# https://github.com/conda/constructor/blob/555eccb19ab4c3ed8cf5384bf66348b6d9613fd1/scripts/create_self_signed_certificates_macos.sh
# However, installer certificates must be trusted. Adding a trusted certificate to any
# keychain requires authentication, which is interactive and causes the run to hang.
APPLICATION_ROOT="application"
keyusage="codeSigning"
certtype="1.2.840.113635.100.6.1.13"
commonname="${APPLICATION_SIGNING_ID}"
password="${APPLICATION_SIGNING_PASSWORD}"
keyfile="${ROOT_DIR}/application.key"
p12file="${ROOT_DIR}/application.p12"
crtfile="${ROOT_DIR}/application.crt"

openssl genrsa -out "${keyfile}" 2048
openssl req -x509 -new -key "${keyfile}"\
    -out "${crtfile}"\
    -sha256\
    -days 1\
    -subj "/C=XX/ST=State/L=City/O=Company/OU=Org/CN=${commonname}/emailAddress=somebody@somewhere.com"\
    -addext "basicConstraints=critical,CA:FALSE"\
    -addext "extendedKeyUsage=critical,${keyusage}"\
    -addext "keyUsage=critical,digitalSignature"\
    -addext "${certtype}=critical,DER:0500"

# shellcheck disable=SC2086
openssl pkcs12 -export\
    -out "${p12file}"\
    -inkey "${keyfile}"\
    -in "${crtfile}"\
    -passout pass:"${password}"\
    ${legacy}

security import "${p12file}" -P "${password}"  -t cert -f pkcs12 -k "${KEYCHAIN_PATH}" -A
# shellcheck disable=SC2046
security list-keychains -d user -s "${KEYCHAIN_PATH}" $(security list-keychains -d user | xargs)

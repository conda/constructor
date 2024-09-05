#!/bin/bash

set +e

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

APPLICATION_ROOT="application"
APPLICATION_SIGNING_ID=${APPLICATION_SIGNING_ID:-${APPLICATION_ROOT}}
INSTALLER_ROOT="installer"
INSTALLER_SIGNING_ID=${INSTALLER_SIGNING_ID:-${INSTALLER_ROOT}}
KEYCHAIN_PATH="${ROOT_DIR}/constructor.keychain-db"

security create-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"
security set-keychain-settings -lut 3600 "${KEYCHAIN_PATH}"
security unlock-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"

for context in ${APPLICATION_ROOT} ${INSTALLER_ROOT}; do
    if [[ "${context}" == "${APPLICATION_ROOT}" ]]; then
        keyusage="codeSigning"
        certtype="1.2.840.113635.100.6.1.13"
        commonname="${APPLICATION_SIGNING_ID}"
        password="${APPLICATION_SIGNING_PASSWORD}"
    else
        keyusage="1.2.840.113635.100.4.13"
        certtype="1.2.840.113635.100.6.1.14"
        commonname="${INSTALLER_SIGNING_ID}"
        password="${INSTALLER_SIGNING_PASSWORD}"
    fi

    keyfile="${ROOT_DIR}/${context}.key"
    p12file="${ROOT_DIR}/${context}.p12"
    crtfile="${ROOT_DIR}/${context}.crt"
    pemfile="${ROOT_DIR}/${INSTALLER_ROOT}.pem"

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
    # shellcheck disable=SC2086
    openssl pkcs12 -in "${p12file}" -clcerts -nokeys -out "${pemfile}" ${legacy} -password pass:"${password}"

    # Output to verify installer signatures
    fingerprint=$(openssl x509 -in "${pemfile}" -noout -fingerprint -sha256 | cut -f2 -d'=' | sed 's/://g')
    echo "SHA256 ${commonname} = ${fingerprint}"
    if [[ "${context}" == "installer" ]]; then
        # Installer certificates must be trusted to be found in the keychain.
        # In non-CI environments, users will be asked for a passkey.
        security add-trusted-cert -p basic -k "${KEYCHAIN_PATH}" "${pemfile}"
    fi
done

# Add keychain at the beginning of the keychain list
# Must be removed at a later clean-up step
# shellcheck disable=SC2046
security list-keychains -d user -s "${KEYCHAIN_PATH}" $(security list-keychains | xargs)

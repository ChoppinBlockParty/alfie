"""Operator backup encryption using OpenSSL CMS AES-256-GCM and RSA-OAEP.

Private keys stay on the recovery Mac, never on the VPS. Decryption writes a private
temporary file and publishes it only after authentication succeeds; never pipe decrypted
output directly to an extractor. No custom cryptographic primitives or account APIs.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def openssl():
    executable = shutil.which('openssl')
    if not executable:
        raise ValueError('OpenSSL is required')
    return executable


def run(arguments):
    result = subprocess.run([openssl(), *arguments], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=1800)
    if result.returncode:
        raise ValueError('OpenSSL operation failed; no output published')


def keygen(directory):
    directory = Path(directory)
    # Refuse overwrites: losing an old recovery key makes its backups unreadable.
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    directory.chmod(0o700)
    key, cert = directory / 'recovery.key.pem', directory / 'recipient.cert.pem'
    old = os.umask(0o077)
    try:
        run(['req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '3650',
             '-subj', '/CN=Alfie backup recovery', '-keyout', str(key), '-out', str(cert)])
    finally:
        os.umask(old)
    key.chmod(0o600)
    cert.chmod(0o600)
    return key, cert


def transform(source, destination, certificate, *, private_key=None):
    source, destination, certificate = map(Path, (source, destination, certificate))
    if source.is_symlink() or not source.is_file():
        raise ValueError('Input must be a regular file')
    if destination.exists() or destination.is_symlink():
        raise ValueError('Never overwrite a backup or recovered archive')
    if not certificate.is_file():
        raise ValueError('Recipient certificate required')
    # Tempfile permissions are 0600. A failed authentication never becomes the output.
    fd, temporary = tempfile.mkstemp(prefix='.alfie-crypto-', dir=destination.parent)
    os.close(fd)
    try:
        if private_key is None:
            args = ['cms', '-encrypt', '-binary', '-stream', '-outform', 'DER',
                    '-aes-256-gcm', '-in', str(source), '-out', temporary,
                    '-recip', str(certificate), '-keyopt', 'rsa_padding_mode:oaep',
                    '-keyopt', 'rsa_oaep_md:sha256']
        else:
            key = Path(private_key)
            if key.is_symlink() or key.stat().st_mode & 0o077:
                raise ValueError('Recovery key must be private (0600)')
            args = ['cms', '-decrypt', '-binary', '-inform', 'DER', '-in', str(source),
                    '-out', temporary, '-recip', str(certificate), '-inkey', str(key)]
        run(args)
        # Hard-link publication is exclusive, including races with another operator.
        os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    generate = sub.add_parser('keygen')
    generate.add_argument('directory')
    for name in ('encrypt', 'decrypt'):
        command = sub.add_parser(name)
        command.add_argument('source')
        command.add_argument('destination')
        command.add_argument('--certificate', required=True)
        if name == 'decrypt':
            command.add_argument('--private-key', required=True)
    args = parser.parse_args()
    if args.action == 'keygen':
        keygen(args.directory)
    else:
        transform(args.source, args.destination, args.certificate,
                  private_key=getattr(args, 'private_key', None))
    print('PASS backup cryptographic operation completed; sensitive paths/content omitted')

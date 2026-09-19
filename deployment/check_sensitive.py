#!/usr/bin/env python3
"""Scan publishable files or staged changes; report locations, never matched values.

This is a guard for common credentials and known local identifiers, not proof of absence.
Run from anywhere inside the repository. Historical objects require a separate scan.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys

PATTERNS = {
    'private key': re.compile(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY'),
    'provider token': re.compile(rb'\b(?:AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{35}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})'),
    'Telegram token': re.compile(rb'\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}'),
}
PRIVATE_NAME = re.compile(r'(^|/)(\.env(?!\.example$)[^/]*|auth\.json|pki|backups)(/|$)|\.(pem|key|p12|pfx|db|sqlite)$|(?:token|credential|client_secret)[^/]*\.json$')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
    local = root / '.env.local'
    identifiers = []
    if local.exists():
        for line in local.read_text().splitlines():
            key, sep, value = line.partition('=')
            value = value.strip().strip('\"\'')
            if sep and not key.startswith('#') and len(value) >= 8:
                identifiers.append(value.encode())
    command = (['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'] if args.staged else
               ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    paths = set(subprocess.check_output(command, cwd=root).decode().split('\0')) - {''}
    failures = 0
    for name in sorted(paths):
        if PRIVATE_NAME.search(name):
            print(f'{name}: forbidden private artifact'); failures += 1
            continue
        if args.staged:
            data = subprocess.check_output(['git', 'show', ':' + name], cwd=root)
        else:
            path = root / name
            if not path.is_file():
                continue
            data = path.read_bytes()
        for number, line in enumerate(data.splitlines(), 1):
            labels = [label for label, pattern in PATTERNS.items() if pattern.search(line)]
            if any(value in line for value in identifiers):
                labels.append('local deployment identifier')
            if labels:
                print(f'{name}:{number}: ' + ', '.join(labels)); failures += 1
    print(f'Scanned {len(paths)} files; {failures} findings.')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Render public-address templates to stdout; callers send output directly over SSH."""
import ipaddress
import os
from pathlib import Path
import sys


def render(source, environ):
    for name, version in (("ALFIE_PUBLIC_IPV4", 4), ("ALFIE_PUBLIC_IPV6", 6)):
        marker = "@@" + name + "@@"
        if marker not in source:
            continue
        try:
            address = ipaddress.ip_address(environ.get(name, ""))
        except ValueError:
            raise ValueError(f"Set a valid {name} in .env.local") from None
        if address.version != version:
            raise ValueError(f"Wrong address family for {name}")
        source = source.replace(marker, str(address))
    return source


if __name__ == "__main__":
    try:
        sys.stdout.write(render(Path(sys.argv[1]).read_text(), os.environ))
    except ValueError as exc:
        sys.exit(str(exc))

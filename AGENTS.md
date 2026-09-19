# Alfie repository instructions

Follow the project and working instructions in `CLAUDE.md`.

Treat this repository as public. Never add real secrets, credentials, API/OAuth tokens,
private or public keys, personal identifiers, account IDs, email addresses, usernames,
public host IP addresses, instance IDs, SSH aliases, sensitive host paths, backup names,
or other deployment-specific identifiers. Use obvious placeholders or environment variables.

Before committing, scan both staged changes and newly added files for sensitive information.
Run `python3 deployment/check_sensitive.py` and `python3 deployment/check_sensitive.py --staged`.
If a real value is required for deployment, keep it in an ignored local file or external
secret store and document only its variable name and expected format.

# Public repository sanitization plan

## Working tree

- [x] Store SSH target and Telegram bot username/chat/topic/user IDs in ignored
      `.env.local`, mode 0600. Replace actual public IPv4/IPv6 even in that local file with
      non-address placeholders. Deployment refuses these until the operator supplies addresses.
      Publish only `.env.example` with reserved example addresses.
- [x] Load local configuration from every subsystem deploy script. Render validated public
      addresses into firewall, Squid and verification files before transfer, preserving denials.
- [x] Remove embedded Telegram destinations from registration; deliver private settings over
      SSH stdin. Preserve existing origins for direct on-host updates without supplied settings.
- [x] Remove owner name, bot identity, host/provider inventory, instance ID, exact credential
      source, backup names, cron ID, home timezone declaration and certificate expiry from docs.
- [x] Ignore environment files, keys, credential JSON, databases, logs, PKI and backups.
- [x] Add agent instructions and a location-only scanner for common secrets and identifiers
      from `.env.local`. Run `python3 deployment/check_sensitive.py` and, before each commit,
      `python3 deployment/check_sensitive.py --staged`.
- [x] Verify 65 local tests, Bash/POSIX shell syntax, rendered Python syntax, ignore coverage,
      and a clean working-tree sensitive-data scan. Existing unrelated user edits are preserved.
- [x] Deploy and perform live acceptance in a maintenance window. See deployment/acceptance.md
      for current evidence and limitations. On-host rendered rules retain private values.

Generic private network ranges, container service names, default installation paths, required
ports, dependency versions and documented security boundaries remain public implementation
details. They grant no access. Do not remove deny rules or hide security limitations to sanitize
the repository. Real host addresses and account identities belong only in private configuration.

## Publish this repository with one sanitized root commit

The selected approach is to collapse this repository's local history into one new commit.
The separate export is not the publication target. Keep this repository private until the
remote replacement and remaining publication checks are complete.

- [x] Back up all old Git refs, Git metadata and working files (including local configuration)
      under ignored `.private/`, with private permissions. Verify the recovery bundle.
- [x] Replace local history with one parentless commit containing the sanitized working tree,
      including current user edits. Remove old local remote-tracking refs and reflogs, and prune
      unreachable old objects after verification. Recovery history remains in the private backup.
- [x] Use the operator's configured Git author/committer identity, explicitly approved for
      publication. Other private identifiers remain excluded from repository content.
- [x] Replace the remote branch using an explicit force-with-lease against the reviewed remote
      tip. First inspect remote branches and tags; stop if the remote has unexpected changes.
      A normal fetch before replacement can reintroduce old remote-tracking history locally.
- [ ] Scan the final commit with a dedicated secret scanner; review findings and any unrecognized
      high-entropy strings before publication. The built-in pattern and known-value checks pass,
      but do not replace a dedicated scanner.
- [ ] Review remote branches, tags, PRs, releases and artifacts for earlier disclosures.
      Local scanning cannot establish their absence. Rotate/revoke any actual credential found
      exposed; removing its Git history is not revocation.
- [ ] Make this existing repository public only after these checks. Local history replacement
      does not replace remote history, change repository visibility or revoke credentials.

No actual credential value was identified by the initial pattern scan; this is not a guarantee
that none exists. Public addresses and Telegram IDs are identifiers, not authentication secrets.

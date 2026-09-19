# Encrypted recovery backups

Operator-only subsystem using existing containers and existing restricted Google Drive access.
No model-callable backup/upload/decrypt tool. The owner authorized the unique accessible `Alfie`
folder and its `backup` child; the exact IDs are pinned in ignored/private host configuration.
No account-wide Drive scope was added. Backups are manual by owner decision. No recurring timer
or automatic retention deletion is enabled; neither should be enabled without a new instruction.

## Encryption and key custody

`crypto.py` uses OpenSSL CMS authenticated encryption (AES-256-GCM), with the content key
wrapped using RSA-OAEP/SHA-256. It uses streaming encryption, exclusive output publication and
0600 temporary files. Decryption publishes no output until authentication succeeds; never pipe
unauthenticated plaintext into tar. Round-trip, tampering and overwrite tests are included.
See the [OpenSSL CMS documentation](https://docs.openssl.org/3.3/man1/openssl-cms/).

The recovery private key and matching certificate are generated only on the owner's Mac:

```bash
python3 backup/crypto.py keygen .private/backup-recovery
```

The command refuses to overwrite an existing directory/key. The VPS receives only
`recipient.cert.pem`, never `recovery.key.pem`. The private key is permission-protected but
not passphrase-encrypted. Keep the Mac encrypted and make a separate secure offline copy of
both files; losing the only key loses recovery. Repository cleanup/deletion must not delete
the ignored key directory. The public repository contains no keys, IDs or backup artifact names.

## Capture and transfer

Host code is staged under `/opt/alfie/backup` (0700). `snapshot.py` checks disk headroom and the
expected persistent mounts, stops only the gateway, captures project state and sandbox host
keys, then restarts the gateway even if capture fails. Capture has a five-GiB input budget and
a ten-minute checked deadline. It is not a zero-downtime backup: notice is required beforehand.

The archive includes credentials, personal databases, WAL state, cron definitions, code and
configuration. Existing backups, selected rebuildable caches/logs and the upstream Git object
directory are excluded (see `EXCLUDED` in source). Docker images are inventoried, not exported;
host OS, SSH administration configuration and a complete replacement-host rebuild are not
covered. Do not call this a complete machine image.

After successful encryption the task-created plaintext archive is removed. On failure it may
remain in the root-only snapshot directory for operator investigation. No uploads occur from
that plaintext path. Host ciphertext is retained; no broad cleanup commands are used.

`drive_backup.py configure` creates only a missing `backup` child under the unique accessible
owner-approved parent. Multiple matching folders fail closed. Save its output privately.
Uploads revalidate the pinned destination, use content-addressed names and never overwrite or
delete Drive files. They check size/checksum and produce a private receipt. Uncertain creation
requires reconciliation; resumable transfers have no blind automatic retries.

`transfer_host.py` stages ciphertext in the gateway, uploads it, downloads it again, verifies its
SHA-256 and removes only its explicit temporary transfer files. Model task grants cannot invoke
this operator path. Same-account compromise could delete Drive backups; offline key custody
does not protect availability. Google Drive is not immutable/offline storage.

## Recovery rehearsal

Copy the encrypted Drive read-back to the Mac, then:

```bash
python3 backup/crypto.py decrypt .private/backup-recovery/readback.cms \
  .private/backup-recovery/recovered.tar.gz \
  --certificate .private/backup-recovery/recipient.cert.pem \
  --private-key .private/backup-recovery/recovery.key.pem
python3 backup/rehearse_restore.py .private/backup-recovery/recovered.tar.gz \
  .private/backup-recovery/rehearsal
```

Existing outputs are not overwritten. Use fresh private paths for subsequent rehearsals.
`rehearse_restore.py` extracts only selected regular data/config files into a new private
directory, refuses traversal and selected symlinks, checks SQLite integrity and exercises
approval invalidation on the recovered copy. It never starts a gateway, invokes Google or
delivers messages. Rehearsal data is plaintext/private and must not be committed or synced to
unapproved storage. Keep it protected until the owner chooses a cleanup policy.

Before any real restore starts writers: invalidate approvals, reconcile unknown actions,
restore current deny policies and read-only mounts, and install the firewall-first boot gate
from current deployment sources. The first encrypted snapshot predates the boot-gate cutover;
do not blindly start its older Compose restart configuration. A full replacement-host rebuild
and image recovery remain separate acceptance work.

## Evidence and tests

On 2026-09-19 the first encrypted artifact was uploaded and read back from the pinned folder;
size and digest matched. On the Mac it authenticated/decrypted, recovered 26 selected artifacts
and passed integrity checks on 14 SQLite databases. Pending/executing approval sentinels became
expired/unknown on the recovered copy. No duplicate live service or account write was executed.

```bash
python3 -m unittest discover -s backup -p 'test_*.py'
```

Keep receipts, snapshots, private configuration, keys and raw recovery logs out of the public
repository. Acceptance status belongs in `deployment/acceptance.md`.

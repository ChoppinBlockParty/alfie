"""Bounded pending actions. No approval or execution authority is exposed here.

The authenticated Telegram integration must be completed before requests can execute.
This store is private gateway state, never a sandbox mount or model-editable policy.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid
from contextlib import closing
from contextlib import contextmanager

TTL_S = 24 * 60 * 60
MAX_PENDING = 100
MAX_ACTION_BYTES = 128 * 1024
STORE = Path('/opt/data/security/pending-actions.sqlite')


@contextmanager
def database(path=None):
    """Version two never consumes legacy, unauthenticated pending_actions rows."""
    path = Path(path) if path is not None else STORE
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o077:
        raise ValueError('Approval directory must be private')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise ValueError('Approval database must be private')
    finally:
        os.close(fd)
    with closing(sqlite3.connect(path, timeout=5)) as con, con:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA secure_delete=ON')
        con.execute('''CREATE TABLE IF NOT EXISTS telegram_actions (
            id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL,
            binding TEXT NOT NULL, epoch TEXT NOT NULL, message TEXT,
            created REAL NOT NULL, expires REAL NOT NULL, status TEXT NOT NULL)''')
        con.execute('BEGIN IMMEDIATE')
        yield con


def enqueue(operation, arguments, binding, epoch, *, path=None, now=None):
    now = time.time() if now is None else now
    payload, digest = canonical_action(operation, arguments)
    binding = json.dumps(binding, sort_keys=True)
    with database(path) as con:
        con.execute("DELETE FROM telegram_actions WHERE expires<=? AND status NOT IN ('executing','unknown')", (now,))
        if con.execute('SELECT count(*) FROM telegram_actions').fetchone()[0] >= MAX_PENDING:
            raise ValueError('Approval capacity reached')
        request_id = uuid.uuid4().hex
        con.execute('INSERT INTO telegram_actions VALUES (?,?,?,?,?,?,?,?,?)',
                    (request_id, payload, digest, binding, epoch, None, now, now + TTL_S, 'presenting'))
    return request_id, payload, digest


def bind_message(request_id, message, epoch, *, path=None):
    with database(path) as con:
        if con.execute("UPDATE telegram_actions SET message=?,status='pending' "
                       "WHERE id=? AND epoch=? AND status='presenting'",
                       (str(message), request_id, epoch)).rowcount != 1:
            raise ValueError('Review no longer available')


def consume(request_id, origin, message, epoch, accept, *, path=None, now=None, validate=None):
    now = time.time() if now is None else now
    with database(path) as con:
        row = con.execute('SELECT * FROM telegram_actions WHERE id=?', (request_id,)).fetchone()
        if not row or row['status'] != 'pending' or row['expires'] <= now or row['epoch'] != epoch:
            raise ValueError('Review is expired or already consumed')
        binding = json.loads(row['binding'])
        if any(binding.get(k) != origin.get(k) for k in ('user', 'chat', 'thread')) or row['message'] != str(message):
            raise ValueError('Review origin mismatch')
        if hashlib.sha256(row['payload'].encode()).hexdigest() != row['digest']:
            raise ValueError('Review content changed')
        action = json.loads(row['payload'])
        if accept and validate is not None:
            validate(binding, action)
        con.execute('UPDATE telegram_actions SET status=? WHERE id=?',
                    ('executing' if accept else 'rejected', request_id))
        if accept and validate is not None:
            action['authorization'] = binding
        return action if accept else None


def finish(request_id, status, *, path=None):
    if status not in ('succeeded', 'unknown'):
        raise ValueError('Invalid outcome')
    with database(path) as con:
        con.execute("UPDATE telegram_actions SET status=? WHERE id=? AND status='executing'",
                    (status, request_id))


def restart(*, path=None):
    with database(path) as con:
        con.execute("UPDATE telegram_actions SET status='expired' WHERE status IN ('presenting','pending')")
        con.execute("UPDATE telegram_actions SET status='unknown' WHERE status='executing'")


def canonical_action(operation, arguments):
    payload = json.dumps({'operation': operation, 'arguments': arguments},
                         sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                         allow_nan=False)
    if len(payload.encode()) > MAX_ACTION_BYTES:
        raise ValueError('Action is too large for review')
    return payload, hashlib.sha256(payload.encode()).hexdigest()


def propose(operation, arguments, *, path=None, now=None):
    path = Path(path) if path is not None else STORE
    now = time.time() if now is None else now
    payload, digest = canonical_action(operation, arguments)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Fail closed if deployment accidentally exposes approval state to other users.
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o077:
        raise ValueError('Pending action directory must be private')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_mode & 0o077:
            raise ValueError('Pending action database must be private')
    finally:
        os.close(fd)
    with closing(sqlite3.connect(path, timeout=5)) as con, con:
        con.execute('PRAGMA secure_delete=ON')
        con.execute('''CREATE TABLE IF NOT EXISTS pending_actions (
            id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL,
            created REAL NOT NULL, expires REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'expired'))
        )''')
        con.execute('BEGIN IMMEDIATE')
        # Expired requests have no authority and retain no private message bodies.
        con.execute('DELETE FROM pending_actions WHERE expires <= ?', (now,))
        found = con.execute('SELECT id, expires FROM pending_actions '
                            'WHERE digest=? AND payload=? AND status=?',
                            (digest, payload, 'pending')).fetchone()
        if found:
            request_id, expires = found
        else:
            if con.execute('SELECT count(*) FROM pending_actions').fetchone()[0] >= MAX_PENDING:
                raise ValueError('Pending action limit reached; owner review required')
            request_id, expires = uuid.uuid4().hex, now + TTL_S
            con.execute('INSERT INTO pending_actions VALUES (?,?,?,?,?,?)',
                        (request_id, payload, digest, now, expires, 'pending'))
    return {'status': 'pending_approval', 'request_id': request_id,
            'digest': digest, 'expires_at': expires,
            'notice': 'No account change was made. Authenticated Telegram approvals are '
                      'not connected yet; this request cannot execute. Chat text is not approval.'}

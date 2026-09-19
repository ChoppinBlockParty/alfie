"""Operator-only read-only inspection of uncertain actions; never retries or changes status.

Run inside the gateway with --request-id from private operator records. Output is private:
redirect it to a permission-protected file, never public logs. Matching current state is not
proof this request caused it; missing evidence is not proof it did not execute.
"""
import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys


def inspect(path, request_id, lookup):
    with closing(sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)) as con:
        con.row_factory = sqlite3.Row
        row = con.execute('SELECT * FROM telegram_actions WHERE id=?', (request_id,)).fetchone()
    if not row or row['status'] not in ('unknown', 'executing', 'succeeded'):
        raise ValueError('No execution outcome to reconcile')
    if hashlib.sha256(row['payload'].encode()).hexdigest() != row['digest']:
        raise ValueError('Stored action integrity failure')
    action = json.loads(row['payload'])
    binding = json.loads(row['binding'])
    report = {'status': row['status'], 'action': action, 'reviewed_context': binding.get('review_context'),
              'conclusion': 'Unresolved. Never automatically retry; current state does not establish causation.'}
    # These exact existing targets can be read without searching unrelated private data.
    if action['operation'] in ('gmail.modify', 'calendar.delete', 'docs.append', 'sheets.update', 'sheets.append'):
        try:
            report['current_context'] = lookup(action['operation'], action['arguments'])
        except Exception:
            report['current_context'] = {'error': 'Target unavailable; absence does not establish execution'}
    else:
        report['next_step'] = 'Inspect Sent mail or the exact destination in Google; creation/send cannot be proved from this local record.'
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-id', required=True)
    args = parser.parse_args()
    try:
        spec = importlib.util.spec_from_file_location('reconcile_connector',
            '/opt/data/plugins/google_workspace/__init__.py')
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        print(json.dumps(inspect('/opt/data/security/pending-actions.sqlite', args.request_id, plugin.review_context),
                         ensure_ascii=True, sort_keys=True, indent=2))
    except Exception:
        print('Reconciliation unavailable; no changes or retry performed', file=sys.stderr)
        sys.exit(1)

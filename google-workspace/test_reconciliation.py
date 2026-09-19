import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock
from reconcile import inspect


class ReconciliationTests(unittest.TestCase):
    def test_read_only_inspection_never_concludes_success_from_matching_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'actions.sqlite'
            payload = json.dumps({'operation':'docs.append','arguments':{'doc_id':'fixture','text':'synthetic'}})
            with closing(sqlite3.connect(path)) as con, con:
                con.execute('CREATE TABLE telegram_actions (id,payload,digest,binding,status)')
                con.execute('INSERT INTO telegram_actions VALUES (?,?,?,?,?)',
                    ('fixture',payload,hashlib.sha256(payload.encode()).hexdigest(),'{}','unknown'))
            lookup = Mock(return_value={'target':'synthetic'})
            report = inspect(path, 'fixture', lookup)
            self.assertEqual(report['status'], 'unknown')
            self.assertIn('Unresolved', report['conclusion'])
            lookup.assert_called_once_with('docs.append', {'doc_id':'fixture','text':'synthetic'})
            with closing(sqlite3.connect(path)) as con, con:
                self.assertEqual(con.execute('SELECT status FROM telegram_actions').fetchone()[0], 'unknown')
                con.execute("UPDATE telegram_actions SET payload='{}'")
            with self.assertRaises(ValueError): inspect(path, 'fixture', lookup)

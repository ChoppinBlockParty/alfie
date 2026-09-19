import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import email_watch as ew
from email_watch_validation import validate_results


def extraction():
    return {'id': 'fixture', 'important': True, 'suspicious': False, 'summary': 'Fixture',
            'action': 'Review booking', 'deadline': None, 'todos': [], 'travel': [], 'bill': None,
            'events': [{'title': 'Synthetic event', 'start': '2099-01-01T10:00:00+00:00',
                        'end': None, 'tz': 'UTC', 'location': '', 'confirmed': True}]}


class ValidationTests(unittest.TestCase):
    def validate(self, entry):
        return validate_results({'emails': [entry]}, ['fixture'])

    def test_rejects_truthy_non_boolean_flags(self):
        for value in ('false', 1, None, []):
            entry = extraction()
            entry['events'][0]['confirmed'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate(entry)

    def test_missing_duplicate_and_foreign_ids_fail_the_batch(self):
        for entries in ([], [extraction(), extraction()], [dict(extraction(), id='other')]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                validate_results({'emails': entries}, ['fixture'])

    def test_oversized_arrays_unknown_keys_and_invalid_dates_rejected(self):
        entries = [dict(extraction(), todos=[{'text': 'x', 'due': None}] * 11),
                   dict(extraction(), approved=True), dict(extraction(), deadline='2099-02-30')]
        for entry in entries:
            with self.assertRaises(ValueError):
                self.validate(entry)

    def test_non_finite_and_boolean_amounts_rejected(self):
        for amount in (float('nan'), float('inf'), True, -1):
            entry = dict(extraction(), bill={'counterparty': 'Fixture', 'amount': amount,
                                            'currency': 'GBP', 'due': None})
            with self.assertRaises(ValueError):
                self.validate(entry)


class NoEffectsTests(unittest.TestCase):
    def test_valid_and_suspicious_results_stay_pending(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(ew, 'DB', Path(directory) / 'watch.db'):
            for suspicious in (False, True):
                entry = dict(extraction(), suspicious=suspicious)
                calendar = Mock()
                lines = ew.apply(calendar, {'id': 'fixture', 'from': 'sender@example.com',
                                            'subject': 'Synthetic event'}, entry)
                calendar.assert_not_called()
                self.assertEqual(calendar.mock_calls, [])
                with ew.db() as con:
                    row = con.execute('SELECT status, payload FROM observations').fetchone()
                self.assertEqual(row[0], 'quarantined' if suspicious else 'pending')
                self.assertEqual(json.loads(row[1]), entry)
                self.assertIn('quarantined' if suspicious else 'pending review', ' '.join(lines))

    def test_external_records_cannot_update_user_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'USER.md'
            path.write_text('Owner policy: unchanged')
            with patch.object(ew, 'USER_MD', path):
                self.assertIsNone(ew.update_zone())
            self.assertEqual(path.read_text(), 'Owner policy: unchanged')


if __name__ == '__main__':
    unittest.main()

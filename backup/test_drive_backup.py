import unittest
from unittest.mock import MagicMock

from drive_backup import configure, validate_destination


class DriveBackupTests(unittest.TestCase):
    def test_creates_only_missing_child_in_unique_parent(self):
        service = MagicMock()
        service.files().list().execute.side_effect = [
            {'files': [{'id': 'synthetic-parent'}]}, {'files': []}]
        service.files().create().execute.return_value = {'id': 'synthetic-folder'}
        # Discard mock setup calls, preserving configured return values.
        service.reset_mock()
        self.assertEqual(configure(service)['folder'], 'synthetic-folder')
        body = service.files().create.call_args.kwargs['body']
        self.assertEqual(body['parents'], ['synthetic-parent'])
        self.assertEqual(body['name'], 'backup')

    def test_existing_child_is_reused(self):
        service = MagicMock()
        service.files().list().execute.side_effect = [
            {'files': [{'id': 'synthetic-parent'}]}, {'files': [{'id': 'synthetic-folder'}]}]
        self.assertEqual(configure(service)['folder'], 'synthetic-folder')
        service.files().create.assert_not_called()

    def test_ambiguous_parent_or_pagination_denied(self):
        for result in ({'files': []}, {'files': [{'id': 'a'}, {'id': 'b'}]},
                       {'files': [{'id': 'a'}], 'nextPageToken': 'synthetic'}):
            service = MagicMock()
            service.files().list().execute.return_value = result
            with self.assertRaises(ValueError):
                configure(service)
            service.files().create.assert_not_called()

    def test_moved_or_trashed_destination_denied(self):
        service = MagicMock()
        base = {'name': 'backup', 'parents': ['synthetic-parent'],
                'mimeType': 'application/vnd.google-apps.folder'}
        for changes in ({'parents': ['other']}, {'trashed': True}, {'name': 'renamed'}):
            service.files().get().execute.return_value = dict(base, **changes)
            with self.assertRaises(ValueError):
                validate_destination(service, {'parent': 'synthetic-parent', 'folder': 'synthetic-folder'})

import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
import google_api
import review_context


class ReviewContextTests(unittest.TestCase):
    def test_sheet_update_uses_literal_values(self):
        api = Mock()
        api.spreadsheets.return_value.values.return_value.update.return_value.execute.return_value = {'updatedCells':1}
        with patch.object(google_api, '_gws_binary', return_value=None), \
             patch.object(google_api, 'build_service', return_value=api), patch('sys.stdout', io.StringIO()):
            google_api.sheets_update(SimpleNamespace(sheet_id='fixture', range='A1', values='[["=1+1"]]'))
        kwargs = api.spreadsheets.return_value.values.return_value.update.call_args.kwargs
        self.assertEqual(kwargs['valueInputOption'], 'RAW')

    def test_drive_search_escapes_query_literal(self):
        api = Mock()
        api.files.return_value.list.return_value.execute.return_value = {'files':[]}
        with patch.object(google_api, '_gws_binary', return_value=None), \
             patch.object(google_api, 'build_service', return_value=api), patch('sys.stdout', io.StringIO()):
            google_api.drive_search(SimpleNamespace(query="x' or trashed = true or name = 'x", raw_query=False, max=5))
        self.assertEqual(api.files.return_value.list.call_args.kwargs['q'],
                         "fullText contains 'x\\' or trashed = true or name = \\'x'")

    def test_target_metadata_type_and_trash_fail_closed(self):
        api = Mock()
        result = {'id':'fixture','name':'Synthetic','mimeType':'application/vnd.google-apps.document',
                  'version':'1','shared':True}
        api.files.return_value.get.return_value.execute.return_value = result
        with patch.object(review_context, 'build_service', return_value=api):
            output = review_context.context('docs.append', {'doc_id':'fixture','text':'synthetic'})
            self.assertEqual(output['target'], result)
            self.assertIn('viewers', output['disclosure'])
            for change in ({'trashed':True}, {'mimeType':'wrong'}):
                api.files.return_value.get.return_value.execute.return_value = dict(result, **change)
                with self.assertRaises(ValueError):
                    review_context.context('docs.append', {'doc_id':'fixture','text':'synthetic'})

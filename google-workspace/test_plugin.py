import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('google_plugin', Path(__file__).parent/'gateway-plugin/__init__.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
class BoundaryTests(unittest.TestCase):
    def test_no_arbitrary_file_or_command(self):
        for op,args in [('drive.upload', {'path':'/opt/data/auth.json'}), ('gmail.get',{'message_id':'--help'}),
                        ('gmail.search',{'query':'x','path':'/opt/data/.env'}), ('gmail.search',{'query':'x','max':True})]:
            with self.assertRaises(ValueError): p.build_args(op,args)
    def test_option_value_cannot_inject(self):
        self.assertEqual(p.build_args('gmail.send',{'to':'a@example.com','subject':'--help','body':'$(id)'}),
                         ['gmail','send','--to=a@example.com','--subject=--help','--body=$(id)'])
    def test_read_and_boolean(self):
        self.assertEqual(p.build_args('gmail.search',{'query':'booking','max':5}),['gmail','search','booking','--max=5'])
        with self.assertRaises(ValueError): p.build_args('gmail.send', {'to':'x','subject':'x','body':'x','html':'false'})
if __name__ == '__main__': unittest.main()

from pathlib import Path
import tempfile
import unittest

from crypto import keygen, transform


class CryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.key, cls.cert = keygen(cls.root / 'keys')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_roundtrip_tampering_and_no_overwrite(self):
        source = self.root / 'synthetic.tar'
        source.write_bytes(b'Synthetic backup canary\x00' * 10000)
        encrypted, restored = self.root / 'backup.cms', self.root / 'restored.tar'
        transform(source, encrypted, self.cert)
        self.assertNotIn(b'Synthetic backup canary', encrypted.read_bytes())
        transform(encrypted, restored, self.cert, private_key=self.key)
        self.assertEqual(restored.read_bytes(), source.read_bytes())
        with self.assertRaises(ValueError):
            transform(source, encrypted, self.cert)
        damaged = bytearray(encrypted.read_bytes())
        damaged[len(damaged) // 2] ^= 1
        corrupt = self.root / 'corrupt.cms'
        corrupt.write_bytes(damaged)
        rejected = self.root / 'must-not-exist.tar'
        with self.assertRaises(ValueError):
            transform(corrupt, rejected, self.cert, private_key=self.key)
        self.assertFalse(rejected.exists())
        self.assertFalse(list(self.root.glob('.alfie-crypto-*')))

    def test_key_generation_never_replaces_existing_directory(self):
        before = self.key.read_bytes()
        with self.assertRaises(FileExistsError):
            keygen(self.key.parent)
        self.assertEqual(self.key.read_bytes(), before)

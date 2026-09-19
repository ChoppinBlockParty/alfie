import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from contextlib import contextmanager
sys.path.insert(0, str(Path(__file__).parent / 'worker'))
import retrieval as r


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        r.public_addresses.cache_clear()

    def test_private_mixed_and_malformed_destinations_denied(self):
        for url in ('file:///etc/passwd', 'http://localhost/', 'https://u:p@example.com',
                    'https://example.com:22', 'https://example.com/\n', 'http://a.internal'):
            with self.subTest(url=url), self.assertRaises(ValueError): r.public_url(url)
        for ips in (['127.0.0.1'], ['169.254.169.254'], ['::1'], ['93.184.216.34', '10.0.0.1']):
            r.public_addresses.cache_clear()
            with patch.object(r, 'request_json', return_value={'Status':0,'Answer':[{'type':1,'data':ip} for ip in ips]}):
                with self.assertRaises(ValueError): r.public_url('https://example.com')
        with patch.object(r, 'request_json', return_value={'Status':0,'Answer':[{'type':1,'data':'93.184.216.34'}]}) as dns:
            self.assertEqual(r.public_url('https://example.com'), 'https://example.com')
            self.assertEqual(dns.call_count, 2)
            self.assertEqual(dns.call_args.args[1], 'https://cloudflare-dns.com/dns-query')
        with patch.object(r, 'request_json') as dns, self.assertRaises(ValueError):
            r.public_url('http://127.0.0.1')
        dns.assert_not_called()

    def test_stream_limits_redirect_compression_and_json_shape(self):
        try:
            import httpx
        except ImportError:
            self.skipTest('httpx installed in worker runtime')
        @contextmanager
        def response(status=200, headers=None, chunks=(b'{}',)):
            yield Mock(status_code=status, headers=headers or {}, iter_raw=Mock(return_value=iter(chunks)))
        for kwargs in ({'status':302}, {'headers':{'content-encoding':'gzip'}},
                       {'headers':{'content-length':str(r.MAX_RESPONSE+1)}},
                       {'chunks':(b'x' * (r.MAX_RESPONSE+1),)}, {'chunks':(b'[]',)}, {'chunks':(b'{broken',)}):
            with patch.object(httpx, 'stream', return_value=response(**kwargs)), self.assertRaises(r.VendorFailed):
                r.post_json('https://example.com', {}, {})
        with patch.object(httpx, 'stream', return_value=response()) as send:
            self.assertEqual(r.post_json('https://example.com', {}, {}), {})
            self.assertFalse(send.call_args.kwargs['follow_redirects'])
            self.assertEqual(send.call_args.kwargs['headers']['Accept-Encoding'], 'identity')

    def test_bad_scrape_url_never_sent_and_bad_schema_rejected(self):
        with patch.object(r, 'post_json') as send:
            self.assertTrue(r.extract('http://localhost/', 100)['error'])
            send.assert_not_called()
        with patch.object(r, 'public_url', side_effect=lambda url:url), \
             patch.object(r, 'post_json', return_value={'data':{'markdown':[],'metadata':{'title':[]}}}):
            self.assertTrue(r.extract('https://example.com', 100)['error'])
        with patch.object(r, 'post_json', return_value={'results':'bad'}), self.assertRaises(r.VendorFailed):
            r.search('synthetic')

import asyncio
import importlib.util
from pathlib import Path
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

spec=importlib.util.spec_from_file_location('browser',Path(__file__).parent/'worker/browser.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
plugin_spec=importlib.util.spec_from_file_location('browser_plugin',Path(__file__).parent/'gateway-plugin/__init__.py')
plugin=importlib.util.module_from_spec(plugin_spec);plugin_spec.loader.exec_module(plugin)

class URLTests(unittest.TestCase):
    def test_reject_unsafe_navigation(self):
        for url in ('file:///etc/passwd','data:text/html,hello','javascript:alert(1)',
                    'http://localhost','http://127.0.0.1','http://169.254.169.254/',
                    'http://172.31.240.2','https://[::1]/','http://2130706433',
                    'http://0177.0.0.1','https://user:pass@example.com','https://example.com:22',
                    'http://224.0.0.1','http://test.internal','https://example.com/\n'):
            with self.subTest(url=url), self.assertRaises(ValueError): b.public_url(url)
    def test_public_urls(self):
        for url in ('https://example.com','https://books.toscrape.com/catalogue/page-2.html','http://1.1.1.1'):
            self.assertEqual(b.public_url(url),url)

class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setup_active(self):
        worker=b.Browser();worker.session='owned';worker.started=worker.touched=time.monotonic()
        worker.browser=AsyncMock();worker.playwright=AsyncMock();worker.snapshot=AsyncMock(return_value={})
        return worker
    async def test_foreign_session_cannot_act(self):
        worker=self.setup_active()
        with self.assertRaises(ValueError): await worker.perform({'action':'close','session_id':'foreign'})
        self.assertTrue(worker.active)
        worker.browser.close.assert_not_awaited()
    async def test_expiry_releases_browser(self):
        worker=self.setup_active();chrome=worker.browser;worker.touched-=b.IDLE_S+1
        await worker.expire()
        self.assertFalse(worker.active);chrome.close.assert_awaited_once()
    async def test_absolute_expiry(self):
        worker=self.setup_active();worker.started-=b.LIFETIME_S+1
        await worker.expire();self.assertFalse(worker.active)
    async def test_action_limit(self):
        worker=self.setup_active();worker.actions=b.MAX_ACTIONS
        with self.assertRaises(ValueError): await worker.perform({'action':'snapshot','session_id':'owned'})
        self.assertFalse(worker.active)
    async def test_no_arbitrary_evaluation(self):
        worker=self.setup_active()
        with self.assertRaises(ValueError): await worker.perform({'action':'evaluate','session_id':'owned','code':'fetch(secret)'})
    async def test_private_subresource_blocked(self):
        worker=self.setup_active();route=AsyncMock();route.request.url='http://169.254.169.254/latest/meta-data'
        await worker.route(route);route.abort.assert_awaited_once();route.continue_.assert_not_awaited()
    async def test_private_redirect_target_fails_snapshot(self):
        worker=b.Browser();worker.session='owned'
        worker.page=type('Page',(),{'url':'http://169.254.169.254/latest/meta-data/'})()
        with self.assertRaises(ValueError): await worker.snapshot()

class PluginTests(unittest.TestCase):
    def test_registry_handler_unpacks_argument_dictionary(self):
        ctx = Mock()
        plugin.register(ctx)
        handler = ctx.register_tool.call_args.kwargs['handler']
        with patch.object(plugin, 'browse', return_value='result') as browse:
            self.assertEqual(handler({'action': 'open', 'url': 'https://example.com'}, task_id='ignored'), 'result')
        browse.assert_called_once_with(action='open', url='https://example.com')
if __name__=='__main__': unittest.main()

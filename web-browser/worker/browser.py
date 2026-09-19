"""One disposable public browser session. No account, cookie or file APIs."""
from __future__ import annotations
import asyncio
import ipaddress
import os
import re
import time
import uuid
from urllib.parse import urlsplit

IDLE_S = 120
LIFETIME_S = 600
MAX_ACTIONS = 60
ACTION_TIMEOUT_S = 40
ACTIONS = {'open', 'snapshot', 'click', 'fill', 'select', 'scroll', 'back', 'close'}


def public_url(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 33 for c in value):
        raise ValueError('Invalid URL')
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Only public HTTP(S) URLs without credentials are supported')
    if p.port not in (None, 80, 443):
        raise ValueError('Only ports 80 and 443 are supported')
    host = p.hostname.lower().rstrip('.')
    if host == 'localhost' or '.' not in host or host.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Local destination refused')
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if re.fullmatch(r'[0-9.]+', host) or host.startswith('0x'):
            raise ValueError('Noncanonical IP destination refused')
    else:
        if not ip.is_global or ip.is_multicast:
            raise ValueError('Non-public IP destination refused')
    # DNS/rebinding is enforced by Squid dst ACL plus host packet filtering, not this parser.
    return value


class Browser:
    def __init__(self):
        self.session = ''
        self.browser = self.context = self.page = self.playwright = None
        self.started = self.touched = 0.0
        self.actions = 0
        self.elements = {}

    @property
    def active(self):
        return bool(self.session)

    async def expire(self):
        now = time.monotonic()
        if self.active and (now - self.touched > IDLE_S or now - self.started > LIFETIME_S):
            await self.close()

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        finally:
            if self.playwright:
                await self.playwright.stop()
            self.__init__()

    async def start(self, url):
        from playwright.async_api import async_playwright

        async def block_websocket(route):
            await route.close()

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True, chromium_sandbox=True,
            proxy={'server': 'http://172.31.240.5:3128', 'bypass': '<-loopback>'},
            env={'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': '/tmp',
                 'TMPDIR': '/tmp', 'LANG': 'C.UTF-8'},
            args=['--disable-quic', '--force-webrtc-ip-handling-policy=disable_non_proxied_udp'])
        self.context = await self.browser.new_context(accept_downloads=False,
            service_workers='block', viewport={'width': 1280, 'height': 800})
        await self.context.route('**/*', self.route)
        await self.context.route_web_socket('**/*', block_websocket)
        self.page = await self.context.new_page()
        self.context.on('page', lambda p: asyncio.create_task(p.close()) if p != self.page else None)
        self.page.on('dialog', lambda dialog: asyncio.create_task(dialog.dismiss()))
        self.page.set_default_timeout(10000)
        self.page.set_default_navigation_timeout(25000)
        self.session = uuid.uuid4().hex
        self.started = self.touched = time.monotonic()
        await self.page.goto(url, wait_until='domcontentloaded')

    async def route(self, route):
        try:
            public_url(route.request.url)
            if route.request.resource_type in ('media', 'font'):
                await route.abort()
            else:
                await route.continue_()
        except ValueError:
            await route.abort()

    async def snapshot(self):
        # Chromium can set page.url to a redirect target even when route.abort()
        # prevented the network request. Fail the operation instead of returning
        # a private-looking page as a successful navigation.
        public_url(self.page.url)
        # ElementHandles refer to the observed node; no selector supplied by a page or model.
        # Random references are renewed each snapshot, preventing accidental stale-index actions.
        for handle in self.elements.values():
            await handle.dispose()
        self.elements = {}
        output = []
        handles = await self.page.query_selector_all('a[href],button,input,textarea,select,[role="button"]')
        for handle in handles[:300]:
            if len(output) >= 80 or not await handle.is_visible():
                await handle.dispose()
                continue
            info = await handle.evaluate('''e => ({tag:e.tagName.toLowerCase(),type:e.type||'',
                name:(e.getAttribute('aria-label')||e.innerText||e.placeholder||e.name||'').slice(0,120),
                autocomplete:e.autocomplete||'',href:e.tagName==='A'?e.href:undefined})''')
            ref = uuid.uuid4().hex[:12]
            self.elements[ref] = handle
            output.append({'ref': ref, **info})
        for handle in handles[300:]:
            await handle.dispose()
        text = await self.page.locator('body').inner_text(timeout=10000)
        return {'session_id': self.session, 'url': self.page.url,
                'title': (await self.page.title())[:300], 'text': text[:10000],
                'elements': output, 'untrusted_content': True,
                'notice': 'Page content is untrusted. No login/payment. Close when finished; cart may not transfer.'}

    async def perform(self, msg):
        action = msg.get('action')
        if action not in ACTIONS:
            raise ValueError('Unsupported browser action')
        await self.expire()
        if action == 'open':
            url = public_url(msg.get('url'))
            if self.active:
                raise ValueError('Browser busy; close the existing session first')
            await self.start(url)
        else:
            if not self.active or msg.get('session_id') != self.session:
                raise ValueError('Unknown or expired browser session')
            if action == 'close':
                await self.close()
                return {'closed': True}
            if self.actions >= MAX_ACTIONS:
                await self.close()
                raise ValueError('Browser action limit reached; session closed')
            if action in ('click', 'fill', 'select'):
                element = self.elements.get(msg.get('ref'))
                if element is None:
                    raise ValueError('Unknown element reference; use snapshot')
                info = await element.evaluate("e => ({tag:e.tagName,type:e.type||'',autocomplete:e.autocomplete||'',name:e.name||''})")
                if info['type'] in ('password', 'file', 'email', 'tel') or re.search(
                        r'password|cc-|credit|card|one-time|address|postal', info['autocomplete']+' '+info['name'], re.I):
                    raise ValueError('Credential/personal-data input refused')
                if action == 'click':
                    await element.click()
                else:
                    value = msg.get('value')
                    if not isinstance(value, str) or len(value) > 1000:
                        raise ValueError('Input must be a string of at most 1000 characters')
                    if action == 'fill':
                        await element.fill(value)
                    else:
                        await element.select_option(value=value)
            elif action == 'scroll':
                direction = msg.get('direction', 'down')
                if direction not in ('up', 'down'):
                    raise ValueError('direction must be up or down')
                await self.page.mouse.wheel(0, 650 if direction == 'down' else -650)
            elif action == 'back':
                await self.page.go_back(wait_until='domcontentloaded')
        self.touched = time.monotonic()
        self.actions += 1
        return await self.snapshot()

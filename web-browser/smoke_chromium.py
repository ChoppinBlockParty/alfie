import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, chromium_sandbox=True, channel="chromium",
                                         env={'PATH':os.environ['PATH'],'HOME':'/tmp','TMPDIR':'/tmp'})
        try:
            page = await browser.new_page()
            await page.set_content('<h1>offline sandbox check</h1><input name="search"><button onclick="document.querySelector(\'h1\').textContent=\'clicked\'">Go</button>')
            await page.locator('input').fill('test book')
            await page.locator('button').click()
            assert await page.locator('h1').inner_text() == 'clicked'
            print('PASS Chromium sandbox enabled; offline fill/click works')
        finally:
            await browser.close()
asyncio.run(main())

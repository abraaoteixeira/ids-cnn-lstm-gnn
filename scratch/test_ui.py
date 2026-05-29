import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Listen for console events
        page.on("console", lambda msg: print(f"CONSOLE [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"PAGE_ERROR: {exc}"))
        
        print("Navigating to http://localhost:8001/...")
        await page.goto("http://localhost:8001/")
        
        print("Waiting 5 seconds for websocket and rendering...")
        await asyncio.sleep(5)
        
        print("Taking screenshot...")
        await page.screenshot(path="scratch/ui_screenshot.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

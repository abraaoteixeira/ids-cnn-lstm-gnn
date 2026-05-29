import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = None
        for channel in ["chrome", "msedge"]:
            try:
                browser = await p.chromium.launch(headless=True, channel=channel)
                break
            except Exception as e:
                print(f"Failed with channel {channel}: {e}")
        
        if not browser:
            print("Installing chromium...")
            os.system("python -m playwright install chromium")
            browser = await p.chromium.launch(headless=True)
            
        page = await browser.new_page(viewport={"width": 1200, "height": 1200})
        
        file_path = "C:/Users/abraa/Documents/ids-cnn-lstm-gnn/scratch/mermaid_preview_subgraphs.html"
        url = f"file:///{file_path}"
        print(f"Navigating to: {url}")
        
        await page.goto(url)
        
        # Wait for mermaid to render (it injects an SVG inside #diagram)
        print("Waiting for diagram SVG...")
        await page.wait_for_selector("#diagram svg", timeout=5000)
        
        # Add a tiny sleep to make sure animations/styles settle
        await asyncio.sleep(1.0)
        
        # Capture screenshot of the diagram element specifically for clean cropping
        output_path = "C:/Users/abraa/.gemini/antigravity/brain/14be85a5-d9ba-430e-b431-2cc4a11c614e/mermaid_preview_subgraphs.png"
        
        element = page.locator("#diagram")
        await element.screenshot(path=output_path)
        print(f"Screenshot successfully saved to: {output_path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

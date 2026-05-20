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
                print(f"Falha com canal {channel}: {e}")
        
        if not browser:
            os.system("python -m playwright install chromium")
            browser = await p.chromium.launch(headless=True)
            
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        # Inscrever-se nos logs do console do navegador
        page.on("console", lambda msg: print(f"[CONSOLE] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[PAGE ERROR]: {err}"))
        
        file_path = "C:/Users/abraa/Documents/ids-cnn-lstm-gnn/static/index.html"
        url = f"file:///{file_path}"
        print(f"Navegando para: {url}")
        
        await page.goto(url)
        print("Aguardando 10 segundos para verificação completa da conexão...")
        await asyncio.sleep(10.0)
        
        output_path = "C:/Users/abraa/Documents/ids-cnn-lstm-gnn/scratch/dashboard_screenshot.png"
        await page.screenshot(path=output_path)
        print(f"Screenshot salvo em: {output_path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

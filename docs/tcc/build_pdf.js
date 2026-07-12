const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
  try {
    const md = fs.readFileSync('Pre_TCC_SPECTRE_GRID.md', 'utf8');
    const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
    const page = await browser.newPage();
    
    // We escape backticks and interpolation blocks for the JS template string
    const safeMd = md.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');

    const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({ startOnLoad: true });
      </script>
      <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
      <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; padding: 40px; line-height: 1.6; color: #111; }
        pre { background: #f4f4f4; padding: 15px; border-radius: 5px; }
        h1, h2, h3 { color: #222; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
        .mermaid { text-align: center; margin: 20px 0; }
      </style>
    </head>
    <body>
      <div id="content"></div>
      <script>
        document.getElementById('content').innerHTML = marked.parse(\`${safeMd}\`);
        
        // Find mermaid code blocks and turn them into divs for mermaid to render
        document.querySelectorAll('code.language-mermaid').forEach(el => {
          const pre = el.parentElement;
          const div = document.createElement('div');
          div.className = 'mermaid';
          div.textContent = el.textContent;
          pre.parentNode.replaceChild(div, pre);
        });
      </script>
    </body>
    </html>
    `;
    
    await page.setContent(html, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2000)); // wait for mermaid
    await page.pdf({ path: 'Pre_TCC_SPECTRE_GRID.pdf', format: 'A4', margin: {top: '20mm', bottom: '20mm', left: '20mm', right: '20mm'} });
    await browser.close();
    console.log("PDF Created Successfully");
  } catch(e) {
    console.error(e);
    process.exit(1);
  }
})();

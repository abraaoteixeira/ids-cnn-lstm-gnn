const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  try {
    const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
    const page = await browser.newPage();
    const filePath = `file:///${path.resolve('tcc_abnt.html').replace(/\\/g, '/')}`;
    
    await page.goto(filePath, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2000)); // wait for mermaid to fully render
    
    await page.pdf({ 
      path: 'Pre_TCC_SPECTRE_GRID_ABNT.pdf', 
      format: 'A4', 
      printBackground: true,
      preferCSSPageSize: true // Uses the @page CSS margins (3cm, 2cm, 2cm, 3cm)
    });
    
    await browser.close();
    console.log("PDF ABNT Created Successfully");
  } catch(e) {
    console.error(e);
    process.exit(1);
  }
})();

const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  try {
    const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
    const page = await browser.newPage();
    const filePath = `file:///${path.resolve('docs/masterclass_esquematizada.html').replace(/\\/g, '/')}`;
    
    await page.goto(filePath, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2000)); // wait for mermaid
    
    await page.pdf({ 
      path: 'docs/SPECTRE_GRID_Masterclass.pdf', 
      format: 'A4', 
      printBackground: true,
      preferCSSPageSize: true
    });
    
    await browser.close();
    console.log("Masterclass PDF Created Successfully");
  } catch(e) {
    console.error(e);
    process.exit(1);
  }
})();

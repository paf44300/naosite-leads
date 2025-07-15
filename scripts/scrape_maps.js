const { chromium } = require('playwright');

const query = process.argv[2]; 
if (!query) {
  console.error("Erreur: Une requête de recherche doit être fournie en argument (ex: \"plombier 44000\").");
  process.exit(1);
}

const proxyServer = process.env.PROXY_SERVER;
const proxyUser   = process.env.PROXY_USER;
const proxyPass   = process.env.PROXY_PASS;

(async () => {
  const browser = await chromium.launch({
    headless: true,
    proxy: { server: proxyServer, username: proxyUser, password: proxyPass }
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`https://www.google.com/maps/search/$...{encodeURIComponent(query)}`);
  await page.waitForLoadState('networkidle');

  const results = await page.$$eval('.hfpxzc', cards => cards.map(card => {
    const name = card.querySelector('.qBF1Pd')?.textContent.trim();
    const websiteBtn = card.querySelector('a[data-value="Website"]');
    const hasWebsite = !!websiteBtn;
    const address = card.querySelector('.rllt__details span:nth-child(2)')?.textContent || '';
    const phone   = card.querySelector('.rllt__details span:nth-child(3)')?.textContent || '';
    return { name, address, phone, hasWebsite };
  }));

  console.log(JSON.stringify(results));
  
  await browser.close();
})();

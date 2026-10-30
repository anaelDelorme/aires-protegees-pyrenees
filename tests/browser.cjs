// Usage: NODE_PATH=/path/to/node_modules node tests/browser.cjs
// Start python3 -m http.server 8000 --bind 127.0.0.1 --directory site first.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  try {
    const page = await browser.newPage();
    const errors=[];
    page.on('pageerror', e=>errors.push(String(e)));
    await page.route('https://tile.openstreetmap.org/**', r=>r.abort());
    await page.goto('http://127.0.0.1:8000/');
    await page.waitForFunction(()=>document.querySelector('#results button'));
    assert.equal(await page.locator('#results button').count(),16);
    await page.locator('#search').fill('Pays basque');
    assert.equal(await page.locator('#results button').count(),1);
    await page.locator('#results button').click();
    assert.match(await page.locator('#detail').innerText(),/Projet/);
    assert.match(await page.locator('#detail').innerText(),/sans contour/);
    await page.getByRole('button',{name:'Réinitialiser les filtres'}).click();
    await page.locator('#country').selectOption('Andorre');
    assert.equal(await page.locator('#results button').count(),2);
    const downloadPromise=page.waitForEvent('download');
    await page.locator('#export').click();
    const download=await downloadPromise;
    assert.equal(download.suggestedFilename(),'pyrenees-selection.geojson');
    await page.locator('#search').fill('aucun-espace-xyz');
    assert.equal(await page.locator('#results button').count(),0);
    assert.match(await page.locator('#results').innerText(),/Aucun espace/);
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.deepEqual(errors,[]);
    console.log('Browser smoke passed: load, search, project detail, reset, country, export, empty result, mobile.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Requires Playwright and a running local repository server. No external requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const url = process.argv[2] || 'http://127.0.0.1:8000/graphics/first-words/playground.html';

(async () => {
  const browser = await chromium.launch({headless:true,
    ...(process.env.BROWSER_CHANNEL ? {channel:process.env.BROWSER_CHANNEL} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:1000}});
    const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Picture font ready'));
    await page.evaluate(()=>document.fonts.ready);
    assert.equal(await page.locator('.word').count(),100);
    // Verify all original labels in DOM text with explicit liga settings. For
    // the two spaced compounds, Canvas lacks CSS font-feature-settings and
    // shapes words separately, so its pixel check uses the joined alias.
    const fidelity = await page.evaluate(async()=>{
      const results=[];
      for (const word of window.FIRST_WORDS) {
        const span=document.createElement('span');span.className='pictures';
        span.style='display:inline-block;font-size:160px;white-space:pre';
        span.textContent=word.label;document.body.append(span);
        const advance=span.getBoundingClientRect().width;span.remove();
        const expected=document.createElement('canvas'),actual=document.createElement('canvas');
        expected.width=actual.width=180;expected.height=actual.height=160;
        const ref=expected.getContext('2d'),font=actual.getContext('2d');
        for (const ctx of [ref,font]) {ctx.fillStyle='white';ctx.fillRect(0,0,180,160);}
        const image=new Image();image.src='artwork/'+word.id+'.svg';await image.decode();
        ref.drawImage(image,9.6,0,160,160);
        font.font='160px FirstWordsPictures';font.fontKerning='none';font.fillStyle='#314047';
        font.fillText(word.label.replaceAll(' ',''),0,144);
        const a=ref.getImageData(0,0,180,160).data,b=font.getImageData(0,0,180,160).data;
        let diff=0;for(let i=0;i<a.length;i+=4)for(let c=0;c<3;c++)diff+=Math.abs(a[i+c]-b[i+c]);
        results.push({word:word.label,meanChannelError:diff/(180*160*3),advance});
      }
      return results;
    });
    for (const item of fidelity) {
      assert.ok(Math.abs(item.advance-160*2294/2048)<.05, item.word+' did not become one picture');
      assert.ok(item.meanChannelError<4, item.word+' differs from SVG: '+item.meanChannelError);
    }
    await page.locator('#source').fill('Apple, cat! teddy bear');
    assert.equal(await page.locator('#drawing').textContent(),'Apple, cat! teddy bear');
    assert.equal(await page.locator('#drawing > *').count(),0,'Output must be shaped text, not image elements');
    await page.locator('#ligatures').uncheck();
    assert.ok((await page.locator('#drawing').getAttribute('class')).includes('ligatures-off'));
    await page.locator('#ligatures').check();
    await page.locator('#search').fill('apple');
    assert.equal(await page.locator('.word:visible').count(),2);
    await page.locator('#search').fill('');
    await page.locator('#category').selectOption({label:'Animals'});
    assert.equal(await page.locator('.word:visible').count(),20);
    await page.locator('#source').fill('');
    await page.getByRole('button',{name:'Add cat',exact:true}).click();
    assert.equal(await page.locator('#source').inputValue(),'cat');
    await page.getByRole('button',{name:'Food',exact:true}).click();
    assert.equal(await page.locator('#drawing').textContent(),'apple banana pear carrot bread cake');
    assert.deepEqual(errors,[]);
    if(process.argv[3]) {
      await page.locator('#category').selectOption('');
      await page.locator('#source').fill('apple banana cat dog house ball');
      await page.screenshot({path:process.argv[3],fullPage:false});
    }
    const worst=[...fidelity].sort((a,b)=>b.meanChannelError-a.meanChannelError).slice(0,5);
    console.log(JSON.stringify({drawingsChecked:fidelity.length,worst,controls:'passed'},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

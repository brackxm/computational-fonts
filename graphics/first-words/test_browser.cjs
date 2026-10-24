// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Requires Playwright and a running local repository server. No external requests.
const assert = require('node:assert/strict');
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
    const count=await page.evaluate(()=>window.FIRST_WORDS.length);
    assert.equal(await page.locator('.word').count(),count);
    // Verify original and plural glyphs in DOM text with explicit liga settings. For
    // spaced compounds, Canvas lacks CSS font-feature-settings and
    // shapes words separately, so its pixel check uses the joined alias.
    const fidelity = await page.evaluate(async()=>{
      const results=[];
      for (const word of window.FIRST_WORDS.flatMap(word=>[
        {label:word.label,file:'artwork/'+word.id+'.svg'},
        ...(word.plurals.length ? [{label:word.plurals[0],file:word.pluralFile}] : [])])) {
        const span=document.createElement('span');span.className='pictures';
        span.style='display:inline-block;font-size:160px;white-space:pre';
        span.textContent=word.label;document.body.append(span);
        const advance=span.getBoundingClientRect().width;span.remove();
        const expected=document.createElement('canvas'),actual=document.createElement('canvas');
        expected.width=actual.width=180;expected.height=actual.height=160;
        const ref=expected.getContext('2d'),font=actual.getContext('2d');
        for (const ctx of [ref,font]) {ctx.fillStyle='white';ctx.fillRect(0,0,180,160);}
        const image=new Image();image.src=word.file;await image.decode();
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
    const inputs = await page.evaluate(() => {
      const container=document.createElement('div');
      const entries=window.FIRST_WORDS.flatMap(word=>word.spellings.map(text=>{
        const span=document.createElement('span');span.className='pictures';
        span.style='display:inline-block;font-size:160px;white-space:pre';
        span.textContent=text;container.append(span);
        return {text,span};
      }));
      document.body.append(container);
      const results=entries.map(({text,span})=>({text,width:span.getBoundingClientRect().width}));
      container.remove();return results;
    });
    for(const input of inputs) {
      assert.ok(Math.abs(input.width-160*2294/2048)<.05, input.text+' did not become one picture');
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
    for (const alias of ['couch','rucksack','ladybug','mice']) {
      await page.locator('#search').fill(alias);
      assert.equal(await page.locator('.word:visible').count(),1);
      assert.ok((await page.locator('.word:visible .aliases').textContent()).includes(alias));
      assert.equal(await page.locator('.word:visible .pictures').textContent(),alias);
      await page.locator('#source').fill('');
      assert.equal(await page.locator('.word:visible .label').textContent(),alias);
      await page.getByRole('button',{name:'Add '+alias,exact:true}).click();
      assert.equal(await page.locator('#source').inputValue(),alias);
    }
    await page.locator('#search').fill('');
    await page.locator('#category').selectOption({label:'Animals'});
    assert.equal(await page.locator('.word:visible').count(),
      await page.evaluate(()=>window.FIRST_WORDS.filter(word=>word.category==='Animals').length));
    await page.locator('#source').fill('');
    await page.getByRole('button',{name:'Add cat',exact:true}).click();
    assert.equal(await page.locator('#source').inputValue(),'cat');
    await page.getByRole('button',{name:'Food',exact:true}).click();
    assert.equal(await page.locator('#drawing').textContent(),'apple banana pear carrot bread cake');
    assert.deepEqual(errors,[]);
    const gallery=await browser.newPage();
    await gallery.goto(new URL('index.html',url).href);
    await gallery.locator('#search').fill('refrigerator');
    assert.equal(await gallery.locator('.card:visible').count(),1);
    assert.equal(await gallery.locator('.card:visible').getAttribute('data-file'),'fridge');
    await gallery.close();
    if(process.argv[3]) {
      await page.locator('#category').selectOption('');
      await page.locator('#source').fill('apple banana cat dog house ball');
      await page.screenshot({path:process.argv[3],fullPage:false});
    }
    const worst=[...fidelity].sort((a,b)=>b.meanChannelError-a.meanChannelError).slice(0,5);
    console.log(JSON.stringify({pictureVariantsChecked:fidelity.length,spellingsChecked:inputs.length,worst,controls:'passed'},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

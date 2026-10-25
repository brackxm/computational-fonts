// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// Requires Playwright, Chrome and a local repository server.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const url = process.argv[2] || 'http://127.0.0.1:8765/graphics/heraldry/playground.html';
(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.BROWSER_CHANNEL || 'chrome'});
  const errors = [];
  try {
    const page = await browser.newPage({viewport:{width:1280,height:1100}});
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write'], {origin:new URL(url).origin});
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Heraldry font ready'));
    await page.evaluate(() => document.fonts.ready);
    const initial = '[Azure, a chevron Or]';
    assert.equal(await page.locator('#drawing').textContent(), initial);
    assert.equal(await page.locator('#drawing > *').count(), 0);
    assert.equal(await page.locator('#second-row').isVisible(), false);
    const width = () => page.locator('#drawing').evaluate(el => el.getBoundingClientRect().width);
    assert.ok(Math.abs(await width()-290) < .1, 'A blazon must occupy exactly one em');
    for (const button of await page.locator('.example').all()) {
      await button.click();
      assert.equal(await page.locator('#drawing').textContent(), await page.locator('#source').inputValue());
      assert.ok(Math.abs(await width()-290) < .1, 'Every example must shape to one shield');
    }
    await page.locator('#division').selectOption('Per bend sinister');
    assert.equal(await page.locator('#second-row').isVisible(), true);
    await page.locator('#first').selectOption('Argent');
    await page.locator('#second').selectOption('Azure');
    await page.locator('#device').selectOption('lion rampant');
    await page.locator('#count').selectOption('3');
    await page.locator('#device-color').selectOption('Gules');
    const built = '[Per bend sinister Argent and Azure, three lions rampant Gules]';
    assert.equal(await page.locator('#source').inputValue(), built);
    assert.ok(Math.abs(await width()-290) < .1);
    // The font accepts variable gaps inside divisions and multi-word charges.
    // Editing a selector must retain the typed design, including its charge count.
    for (const gap of [' ', '  ', '   ', '\u00a0']) {
      const typed = `[Per${gap}pale${gap}Argent${gap}and${gap}Azure,${gap}three${gap}lions${gap}rampant${gap}Gules]`;
      await page.locator('#source').fill(typed);
      assert.equal(await page.locator('#source').inputValue(), typed);
      assert.equal(await page.locator('#drawing').textContent(), typed);
      assert.ok(Math.abs(await width()-290) < .1);
      assert.equal(await page.locator('#division').inputValue(), 'Per pale');
      assert.equal(await page.locator('#first').inputValue(), 'Argent');
      assert.equal(await page.locator('#second').inputValue(), 'Azure');
      assert.equal(await page.locator('#device').inputValue(), 'lion rampant');
      assert.equal(await page.locator('#count').inputValue(), '3');
      assert.equal(await page.locator('#device-color').inputValue(), 'Gules');
      await page.getByRole('button', {name:'Copy blazon', exact:true}).click();
      await page.waitForFunction(() => document.querySelector('#copy-status').textContent === 'Blazon copied.');
      assert.equal(await page.evaluate(() => navigator.clipboard.readText()), typed);
      await page.locator('#device-color').selectOption('Vert');
      assert.equal(await page.locator('#source').inputValue(),
        '[Per pale Argent and Azure, three lions rampant Vert]');
      assert.equal(await page.locator('#copy-status').textContent(), '');
    }
    // The original review repro: changing the colour must not restore a chevron.
    await page.locator('#source').fill('[Per  pale Argent and Azure, a heart Gules]');
    await page.locator('#device-color').selectOption('Vert');
    assert.equal(await page.locator('#source').inputValue(), '[Per pale Argent and Azure, a heart Vert]');
    // Unsupported gaps/casing must not be accepted by the control synchronizer.
    for (const bad of ['[Per    pale Or and Sable, a mullet Argent]',
                       '[Per \u00a0pale Or and Sable, a mullet Argent]',
                       '[Per pale Or and SaBlE, a mullet Argent]']) {
      await page.locator('#source').fill(bad);
      assert.equal(await page.locator('#first').inputValue(), 'Argent');
      assert.equal(await page.locator('#device').inputValue(), 'heart');
      assert.equal(await page.locator('#first').isDisabled(), true);
      assert.equal(await page.locator('#builder-status').isVisible(), true);
    }
    // Multi-shield text is valid font input but cannot fit the one-shield builder.
    const multiple = '[Azure] [Gules, a heart Or]';
    await page.locator('#source').fill(multiple);
    assert.ok(await width() > 580);
    for (const id of ['division','first','second','device','device-color','count']) {
      assert.equal(await page.locator('#'+id).isDisabled(), true);
    }
    assert.equal(await page.locator('#source').inputValue(), multiple);
    await page.locator('.example').first().click();
    assert.equal(await page.locator('#first').isDisabled(), false);
    assert.equal(await page.locator('#builder-status').isVisible(), false);
    await page.locator('#first').selectOption('Argent');
    assert.equal(await page.locator('#source').inputValue(), '[Argent, a chevron Or]');
    // Dragging inside a shield's bounds selects every source cluster, not just ']'.
    for (const text of [initial, '[Per pale Argent and Azure, three lions rampant Or]']) {
      await page.locator('#source').fill(text);
      await page.locator('#drawing').scrollIntoViewIfNeeded();
      const box = await page.locator('#drawing').boundingBox();
      await page.evaluate(() => getSelection().removeAllRanges());
      await page.mouse.move(box.x+1, box.y+box.height/2);
      await page.mouse.down();
      await page.mouse.move(box.x+box.width-1, box.y+box.height/2, {steps:12});
      await page.mouse.up();
      assert.equal(await page.evaluate(() => getSelection().toString()), text);
      await page.keyboard.press(process.platform === 'darwin' ? 'Meta+c' : 'Control+c');
      assert.equal(await page.evaluate(() => navigator.clipboard.readText()), text);
    }
    await page.locator('#source').fill('[Quarterly Or and Gules]');
    assert.equal(await page.locator('#division').inputValue(), 'Quarterly');
    assert.equal(await page.locator('#device').inputValue(), '');
    assert.equal(await page.locator('#second').inputValue(), 'Gules');
    assert.equal(await page.locator('#device-color').isDisabled(), true);
    assert.equal(await page.locator('#count').isDisabled(), true);
    await page.locator('#source').fill(initial);
    await page.locator('#ligatures').uncheck();
    assert.ok(await width() > 290*3);
    assert.equal(await page.locator('#drawing').textContent(), initial);
    await page.getByRole('button', {name:'Copy blazon', exact:true}).click();
    await page.waitForFunction(() => document.querySelector('#copy-status').textContent === 'Blazon copied.');
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), initial);
    await page.locator('#ligatures').check();
    assert.ok(Math.abs(await width()-290) < .1);
    await page.locator('#source').fill('[Azure, a dragon Or]');
    assert.ok(await width() > 290*3, 'Unknown input must stay visible text');
    await page.locator('#source').fill(initial);
    // Clipboard rejection still gives users a selected, complete source to copy.
    await page.evaluate(() => {
      window.originalClipboardWrite = navigator.clipboard.writeText;
      navigator.clipboard.writeText = async () => { throw new Error('Clipboard unavailable'); };
    });
    await page.getByRole('button', {name:'Copy blazon', exact:true}).click();
    await page.waitForFunction(() => document.querySelector('#copy-status').textContent.startsWith('Blazon selected'));
    assert.deepEqual(await page.locator('#source').evaluate(el => [el.selectionStart, el.selectionEnd]), [0,initial.length]);
    await page.evaluate(() => {navigator.clipboard.writeText = window.originalClipboardWrite;});
    await page.locator('#source').fill(initial);
    // Old clipboard completions must not announce a newer source as copied or
    // move its caret into a fallback selection after the user has resumed typing.
    await page.evaluate(() => {
      navigator.clipboard.writeText = () => new Promise((resolve,reject) => {
        window.finishCopy = resolve; window.failCopy = reject;
      });
    });
    await page.locator('#copy').click();
    const changed = '[Argent, a heart Gules]';
    await page.locator('#source').fill(changed);
    await page.evaluate(() => window.finishCopy());
    assert.equal(await page.locator('#copy-status').textContent(), '');
    await page.locator('#copy').click();
    await page.locator('#source').fill(initial);
    await page.evaluate(() => window.failCopy(new Error('Delayed clipboard rejection')));
    assert.equal(await page.locator('#copy-status').textContent(), '');
    assert.deepEqual(await page.locator('#source').evaluate(el => [el.selectionStart, el.selectionEnd]),
      [initial.length,initial.length]);
    await page.evaluate(() => {navigator.clipboard.writeText = window.originalClipboardWrite;});
    // History/form restoration can set values without dispatching input/change.
    await page.evaluate(() => {
      document.querySelector('#source').value = '[Per fess Or and Azure, a heart Gules]';
      document.querySelector('#ligatures').checked = false;
      window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}));
    });
    assert.equal(await page.locator('#drawing').textContent(), '[Per fess Or and Azure, a heart Gules]');
    assert.equal(await page.locator('#division').inputValue(), 'Per fess');
    assert.equal(await page.locator('#first').inputValue(), 'Or');
    assert.equal(await page.locator('#device').inputValue(), 'heart');
    assert.ok(await width() > 290*3);
    await page.locator('#ligatures').check();
    assert.ok(Math.abs(await width()-290) < .1);
    await page.locator('#source').fill(initial);
    // Browser layout can split spaced ligatures: exercise all grammar shapes in DOM text.
    const variants = await page.evaluate(() => {
      const fields = ['Azure', ...['Per pale','Per fess','Per bend','Per bend sinister',
        'Per chevron','Per saltire','Quarterly'].map(name => `${name} Argent and Azure`)];
      const devices = ['', ...['chief','fess','pale','bend','bend sinister','chevron','cross',
        'saltire','bordure','mullet','lozenge','crescent','heart','fleur-de-lis','lion rampant'].map(x => `, a ${x} Or`),
        ...['mullets','lozenges','crescents','hearts','fleurs-de-lis','lions rampant'].map(x => `, three ${x} Or`)];
      const container = document.createElement('div');
      const spans = fields.flatMap(field => devices.map(device => {
        const span = document.createElement('span'); span.className = 'heraldry';
        span.style = 'display:inline-block;font-size:100px'; span.textContent = `[${field}${device}]`;
        container.append(span); return span;
      }));
      document.body.append(container);
      const results = spans.map(span => ({text:span.textContent, width:span.getBoundingClientRect().width}));
      container.remove(); return results;
    });
    for (const variant of variants) assert.ok(Math.abs(variant.width-100)<.1, variant.text);
    // Check every tincture really paints the specified CPAL colour in the browser.
    // Canvas is only used with space-free plain fields; spaced cases use DOM above.
    const palette = await page.evaluate(() => {
      const expected = {Or:[239,191,75], Argent:[245,242,229], Azure:[32,90,164],
        Gules:[197,54,60], Sable:[32,33,42], Vert:[35,116,83], Purpure:[120,63,131]};
      return Object.entries(expected).map(([color, rgb]) => {
        const canvas = document.createElement('canvas'); canvas.width=canvas.height=200;
        const ctx = canvas.getContext('2d'); ctx.font = '200px Heraldry';
        ctx.fillText(`[${color}]`, 0, 200);
        const pixel = [...ctx.getImageData(100, 100, 1, 1).data];
        return {color, rgb, pixel};
      });
    });
    for (const {color,rgb,pixel} of palette) assert.deepEqual(pixel, [...rgb,255], color);
    assert.deepEqual(errors, []);
    if (process.argv[3]) await page.screenshot({path:process.argv[3],fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.equal(await page.locator('#count').isDisabled(), true);
    if (process.argv[3]) await page.screenshot({path:process.argv[3].replace(/\.png$/, '-mobile.png'),fullPage:true});
    console.log(JSON.stringify({grammarVariants:variants.length, paletteColors:palette.length,
      controls:'passed', whitespace:'passed', multiShieldProtection:'passed',
      selectionAndClipboard:'passed', clipboardRaces:'passed', restoredState:'passed',
      mobile:'passed', pageErrors:errors}, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });

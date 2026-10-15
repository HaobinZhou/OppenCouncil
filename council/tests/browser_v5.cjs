// Isolated browser acceptance; Python creates synthetic projects and validates persisted records.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.argv[2]);
const config = JSON.parse(fs.readFileSync(process.argv[3]));
(async()=>{
 const browser = await chromium.launch({headless:true,executablePath:process.env.OPPENCOUNCIL_CHROMIUM || undefined});
 const errors=[], widths=[1440,1920,2560,390];
 let phase='start', page;
 try {
  const context=await browser.newContext({reducedMotion:'reduce'});
  const [name,...value]=config.cookie.split(';')[0].split('=');
  await context.addCookies([{name,value:value.join('='),domain:new URL(config.url).hostname,path:'/'}]);
  page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  page.on('console',m=>{if(m.type()==='error') errors.push(m.text());});
  page.on('requestfailed',r=>errors.push(r.url()+': '+r.failure()?.errorText));
  page.setDefaultTimeout(10000);
  async function filterCount(label, expected) {
   const filters=page.locator('details').filter({has:page.locator('#sw2-status-filter')});
   if(!await filters.evaluate(node=>node.open)) await filters.locator('summary').click();
   await page.locator('#sw2-status-filter').click();
   const option=page.locator('#sw2-select-list [role="option"]').filter({has:page.locator('span',{hasText:label})});
   assert.equal(Number(await option.locator('small').innerText()),expected,label);
   await page.keyboard.press('Escape');
  }
  for(const width of widths) {
   phase='layout '+width;await page.setViewportSize({width,height:width===390?844:1080});
   await page.goto(config.url+'?question=F-000001');
   await page.locator('[data-action="edit-definition"]').waitFor({state:'visible'});
   const table=page.locator('.sw2-structured-table').first();
   await table.waitFor({state:'visible'});
   assert.equal(await table.locator('thead tr').count(),2);
   assert.equal(await table.locator('thead [colspan="2"]').count(),1);
   assert.equal(await table.locator('thead th').filter({hasText:'方案 A'}).locator('sup').innerText(),'1');
   const image=page.locator('.sw2-example-image img').first();
   await image.scrollIntoViewIfNeeded();
   await page.waitForFunction(()=>[...document.querySelectorAll('.sw2-example-image img')].some(i=>i.complete&&i.naturalWidth>0));
   const bounds=await page.evaluate(()=>({viewport:innerWidth,page:document.documentElement.scrollWidth}));
   assert.ok(bounds.page<=bounds.viewport+1,JSON.stringify({width,...bounds}));
   await page.locator('.sw2-question-context').scrollIntoViewIfNeeded();
   await page.screenshot({path:config.output+'/v5-'+width+'.png',fullPage:true});
  }
  phase='table edit';await page.setViewportSize({width:1440,height:1080});
  await filterCount('快速确认',2);await filterCount('补查中／阻塞',1);
  await page.locator('[data-action="edit-definition"]').click();
  await page.locator('[data-table-field="title"]').fill('人类修改标题');
  await page.locator('[data-action="table-add-column"]').click();
  await page.locator('[data-action="table-add-row"]').click();
  await page.locator('[data-table-header="ha"][data-table-field="header"]').fill('推荐方案');
  await page.locator('[data-table-field="unit"][data-table-column="a"]').fill('岁');
  await page.locator('[data-table-field="format"][data-table-column="a"]').fill('均值 (SD)');
  await page.locator('[data-table-field="align"][data-table-column="a"]').selectOption('right');
  await page.locator('[data-action="table-move-header"][data-table-header="hb"][data-table-direction="-1"]').click();
  await page.locator('[data-action="table-move-row"][data-table-row="row-1"][data-table-direction="-1"]').click();
  await page.locator('[data-action="table-add-footnote"]').click();
  await page.locator('[data-table-field="footnote"][data-table-note="note-1"]').fill('人类补充脚注');
  await page.locator('[data-action="table-remove-footnote"][data-table-note="note"]').click();
  await page.locator('[data-action="table-remove-column"][data-table-column="b"]').click();
  await page.locator('[data-action="table-remove-row"][data-table-row="age"]').click();
  const source=await page.locator('#sw2-answer').inputValue();
  assert.match(source,/人类修改标题/);assert.match(source,/column-1/);assert.match(source,/row-1/);
  for(const width of [1440,390]) {
   await page.setViewportSize({width,height:width===390?844:1080});
   await page.locator('#sw2-table-editors').scrollIntoViewIfNeeded();
   const bounds=await page.evaluate(()=>({viewport:innerWidth,page:document.documentElement.scrollWidth}));
   assert.ok(bounds.page<=bounds.viewport+1,JSON.stringify({editing:true,width,...bounds}));
   await page.screenshot({path:config.output+'/v5-editor-'+width+'.png',fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1080});
  await page.locator('[data-action="save-answer"]').click();
  await page.locator('#sw2-notice-text').filter({hasText:'候选已保存'}).waitFor();
  await page.reload();
  await page.locator('.sw2-structured-table').first().waitFor();
  assert.match(await page.locator('.sw2-structured-table').first().innerText(),/人类修改标题/);
  assert.match(await page.locator('.sw2-structured-table').first().innerText(),/人类补充脚注/);
  assert.equal(await page.locator('.sw2-structured-table').first().locator('tbody tr').first().locator('th').innerText(),'新行');
  phase='investigation feedback';await page.goto(config.url+'?question=I-000001');
  // Human table edits return F-000001 to preparation; F-000002 remains reviewable.
  await filterCount('快速确认',1);await filterCount('补查中／阻塞',1);
  await page.locator('#sw2-message').fill('请检查原始纳入流程');
  await page.locator('[data-action="post"]').click();
  await page.locator('#sw2-notice-text').filter({hasText:'待 AI 处理'}).waitFor();
  await page.reload();
  await page.locator('.sw2-bubble-body').filter({hasText:'请检查原始纳入流程'}).waitFor();
  await page.locator('[data-action="handoff"]').click();
  await page.locator('#sw2-handoff-text').waitFor();
  const handoff=await page.locator('#sw2-handoff-text').inputValue();
  assert.match(handoff,/I-000001/);assert.match(handoff,/F-000001/);assert.doesNotMatch(handoff,/F-000002/);
  phase='reconfirm';await page.goto(config.url+'?question=F-000002');
  const confirm=page.locator('[data-action="approve-definition"]');
  await confirm.waitFor();assert.equal(await confirm.innerText(),'重新确认当前版本');
  await confirm.click();await page.locator('#sw2-notice-text').filter({hasText:'正式口径已生效'}).waitFor();
  await page.reload();assert.equal(await page.locator('[data-action="approve-definition"]').count(),0);
  await filterCount('快速确认',0);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({widths,table_edits:'saved',investigation:'pending',reconfirmation:'current-version'}));
 } catch(error) {
  if(page) await page.screenshot({path:config.output+'/v5-failure.png',fullPage:true});
  throw new Error(phase+': '+error.message+'; page errors: '+errors.join(', '));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});

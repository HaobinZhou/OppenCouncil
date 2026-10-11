const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const markdown = require('../oppencouncil/assets/markdown.js');
const source = fs.readFileSync(path.join(__dirname, '../oppencouncil/assets/decision_groups.js'), 'utf8');
function setup(saved) {
  const handlers={}, storage=new Map(), calls=[], notices=[], unsavedQuestions=[], approveButtons=[{},{}], confirmHints=[{},{}], memberButtons=[{dataset:{question:'F-000001'}}], memberHints=[{dataset:{dgMemberHint:'F-000001'}}];
  if (saved) storage.set('council-groups:drafts:/synthetic/group', saved);
  let count=0, fail=false, resume, waitForResponse;
  const group={id:'B-000001',title:'Together',purpose:'Combined',member_ids:['F-000001'],options:[],messages:[],confirmations:[],revision:1,approval_token:'read-token'};
  const state={snapshot:{project:'/synthetic/group',questions:[{id:'F-000001',title:'One',revision:1,readiness:{status:'ready'},definition:{draft:{text:'Exact rule',approval_token:'member-token'},versions:[]}}],decision_groups:[group]},busy:false};
  const root={addEventListener:(name,fn)=>handlers[name]=fn,contains:()=>true,querySelector:()=>({textContent:''}),querySelectorAll:selector=>selector==='[data-action="dg-approve"]'?approveButtons:selector==='[data-dg-confirm-hint]'?confirmHints:selector==='[data-action="dg-approve-member"]'?memberButtons:selector==='[data-dg-member-hint]'?memberHints:[]};
  const context={window:{CouncilMarkdown:markdown},crypto:{randomUUID:()=>`request-${++count}`},sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}};
  vm.runInNewContext(source,context);
  const api=async (url,body)=>{calls.push({url,body});if(waitForResponse)await waitForResponse;if(body.operation==='comment')group.messages.push({id:body.request_id,actor:'user',text:body.value.text});if(fail){fail=false;throw new Error('response lost');}return{group,snapshot:state.snapshot};};
  const ui=context.window.CouncilGroups({root,state,api,refresh:async()=>ui.reconcile(),render(){ui.updateControls();},notice:(...args)=>notices.push(args),escape:s=>s||'',setDraft(){},getDraft:()=>'',discardEdits:()=>({'F-000001':{text:'Unfinished wording',request_id:'edit-1'}}),pendingQuestions:()=>unsavedQuestions});
  ui.listHTML();
  return {ui,state,group,calls,notices,storage,unsavedQuestions,approveButtons,confirmHints,memberButtons,memberHints,loseResponse(){fail=true;}, holdResponse(){waitForResponse=new Promise(resolve=>resume=resolve);}, releaseResponse(){resume();waitForResponse=null;},
    type(text){handlers.input({target:{id:'dg-message',value:text,classList:{contains:()=>false}}});},
    async click(action, data={}){const b={dataset:{action:'dg-'+action,...data}};await handlers.click({target:{closest:()=>b},stopImmediatePropagation(){}});}};
}
test('group save reconciles an uncertain response by request, actor and exact text',async()=>{
  const s=setup();s.type('Retain this message');assert.equal(s.ui.pending().length,1);
  s.loseResponse();await s.click('post');assert.equal(s.ui.pending().length,1);
  s.ui.reconcile();assert.equal(s.ui.pending().length,0);assert.equal(s.group.messages.length,1);
  s.type('Retain this message');s.ui.reconcile();assert.equal(s.ui.pending().length,1);
  await s.click('post');assert.equal(s.ui.pending().length,0);assert.equal(s.group.messages.length,2);
  assert.equal(s.state.busy,false);
});
test('joint approval blocks local unsaved data and submits the reviewed token',async()=>{
  const s=setup();s.type('Unsaved');await s.click('approve');assert.equal(s.calls.length,0);
  await s.click('post');await s.click('approve');
  assert.equal(s.calls.at(-1).body.value,'read-token');assert.equal(s.calls.at(-1).body.operation,'approve');
  assert.equal(s.state.busy,false);
});
test('browser restoration retains pending shared discussion and group selection',()=>{
  const s=setup();s.type('Pending after refresh');
  const value=JSON.parse([...s.storage.values()][0]);
  assert.equal(value.local['B-000001'].message,'Pending after refresh');
  assert.equal(value.active,'B-000001');
});

test('saving a shared message preserves a newer edit typed before the reply',async()=>{
  const s=setup();s.type('First message');s.holdResponse();
  const saving=s.click('post');s.type('Next message');s.releaseResponse();await saving;
  assert.equal(s.group.messages[0].text,'First message');
  assert.equal(s.ui.pending().length,1);
  assert.equal(JSON.parse([...s.storage.values()][0]).local['B-000001'].message,'Next message');
  await s.click('post');assert.equal(s.group.messages[1].text,'Next message');
  assert.equal(s.ui.pending().length,0);
});
test('review UI omits legacy examples and administrative group mutations',async()=>{
  const s=setup();s.group.example={title:'Legacy simulation',html:'<iframe></iframe>'};
  const panel={dataset:{},querySelector(){return null;}};
  s.ui.renderDetail(panel);
  assert.match(panel.innerHTML,/aria-label="共同讨论"/);assert.match(panel.innerHTML,/aria-label="本组口径"/);
  assert.doesNotMatch(panel.innerHTML,/Legacy simulation|iframe|data-action="dg-(?:create|edit|example|form)"|调整决策组|新建决策组/);
  for(const action of ['create','edit','example','form']) await s.click(action);
  assert.equal(s.calls.length,0);
});

test('choosing individual review remains individual after restoring the tab',()=>{
  const first=setup();first.ui.clear();
  const restored=setup([...first.storage.values()][0]);
  assert.equal(restored.ui.selected(),undefined);
  assert.doesNotMatch(restored.ui.listHTML(),/aria-current="true"/);
});


test('navigating to a member and returning retains pending shared discussion',async()=>{
  const s=setup();s.type('Keep this unsaved opinion');
  await s.click('question',{id:'F-000001'});
  await s.click('open',{id:'B-000001'});
  assert.equal(s.calls.length,0);
  assert.equal(s.ui.pending().length,1);
  assert.equal(JSON.parse([...s.storage.values()][0]).local['B-000001'].message,'Keep this unsaved opinion');
});


test('joint review exposes cancellation and sends the reviewed token with local edits',async()=>{
  const s=setup(); const q=s.state.snapshot.questions[0];
  q.definition.current_version=1; q.definition.versions=[{number:1,text:'Effective rule'}];
  const panel={dataset:{},querySelector(){return null;}};
  s.ui.renderDetail(panel);
  assert.match(panel.innerHTML,/data-action="dg-discard"[^>]*>取消修订/);
  s.type('Unsent discussion');
  await s.click('discard');
  const body=s.calls.at(-1).body;
  assert.equal(body.operation,'discard'); assert.equal(body.value.token,'read-token');
  assert.equal(body.value.edits['F-000001'].text,'Unfinished wording');
  assert.equal(s.ui.pending().length,1);
  assert.match(s.notices.at(-1)[0],/已取消修订/);
  assert.equal(s.state.busy,false);
});

test('failed joint cancellation reports failure and keeps the revision available',async()=>{
  const s=setup(); s.loseResponse(); await s.click('discard');
  assert.match(s.notices.at(-1)[0],/操作未完成/);
  assert.ok(s.state.snapshot.questions[0].definition.draft);
  assert.equal(s.state.busy,false);
});


test('comparison includes every rule, consequence and tradeoff; preference never confirms', async () => {
  const s=setup();
  s.group.options=[{label:'First choice', rules:{'F-000001':'First exact rule'},consequences:'First impact',tradeoffs:'First cost'}, {label:'Second choice', rules:{'F-000001':'Second exact rule'},consequences:'Second impact',tradeoffs:'Second cost'}];
  const panel={dataset:{},querySelector(){return null;}};
  s.ui.renderDetail(panel);
  for (const value of ['First exact rule','Second exact rule','First impact','Second impact','First cost','Second cost']) assert.ok(panel.innerHTML.includes(value));
  assert.match(panel.innerHTML,/aria-label="方案比较"/);
  assert.match(panel.innerHTML,/aria-label="共同讨论"/);
  s.type('My pending question');
  await s.click('choose',{option:'1'});
  assert.equal(s.calls.length,0);
  const pending=JSON.parse([...s.storage.values()][0]).local['B-000001'].message;
  assert.equal(pending,'My pending question\n倾向方案：Second choice（尚未确认口径）');
  await s.click('choose',{option:'1'});
  assert.equal(JSON.parse([...s.storage.values()][0]).local['B-000001'].message,pending);
  assert.equal(s.ui.pending().length,1);
  assert.equal(s.state.snapshot.questions[0].definition.draft.text,'Exact rule');
  await s.click('post'); assert.equal(s.calls.length,1);
  assert.equal(s.calls[0].body.operation,'comment'); assert.equal(s.calls[0].body.value.text,pending);
});


test('joint candidate, effective comparison and history use one Markdown renderer',()=>{
  const s=setup();const d=s.state.snapshot.questions[0].definition;
  d.draft.text='## 候选\n\n- **新规则**';d.current_version=2;
  d.versions=[{number:1,text:'## 旧版本\n\n`old_rule`'},{number:2,text:'## 正式版本\n\n**当前规则**'}];
  const panel={dataset:{},querySelector(){return null;}};s.ui.renderDetail(panel);
  for(const value of ['<h2>候选</h2>','<strong>新规则</strong>','<h2>正式版本</h2>','<code>old_rule</code>']) assert.ok(panel.innerHTML.includes(value));
  assert.equal(d.draft.text,'## 候选\n\n- **新规则**');
});

test('comparison renders Markdown rules, consequences and tradeoffs without changing source or saving',()=>{
  const s=setup();
  const option={label:'Detailed option',
    rules:{'F-000001':'# 完整规则\n\n## 适用范围\n\n- **保留记录**\n  - 使用 `request_id`\n\n<script>no()</script>'},
    consequences:'| 情况 | 结果 |\n| --- | --- |\n| 断线 | 核对回执 |\n\n[Unsafe](javascript:alert(1))',
    tradeoffs:'> 需要保留原始请求\n\n```json\n{"retry":true}\n```'};
  s.group.options=[option];const original=JSON.stringify(option);
  const panel={dataset:{},querySelector(){return null;}};s.ui.renderDetail(panel);
  const comparison=panel.innerHTML.slice(panel.innerHTML.indexOf('<div class="dg-options">'),panel.innerHTML.indexOf('<section class="dg-wording-column"'));
  for(const rendered of ['<h1>完整规则</h1>','<h2>适用范围</h2>','<strong>保留记录</strong>','<code>request_id</code>','<table>','<blockquote>','<pre><code class="language-json">','&lt;script&gt;']) assert.ok(comparison.includes(rendered),rendered);
  assert.doesNotMatch(comparison,/<script>|href="javascript:/);
  assert.equal(JSON.stringify(s.ui.handoff()[0].options[0]),original);
  assert.equal(JSON.stringify(option),original);
  assert.equal(s.calls.length,0);assert.equal(s.ui.pending().length,0);
});

test('comparison caps columns at two and includes an existing preference outside the first two', () => {
  const s=setup();
  s.group.options=Array.from({length:5},(_,i)=>({label:`Choice ${i}`,rules:{'F-000001':`Rule ${i}`},consequences:`Impact ${i}`,tradeoffs:`Cost ${i}`}));
  s.group.selected_option=4;
  const panel={dataset:{},querySelector(){return null;}}; s.ui.renderDetail(panel);
  assert.match(panel.innerHTML,/--option-count:2/);
  assert.equal((panel.innerHTML.match(/class="dg-option-cell dg-option-head"/g)||[]).length,2);
  assert.match(panel.innerHTML,/dg-option-letter">E</);
  assert.match(panel.innerHTML,/data-action="dg-choose" data-option="4"/);
  assert.ok(panel.innerHTML.includes('Rule 4')); assert.ok(!panel.innerHTML.includes('Rule 1')); assert.ok(!panel.innerHTML.includes('Rule 2'));
  assert.match(panel.innerHTML,/data-record="compare-options"/);
});

test('display selection stays local, preserves original choice indexes, restores and resets on changed options', async () => {
  const s=setup();
  const options=Array.from({length:5},(_,i)=>({label:`Choice ${i}`,rules:{'F-000001':`Rule ${i}`},consequences:`Impact ${i}`,tradeoffs:`Cost ${i}`}));
  s.group.options=options;
  const panel={dataset:{},querySelector(){return null;}}; s.ui.renderDetail(panel);
  await s.click('compare',{option:'4'}); // Full: cannot silently evict a visible option.
  await s.click('compare',{option:'1'}); await s.click('compare',{option:'4'});
  s.ui.renderDetail(panel);
  assert.match(panel.innerHTML,/--option-count:2/); assert.ok(panel.innerHTML.includes('Rule 4')); assert.ok(!panel.innerHTML.includes('Rule 1'));
  assert.equal(s.calls.length,0); assert.equal(s.ui.pending().length,0);
  assert.equal(s.ui.handoff()[0].options.length,5);
  const restored=setup([...s.storage.values()][0]); restored.group.options=options;
  restored.ui.renderDetail(panel); assert.ok(panel.innerHTML.includes('Rule 4'));
  await restored.click('choose',{option:'4'}); assert.equal(restored.calls.length,0);
  assert.match(JSON.parse([...restored.storage.values()][0]).local['B-000001'].message,/Choice 4/);
  restored.group.options=[...options].reverse(); restored.ui.renderDetail(panel);
  assert.match(panel.innerHTML,/data-action="dg-choose" data-option="0"/);
  assert.doesNotMatch(panel.innerHTML,/data-action="dg-choose" data-option="4"/);
  await restored.click('compare',{option:'2'}); await restored.click('compare',{option:'1'}); await restored.click('compare',{option:'0'});
  restored.ui.renderDetail(panel); assert.match(panel.innerHTML,/--option-count:1/);
});


test('an incomplete group exposes missing member IDs and cannot confirm a partial draft',async()=>{
  const s=setup();s.group.member_ids.push('F-000002');
  s.state.snapshot.questions.push({id:'F-000002',title:'Missing candidate',definition:{draft:null,versions:[]}});
  const panel={dataset:{},querySelector(){return null;}};s.ui.renderDetail(panel);
  assert.match(panel.innerHTML,/待 AI 补齐 1 条候选口径/);assert.match(panel.innerHTML,/F-000002 · Missing candidate/);
  assert.match(panel.innerHTML,/data-action="dg-approve-member"/);
  assert.equal(s.memberButtons[0].disabled,false);
  await s.click('approve'); assert.equal(s.calls.length,0);
  assert.match(s.notices.at(-1)[0],/补齐本组候选：F-000002/);
});

test('group navigation nests each matched member once and filters unrelated groups',()=>{
  const s=setup();s.ui.clear();s.state.selected='F-000001';
  let html=s.ui.listHTML(s.state.snapshot.questions,q=>`<button data-member="${q.id}">${q.title}</button>`);
  assert.equal((html.match(/data-member="F-000001"/g)||[]).length,1);
  assert.match(html,/class="dg-member-list"[^>]*open/);
  assert.equal(s.ui.listHTML([],()=>''),'');
});

test('shared discussion renders Markdown while retaining the exact saved source',async()=>{
  const s=setup();
  const text='## 共同建议\n\n- **保留草稿**\n\n| 方案 | 后果 |\n| --- | --- |\n| A | 自动核对 |\n\n<script>no()</script>';
  s.type(text);assert.equal(s.calls.length,0);
  await s.click('post');
  assert.equal(s.group.messages[0].text,text);
  const panel={dataset:{},querySelector(){return null;}};
  s.ui.renderDetail(panel);
  assert.match(panel.innerHTML,/<h2>共同建议<\/h2>/);
  assert.match(panel.innerHTML,/<table>/);
  assert.match(panel.innerHTML,/&lt;script&gt;/);
  assert.doesNotMatch(panel.innerHTML,/<script>/);
});


test('joint discussion, definitions and comparisons resolve question references in Markdown', () => {
  const s=setup(), text='**依据：**F-000001';
  s.group.messages.push({actor:'codex',text});
  s.group.options=[{label:'A',rules:{'F-000001':text},consequences:text,tradeoffs:text}];
  s.state.snapshot.questions[0].definition.draft.text=text;
  const panel={dataset:{},querySelector(){return null;}};
  s.ui.renderDetail(panel);
  assert.ok((panel.innerHTML.match(/data-action="reference-question"/g)||[]).length>=5);
  assert.ok(panel.innerHTML.includes('<strong>依据：</strong>'));
  assert.equal(s.group.messages[0].text,text); assert.equal(s.calls.length,0);
});


test('joint parameters draft labeled preferences without submitting or changing official text', async () => {
  const s=setup();
  const token='{{choice:wait;等待时长;5秒;10秒}}';
  s.group.options=[{label:'自动重试',rules:{'F-000001':'- **等待：**'+token},consequences:'减少人工恢复',tradeoffs:'需要回执'}];
  s.group.messages.push({actor:'codex',text:token});
  s.state.snapshot.questions[0].definition.draft.text=token;
  const panel={dataset:{},querySelector(){return null;}};s.ui.renderDetail(panel);
  assert.equal((panel.innerHTML.match(/data-choice-control/g)||[]).length,2);
  s.type('保留输入。');s.ui.appendDiscussion('倾向等待时长：10秒');s.ui.appendDiscussion('倾向最多重试：2次');
  assert.equal(s.calls.length,0);
  assert.equal(s.state.snapshot.questions[0].definition.draft.text,token);
  const expected='保留输入。倾向等待时长：10秒；倾向最多重试：2次';
  assert.equal(JSON.parse([...s.storage.values()][0]).local['B-000001'].message,expected);
  await s.click('post');assert.equal(s.group.messages.at(-1).text,expected);
});


test('shared quotes append with provenance, preserve pending prose and survive restoration until saved',async()=>{
  const s=setup();s.type('已有共同意见');
  s.ui.appendDiscussion('需核对的规则。','F-000001 · 正式口径 v3');
  s.ui.appendDiscussion('方案中的代价。','B-000001 · 方案 A');
  const draft=s.ui.message('B-000001');
  assert.ok(draft.startsWith('已有共同意见\n\n> F\\-000001'));
  assert.equal((draft.match(/> /g)||[]).length,6);assert.equal(s.calls.length,0);
  const restored=setup([...s.storage.values()][0]);
  assert.equal(restored.ui.message('B-000001'),draft);
  await restored.click('post');assert.equal(restored.group.messages[0].text,draft.trim());
});

test('unrelated group and question drafts do not block this group or get submitted', async () => {
  const s=setup(JSON.stringify({active:'B-000001',local:{'B-000002':{message:'Other group opinion'}}}));
  s.unsavedQuestions.push({id:'F-000099'});
  s.ui.updateControls();
  assert.ok(s.approveButtons.every(b=>b.disabled===false));
  await s.click('approve');
  assert.equal(s.calls.length,1);
  assert.equal(s.calls[0].body.operation,'approve');
  assert.equal(s.calls[0].body.value,'read-token');
  assert.equal(s.ui.message('B-000002'),'Other group opinion');
  assert.equal(s.unsavedQuestions.length,1);
});

test('batch confirmation has a visible scoped reason and reenables after save or revert', async () => {
  const s=setup();
  s.unsavedQuestions.push({id:'F-000001'}); s.ui.updateControls();
  assert.ok(s.approveButtons.every(b=>b.disabled===true));
  assert.ok(s.confirmHints.every(h=>h.textContent.includes('F-000001')));
  await s.click('approve'); assert.equal(s.calls.length,0);
  s.unsavedQuestions.length=0; s.type('Own unsaved discussion');
  assert.ok(s.approveButtons.every(b=>b.disabled===true));
  assert.ok(s.confirmHints.every(h=>h.textContent.includes('本组讨论')));
  s.type(''); assert.ok(s.approveButtons.every(b=>b.disabled===false));
  s.state.busy=true; s.ui.updateControls(); assert.ok(s.approveButtons.every(b=>b.disabled===true));
  s.state.busy=false; s.ui.updateControls(); assert.ok(s.approveButtons.every(b=>b.disabled===false));
});

test('each candidate offers its own confirmation while optional batch supports internal dependencies', async () => {
  const s=setup();
  s.group.member_ids.push('F-000002','F-000003');
  for (const id of s.group.member_ids.slice(1)) s.state.snapshot.questions.push({id,title:id,definition:{draft:{text:'Complete candidate'},versions:[]},readiness:{status:'waiting',dependencies:[{question_id:'F-000001',status:'waiting',title:'One',reason:'Same formal definition'}]}});
  const panel={dataset:{},querySelector(){return null;}}; s.ui.renderDetail(panel);
  assert.equal((panel.innerHTML.match(/data-action="dg-approve"/g)||[]).length,1);
  assert.equal((panel.innerHTML.match(/data-action="dg-approve-member"/g)||[]).length,3);
  for(const id of s.group.member_ids) assert.ok(panel.innerHTML.includes('aria-describedby="dg-confirm-'+id+'"'));
  assert.match(panel.innerHTML,/确认本组 3 条口径/);
  assert.ok(s.approveButtons.every(b=>b.disabled===false));
  s.holdResponse(); const saving=s.click('approve');
  await s.click('approve'); assert.equal(s.calls.length,1);
  s.releaseResponse(); await saving;
  assert.ok(s.approveButtons.every(b=>b.disabled===false));
});

test('an empty revision cannot use the old effective wording to pass joint preparation', async () => {
  const s=setup(), q=s.state.snapshot.questions[0];
  q.definition={draft:{text:'  '},current_version:1,versions:[{number:1,text:'Old effective rule'}]};
  s.ui.updateControls();
  assert.ok(s.approveButtons.every(b=>b.disabled===true));
  assert.ok(s.confirmHints.every(h=>h.textContent.includes('F-000001')));
  await s.click('approve'); assert.equal(s.calls.length,0);
});

test('member confirmation posts only its question despite sibling and shared discussion drafts',async()=>{
  const s=setup();s.unsavedQuestions.push({id:'F-000002'});s.group.member_ids.push('F-000002');
  s.state.snapshot.questions.push({id:'F-000002',title:'Other member',definition:{draft:null,versions:[]}});
  s.type('Unsent shared discussion');s.ui.updateControls();
  assert.equal(s.memberButtons[0].disabled,false);
  assert.ok(s.approveButtons.every(b=>b.disabled===true));
  await s.click('approve-member',{question:'F-000001'});
  assert.equal(s.calls.length,1);
  assert.equal(s.calls[0].url,'/api/questions/F-000001/change');
  assert.equal(s.calls[0].body.operation,'definition_approve');
  assert.equal(s.calls[0].body.value,'member-token');
  assert.equal(s.calls[0].body.expected_revision,1);
  assert.equal(s.ui.message('B-000001'),'Unsent shared discussion');
  assert.equal(s.state.snapshot.questions[1].definition.draft,null);
  assert.match(s.notices.at(-1)[0],/F-000001 已冻结；其他口径保持原状态/);
});

test('member confirmation blocks only its own pending edit or real prerequisite',async()=>{
  const s=setup(),q=s.state.snapshot.questions[0];
  s.unsavedQuestions.push({id:q.id});s.ui.updateControls();
  assert.equal(s.memberButtons[0].disabled,true);
  assert.match(s.memberHints[0].textContent,/本条候选或留言/);
  await s.click('approve-member',{question:q.id});assert.equal(s.calls.length,0);
  s.unsavedQuestions.length=0;
  q.readiness={status:'waiting',dependencies:[{question_id:'F-000002',status:'waiting'}]};s.ui.updateControls();
  assert.equal(s.memberButtons[0].disabled,true);
  assert.match(s.memberHints[0].textContent,/前序口径：F-000002/);
  await s.click('approve-member',{question:q.id});assert.equal(s.calls.length,0);
  q.readiness={status:'ready',dependencies:[]};s.ui.updateControls();
  assert.equal(s.memberButtons[0].disabled,false);
});

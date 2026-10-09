// Run the shipped workbench against a controlled DOM, storage and API.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const markdown = require('../oppencouncil/assets/markdown.js');
const source = fs.readFileSync(path.join(__dirname, "../oppencouncil/assets/freeze_workbench.js"), "utf8");
const questionId = "F-000007";
const storageKey = "stepwise-freeze:drafts:v1:/synthetic/project";
const settle = async () => { await new Promise(setImmediate); await new Promise(setImmediate); };

async function workbench({ authRequired = false, platform = 'Win32', layoutPreferences = new Map(), initialUrl = "http://localhost/projects/synthetic/freeze", additionalQuestions = [], drawer = false, reducedMotion = false, decisionGroups = [], reviewNotes = [], display = {}, messages = [], answers = {}, draftMessages = {}, requests = {}, answer = null, definition = { draft: null, versions: [], current_version: null }, definitions = {}, definitionBases = {}, opinion = "" } = {}) {
  let selection = null, focused = null, expired = false, reloads = 0;
  const documentListeners = {};
  const elements = new Map(), listeners = {}, storage = new Map(), windowListeners = {}, historyWrites = [], choiceControls = [];
  const pageLocation = {href:initialUrl,reload:()=>reloads++};
  const pageHistory = Object.fromEntries(['pushState','replaceState'].map(method => [method,(_state,_title,url)=>{pageLocation.href=url;historyWrites.push({method,url});}]));
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      id:selector.startsWith('#') ? selector.slice(1) : '', dataset: {}, attrs:{}, isConnected:true, style: { setProperty(key,value) { this[key]=value; }, removeProperty(key) { delete this[key]; } }, hidden: false, textContent: "", value: "",
      innerHTML: "", scrollTop: 0, scrollHeight: 100, open: false,
      setAttribute(key,value) {this.attrs[key]=value;}, addEventListener() {}, focus() {focused=selector;}, setPointerCapture() {},
      contains(node) {return node===this || (selector==='#sw2-select-popover' && node?.id?.startsWith('sw2-select-'));}, closest() {return null;},
      click() {
        const action = selector.match(/^\[data-action="([^"]+)"\]$/)?.[1];
        if (action) return listeners.click({target:{closest:css=>css==='[data-action]'?{dataset:{action},textContent:action}:null}});
      },
      getBoundingClientRect: () => ({width:selector === '.sw2-discussion-column' ? Math.max(300,Math.min(880,parseFloat(element('#sw2-detail').style['--discussion-width']) || 380)) : 1600}),
      querySelector: element, querySelectorAll: () => [],
    });
    return elements.get(selector);
  }
  const tag = element(".sw2-draft-tag");
  const questionButton = { dataset: { id: questionId }, querySelector: () => tag };
  const root = {
    dataset: { projectId: "synthetic" }, setAttribute() {}, contains: () => true, setPointerCapture() {},
    querySelector: element,
    querySelectorAll: selector => selector === "[data-action=select]" ? [questionButton] : selector === "[data-choice-control]" ? choiceControls : [],
    addEventListener: (name, callback) => { listeners[name] = callback; },
  };
  element("#sw2-overlay").hidden = true;
  let question = {
    id: questionId, title: "合成问题", group: "goal", round: 1, revision: 2,
    review_notes: reviewNotes, discussion_display: display,
    status: "discussing", user_answer: answer, messages, created_by: "codex",
    ai_position: opinion, ai_position_by: "codex", requests: {}, definition: structuredClone(definition),
  };
  let failAfterCommit = false;
  const writes = [];
  storage.set(storageKey, JSON.stringify({ answers, definitions, definitionBases, messages: draftMessages, requests, selected: questionId }));
  vm.runInNewContext(source, {
    document: { getElementById: () => root, addEventListener(name, callback) { documentListeners[name] = callback; }, hidden: false },
    URL, location:pageLocation, navigator: {platform},
    window: { getSelection:()=>selection, innerWidth:1600, innerHeight:1000, location:pageLocation,history:pageHistory,CouncilMarkdown: markdown, matchMedia: query => ({ matches: query.includes('min-width: 1024') || (drawer && query.includes("1279")) || (reducedMotion && query.includes("reduced-motion")), addEventListener() {} }), addEventListener(name,callback) { windowListeners[name]=callback; } },
    localStorage: { getItem:key=>layoutPreferences.get(key),setItem:(key,value)=>layoutPreferences.set(key,value),removeItem:key=>layoutPreferences.delete(key) },
    sessionStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    getComputedStyle: () => ({paddingTop:"0",paddingBottom:"0",borderTopWidth:"0",borderBottomWidth:"0"}),
    crypto: { randomUUID: () => "new-request" }, AbortController,
    setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    fetch: async (_url, options) => {
      if (expired) return {ok:false,status:401,json:async()=>({error:"Login required"})};
      if (_url === "/api/logout") { writes.push({logout:true}); return {ok:true,json:async()=>({ok:true})}; }
      if (options.method === "POST") {
        const body = JSON.parse(options.body);
        writes.push(body);
        if (body.operation === "comment") {
          question.messages.push({ id: body.request_id, actor: "user", text: body.value, round: 1 });
        } else if (body.operation === "answer") question.user_answer = body.value;
        else if (body.operation === "definition_draft") question.definition.draft = {
          text: body.value, text_sha256: "test-hash", base_version: question.definition.current_version,
          updated_by: "user", approval: null, edits: [],
        };
        else if (body.operation === "definition_approve") {
          const def = question.definition, number = def.versions.length + 1;
          def.versions.push({ number, text: def.draft.text, source: `Freeze/questions/${questionId}.json#/definition/versions/${number - 1}` });
          def.current_version = number; def.draft = null; question.status = "frozen";
        }
        else if (body.operation === "definition_begin") question.definition.draft = {
          text: question.definition.versions.at(-1).text, base_version: question.definition.current_version,
          updated_by: "user", approval: null, edits: [],
        };
        else if (body.operation === "definition_discard") {
          const def = question.definition;
          (def.withdrawn_drafts ||= []).push({ ...def.draft, local_edit: body.value ? { ...body.value, by: "user" } : undefined });
          def.draft = null; question.status = def.current_version ? "frozen" : "discussing";
        }
        question.revision++;
        if (failAfterCommit) { failAfterCommit = false; throw new Error("Failed to fetch"); }
        return { ok: true, json: async () => ({ question: structuredClone(question) }) };
      }
      return { ok: true, json: async () => ({ csrf: "test", auth_required:authRequired, snapshot: {
        project: "/synthetic/project", round: 1, questions: [structuredClone(question),...structuredClone(additionalQuestions)], decision_groups: decisionGroups,
      } }) };
    },
  });
  await settle();
  return {
    text: selector => element(selector).textContent,
    html: selector => element(selector).innerHTML,
    value: selector => element(selector).value,
    disabled: selector => element(selector).disabled,
    hidden: selector => element(selector).hidden,
    tag,historyWrites,url:()=>pageLocation.href,
    pop: url=>{pageLocation.href=url;windowListeners.popstate();},
    layout: () => root.dataset,
    drafts: () => JSON.parse(storage.get(storageKey)),
    writes,expire:()=>{expired=true;},reauthenticate:()=>{expired=false;},reloads:()=>reloads,
    discussionWidth: () => element('.sw2-discussion-column').getBoundingClientRect().width,
    resizeEvent: (name, values={}) => listeners[name]({button:0,pointerId:1,clientX:1000,preventDefault(){},target:{closest:()=>element('.sw2-discussion-resizer')},...values}),
    parameter(id, label, values) {
      const select = {id:'',dataset:{action:'open-choice',choiceKey:questionId+':'+id,choiceLabel:label,choiceSignature:JSON.stringify([label,...values])},value:'',setAttribute(){},focus(){},contains:()=>false,
        getBoundingClientRect:()=>({left:100,top:100,bottom:130,width:80}),isConnected:true};
      const click = button=>listeners.click({target:{closest:selector=>selector==='[data-action]'?button:null}});
      choiceControls.push(select);
      return {open(){return click(select);},select(value){click(select);if(value)click({dataset:{action:'select-value',index:String(values.indexOf(value))}});else click({dataset:{action:'clear-choice'}});click({dataset:{action:'close-select'}});},value:()=>select.value,
        async append(){await click(select);await click({dataset:{action:'choice-discuss'}});}};
    },
    menuKey: key=>listeners.keydown({key,preventDefault(){},stopPropagation(){},target:element('#sw2-select-list')}),
    focus:()=>focused,
    outside:()=>documentListeners.pointerdown({target:{}}),
    selectQuote(text, label = 'F-000007 · 候选口径 v1', valid = true) {
      const source = {dataset:{quoteSource:label}, contains:()=>valid};
      const node = {nodeType:1, closest:css=>css==='[data-quote-source]'?source:null};
      selection = {rangeCount:1,isCollapsed:!text,removeAllRanges(){this.isCollapsed=true;},getRangeAt:()=>({
        startContainer:node,endContainer:node,cloneContents:()=>({nodeType:3,textContent:text}),
        getBoundingClientRect:()=>({left:100,top:100,bottom:150,width:200})})};
      documentListeners.selectionchange();
    },
    clearQuote:()=>documentListeners.scroll(),
    remoteDefinition: value => { question.definition = structuredClone(value); question.revision++; },
    failNextResponse: () => { failAfterCommit = true; },
    input: (id, value) => { element("#" + id).value = value; listeners.input({ target: { id, value } }); },
    disclosure: details => listeners.click({ preventDefault(){}, target:{ closest: selector => selector === "summary" ? {parentElement:details} : null } }),
    key: async (id, key, modifiers={}) => {
      let prevented = false;
      listeners.keydown({key,preventDefault(){prevented=true;},target:{id,value:element('#'+id).value,closest:()=>null},...modifiers});
      await settle(); return prevented;
    },
    click: async (action,data={}, modifiers={}) => {
      const button = action === "open-status" ? Object.assign(element("#sw2-status-filter"),{dataset:{action}}) : { dataset: { action,...data }, textContent: action };
      let prevented=false;
      await listeners.click({preventDefault(){prevented=true;},target:{closest:selector=>selector==='[data-action]'?button:null},...modifiers});
      return prevented;
    },
  };
}

test("a saved discussion receipt clears the recovered draft and makes its saved state visible", async () => {
  const app = await workbench({
    messages: [{ id: "saved-comment", actor: "user", text: "已提交的留言" }],
    draftMessages: { [questionId]: " 已提交的留言\n" },
    requests: { [questionId + ":comment"]: "saved-comment" },
  });
  assert.equal(app.text("#sw2-draft-label"), "无未保存修改");
  assert.equal(app.text("#sw2-message-hint"), "讨论已保存 · 1 条记录");
  assert.equal(app.tag.hidden, true);
  assert.deepEqual(app.drafts().messages, {});
  assert.deepEqual(app.writes, []);
});

test("refresh confirms a committed discussion after its save response was lost", async () => {
  const app = await workbench();
  app.input("sw2-message", "测试断线后的留言");
  app.failNextResponse();
  await app.click("post");
  assert.equal(app.text("#sw2-message-hint"), "留言未保存");
  await app.click("refresh");
  assert.equal(app.text("#sw2-draft-label"), "无未保存修改");
  assert.equal(app.text("#sw2-message-hint"), "讨论已保存 · 1 条记录");
  assert.equal(app.writes.length, 1);
  assert.deepEqual(app.drafts().requests, {});
});

test("an identical new discussion keeps its own unsaved draft", async () => {
  const app = await workbench({
    messages: [{ id: "older-comment", actor: "user", text: "相同文字" }],
    draftMessages: { [questionId]: "相同文字" },
    requests: { [questionId + ":comment"]: "different-request" },
  });
  assert.equal(app.text("#sw2-message-hint"), "留言未保存");
  assert.equal(app.tag.textContent, "留言未保存");
  assert.equal(app.drafts().messages[questionId], "相同文字");
});

test("a changed draft or another actor's receipt cannot clear a human draft", async () => {
  for (const [actor, text] of [["user", "以前的留言"], ["codex", "新的留言"]]) {
    const app = await workbench({
      messages: [{ id: "receipt", actor, text }],
      draftMessages: { [questionId]: "新的留言" },
      requests: { [questionId + ":comment"]: "receipt" },
    });
    assert.equal(app.text("#sw2-message-hint"), "留言未保存");
    assert.equal(app.drafts().messages[questionId], "新的留言");
  }
});

test("saved discussions and pending candidate wording have separate labels", async () => {
  const app = await workbench({ messages: [{ id: "receipt", actor: "user", text: "已保存" }] });
  assert.equal(app.text("#sw2-answer-hint"), "尚无正式版本");
  app.input("sw2-answer", "还在修改的完整候选");
  assert.equal(app.text("#sw2-answer-hint"), "候选口径未保存");
  assert.equal(app.text("#sw2-message-hint"), "讨论已保存 · 1 条记录");
  assert.equal(app.tag.textContent, "候选口径未保存");
});

const candidate = text => ({ draft: { text, text_sha256: "hash", updated_by: "codex", approval: null }, versions: [], current_version: null });

test("candidate whitespace uses saved normalization and save-response loss reconciles", async () => {
  const app = await workbench({ definition: candidate("已保存候选"), definitions: { [questionId]: " 已保存候选\n" } });
  assert.equal(app.text("#sw2-draft-label"), "无未保存修改");
  app.input("sw2-answer", "新增的完整规则");
  app.failNextResponse();
  await app.click("save-answer");
  assert.equal(app.text("#sw2-answer-hint"), "候选口径未保存");
  await app.click("refresh");
  assert.equal(app.text("#sw2-draft-label"), "无未保存修改");
  assert.equal(app.writes[0].operation, "definition_draft");
  assert.equal(app.writes.length, 1);
});

test("legacy answers and initial AI recommendations appear in discussion, never as formal versions", async () => {
  const app = await workbench({ answer: "选择 A", opinion: "详细方案建议" });
  const html = app.html("#sw2-detail");
  const discussion = html.slice(html.indexOf('aria-label="逐项讨论"'));
  assert.ok(discussion.includes("选择 A") && discussion.includes("详细方案建议"));
  assert.ok(discussion.includes("历史答复 · 非正式口径"));
  assert.ok(!html.includes('class="sw2-definition-version'));
  const legacy = await workbench({ answers: { [questionId]: "尚未提交的选择" }, draftMessages: { [questionId]: "已有留言" } });
  assert.deepEqual(legacy.drafts().definitions, {});
  assert.ok(legacy.drafts().messages[questionId].includes("尚未提交的选择"));
  assert.ok(legacy.drafts().messages[questionId].includes("已有留言"));
  assert.equal(legacy.writes.length, 0);
});

test("candidate edits save separately and human confirmation immediately makes the saved full text effective", async () => {
  const app = await workbench({ definition: candidate("AI 起草的完整规则") });
  assert.ok(app.html("#sw2-detail").includes("AI 起草的完整规则"));
  await app.click("edit-definition");
  app.input("sw2-answer", "人类修改后的完整规则");
  assert.equal(app.disabled('[data-action="approve-definition"]'), true);
  await app.click("save-answer");
  assert.equal(app.writes[0].operation, "definition_draft");
  assert.ok(app.html("#sw2-detail").includes("人类修改后的完整规则"));
  assert.equal(app.text("#sw2-draft-label"), "无未保存修改");
  await app.click("approve-definition");
  assert.equal(app.writes[1].operation, "definition_approve");
  assert.ok(app.html("#sw2-detail").includes("版本 v1"));
  assert.ok(app.html("#sw2-detail").includes("当前有效"));
  assert.equal(app.text("#sw2-answered"), 1);
});

test("a changed candidate preserves local edits and blocks a stale overwrite", async () => {
  const app = await workbench({ definition: candidate("原候选") });
  app.input("sw2-answer", "人类尚未保存的修改");
  app.remoteDefinition(candidate("AI 更新后的候选"));
  await app.click("refresh");
  assert.equal(app.drafts().definitions[questionId], "人类尚未保存的修改");
  await app.click("save-answer");
  assert.equal(app.writes.length, 0);
  assert.ok(app.html("#sw2-detail").includes("请比较后再保存"));
});

test("opening v2 keeps v1 effective; confirming v2 retains v1 as history", async () => {
  const version = { number: 1, text: "第一版正式完整文本", source: "Freeze/questions/F-000007.json#/definition/versions/0", published_at: "2026-10-06" };
  const app = await workbench({ definition: { draft: null, current_version: 1, versions: [version] } });
  await app.click("begin-definition");
  app.input("sw2-answer", "第二版完整候选");
  await app.click("save-answer");
  assert.ok(app.html("#sw2-detail").includes("版本 v1"));
  assert.equal(app.text("#sw2-answered"), 1);
  await app.click("approve-definition");
  const html = app.html("#sw2-detail");
  assert.ok(html.includes("版本 v1") && html.includes("当前有效"));
  assert.ok(html.includes("版本 v2") && !html.includes("候选 v2"));
  assert.ok(html.includes("旧版本"));
  await app.click("handoff");
  assert.ok(app.value("#sw2-handoff-text").includes("正式口径 v1（旧版本）"));
  assert.ok(app.value("#sw2-handoff-text").includes("正式口径 v2（当前有效）"));
});


test("discussion composer remains available after save and retains temporarily collapsed input", async () => {
  const app = await workbench();
  await app.click("compose");
  assert.equal(app.hidden(".sw2-message-editor"), false);
  app.input("sw2-message", "完整的待保存意见");
  await app.click("close-compose");
  assert.equal(app.hidden(".sw2-message-editor"), true);
  assert.equal(app.drafts().messages[questionId], "完整的待保存意见");
  await app.click("compose");
  assert.equal(app.value("#sw2-message"), "完整的待保存意见");
  await app.click("post");
  assert.equal(app.drafts().messages[questionId], undefined);
  assert.ok(app.html("#sw2-detail").includes('class="sw2-message-editor">'));
  assert.match(app.html("#sw2-detail"), /<textarea id="sw2-message"[^>]*><\/textarea>/);
});

test("a save emits one dismissible notice without copying its message into the footer", async () => {
  const app = await workbench();
  app.input("sw2-message", "待保存意见");
  await app.click("post");
  assert.equal(app.hidden("#sw2-notice"), false);
  assert.match(app.text("#sw2-notice-text"), /讨论已保存/);
  assert.doesNotMatch(app.text("#sw2-save-label"), /讨论已保存/);
  await app.click("dismiss-notice");
  assert.equal(app.hidden("#sw2-notice"), true);
});


test("machine verification stays outside the human page while historical source text is retained", async () => {
  const w = await workbench({
    messages: [{ id: "old-ai", actor: "codex", text: "Human comparison plus SHA-256 private-hash" }],
    display: { "old-ai": "Human comparison" },
    reviewNotes: [{ text: "Self-check report private-check" }],
  });
  const html = w.html("#sw2-detail");
  assert.match(html, /Human comparison/);
  assert.doesNotMatch(html, /private-hash|private-check|查看核验记录|SHA-256/);
});


test("pending candidate precedes current comparison and collapsed history without losing exact versions", async () => {
  const app = await workbench({ definition: { current_version: 2, draft: { text: "待审第三版" }, versions: [
    { number: 1, text: "第一版原文" }, { number: 2, text: "第二版原文" },
  ] } });
  const html = app.html("#sw2-detail");
  assert.ok(html.indexOf("待审第三版") < html.indexOf("第二版原文"));
  assert.ok(html.indexOf("第二版原文") < html.indexOf("第一版原文"));
  assert.match(html, /<details class="sw2-version-history" data-record="history"><summary>历史版本 · 1/);
  assert.match(app.html("#sw2-question-list"), /候选待确认/);
  assert.equal(app.text("#sw2-open"), 1);
  assert.equal(app.text("#sw2-answered"), 1);
  assert.deepEqual(app.writes, []);
});

test("member review includes saved shared discussion and identifies its origin", async () => {
  const app = await workbench({ decisionGroups: [{ id: "B-000001", title: "联动规则", member_ids: [questionId],
    messages: [{ id: "shared-1", actor: "user", text: "这两条必须一起考虑", at: "2026-10-07" }] }] });
  const html = app.html("#sw2-detail");
  assert.match(html, /这两条必须一起考虑/);
  assert.match(html, /共同讨论 · /);
  assert.match(html, /data-mode="discussion">参与共同讨论/);
  assert.doesNotMatch(html, /开始这题的讨论/);
  assert.equal(app.text("#sw2-answered"), 0);
  assert.deepEqual(app.writes, []);
});


test("cancel revision retains local wording in withdrawal and leaves discussion pending", async () => {
  const def = { ...candidate("Saved revision"), current_version: 1, versions: [{ number: 1, text: "Effective rule" }] };
  const app = await workbench({ definition: def });
  assert.match(app.html("#sw2-detail"), /取消修订/);
  app.input("sw2-answer", "Unfinished wording");
  app.input("sw2-message", "Unsent opinion");
  await app.click("discard-definition");
  assert.equal(app.writes.at(-1).operation, "definition_discard");
  assert.equal(app.writes.at(-1).value.text, "Unfinished wording");
  assert.deepEqual(app.drafts().definitions, {});
  assert.equal(app.drafts().messages[questionId], "Unsent opinion");
  assert.match(app.html("#sw2-detail"), /Effective rule/);
  assert.doesNotMatch(app.html("#sw2-detail"), /data-action="discard-definition"/);
  assert.match(app.text("#sw2-notice-text"), /已取消修订/);
});

test("lost cancellation response clears the matching local edit after refresh", async () => {
  const app = await workbench({ definition: candidate("Saved candidate") });
  app.input("sw2-answer", "Unfinished wording");
  app.failNextResponse(); await app.click("discard-definition");
  assert.equal(app.drafts().definitions[questionId], "Unfinished wording");
  await app.click("refresh");
  assert.deepEqual(app.drafts().definitions, {});
  assert.equal(app.text("#sw2-draft-label"), "无未保存修改");
  assert.equal(app.tag.hidden, true);
});


test("navigation drawer opens and closes without changing pending discussion", async () => {
  const app = await workbench({ drawer: true });
  assert.equal(app.hidden('#sw2-nav-scrim'), true);
  app.input('sw2-message', 'Keep while navigating');
  await app.click('toggle-nav');
  assert.equal(app.layout().navOpen, 'true');
  assert.equal(app.hidden('#sw2-nav-scrim'), false);
  await app.click('close-nav');
  assert.equal(app.layout().navOpen, 'false');
  assert.equal(app.hidden('#sw2-nav-scrim'), true);
  assert.equal(app.drafts().messages[questionId], 'Keep while navigating');
  assert.equal(app.writes.length, 0);
});


test("Markdown renders headings, nested lists, tables, quotations and code without rewriting source", () => {
  const source = '# 范围\n\n**明确规则**与*注释*\n\n1. 第一项\n   - 子项 `字段`\n2. 第二项\n\n| 条件 | 处理 |\n| --- | --- |\n| 缺失 | 待确认 |\n\n> 不推定未观测值\n\n```r\nx <- 1\n```';
  const html = markdown.render(source);
  for (const fragment of ['<h1>范围</h1>', '<strong>明确规则</strong>', '<em>注释</em>', '<ol>', '<ul>', '<table>', '<th>条件</th>', '<blockquote>', '<code class="language-r">x &lt;- 1']) assert.ok(html.includes(fragment),fragment);
  assert.equal(markdown.render('第一行\n第二行').includes('第一行<br>\n第二行'),true);
});

test("Markdown renders unsafe HTML as text and refuses executable links and remote image loads", () => {
  const html = markdown.render('<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n\n[坏链接](javascript:alert%281%29) [转义链接](jav&#x61;script:alert%281%29)\n\n[数据](data:text/html,test)\n\n![图](https://example.com/image.png)\n\n[资料](https://example.com/reference)');
  assert.doesNotMatch(html, /<script|<img|href="(?:javascript|data):|<iframe/i);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /href="https:\/\/example.com\/reference" target="_blank" rel="noopener noreferrer"/);
});

test("Markdown candidate edits, preview and confirmed history keep the exact saved Markdown", async () => {
  const first = '## 当前规则\n\n- **规则 A**\n- 例外待核查';
  const next = '## 修订规则\n\n| 条件 | 处理 |\n| --- | --- |\n| 缺失 | 保留缺失 |';
  const app = await workbench();
  app.input('sw2-answer', first);
  assert.match(app.html('#sw2-answer-preview'), /<h2>当前规则<\/h2>/);
  await app.click('save-answer');
  assert.equal(app.writes.at(-1).value, first);
  assert.match(app.html('#sw2-detail'), /<strong>规则 A<\/strong>/);
  await app.click('approve-definition');
  await app.click('begin-definition');
  app.input('sw2-answer', next); await app.click('save-answer'); await app.click('approve-definition');
  assert.equal(app.writes.filter(w=>w.operation==='definition_draft').at(-1).value,next);
  assert.match(app.html('#sw2-detail'), /<h2>修订规则<\/h2>/);
  assert.match(app.html('#sw2-detail'), /<h2>当前规则<\/h2>/);
  await app.click('handoff');
  assert.ok(app.value('#sw2-handoff-text').includes(first));
  assert.ok(app.value('#sw2-handoff-text').includes(next));
});


function disclosureFixture() {
  const animations=[];
  const details={tagName:'DETAILS',open:false,style:{height:'',overflow:''},dataset:{},
    getBoundingClientRect:()=>({height:details.open?240:30}),querySelector:()=>({getBoundingClientRect:()=>({height:30})}),
    animate(frames,timing){const a={frames,timing,canceled:false,cancel(){this.canceled=true;}};animations.push(a);return a;}};
  return {details,animations};
}
test('disclosures reverse in flight and release temporary clipping on completion',async()=>{
  const app=await workbench(), {details,animations}=disclosureFixture();
  await app.disclosure(details); assert.equal(details.open,true); assert.equal(details.style.overflow,'hidden');
  await app.disclosure(details); assert.equal(animations[0].canceled,true); assert.equal(details.dataset.closing,'true');
  animations[1].onfinish(); assert.equal(details.open,false); assert.equal(details.style.overflow,''); assert.equal(details.style.height,'');
  await app.disclosure(details); animations[2].onfinish(); assert.equal(details.open,true); assert.equal(details.dataset.closing,undefined);
});
test('reduced-motion disclosures change immediately without animation or clipping',async()=>{
  const app=await workbench({reducedMotion:true}), {details,animations}=disclosureFixture();
  await app.disclosure(details); assert.equal(details.open,true);
  await app.disclosure(details); assert.equal(details.open,false);
  assert.equal(animations.length,0); assert.equal(details.style.overflow,'');
});


test('question URLs override session selection and browser history preserves pending text',async()=>{
  const other={id:'F-000008',title:'Second question',group:'goal',round:1,status:'open',messages:[],definition:{draft:null,versions:[],current_version:null}};
  const base='http://localhost/projects/synthetic/freeze';
  const app=await workbench({initialUrl:base+'?question=F-000008',additionalQuestions:[other]});
  assert.match(app.html('#sw2-detail'),/Second question/);
  assert.equal(app.historyWrites.length,1);assert.equal(app.historyWrites[0].method,'replaceState');
  await app.click('select',{id:questionId});app.input('sw2-message','Preserve on Back');
  assert.equal(app.url(),base+'?question='+questionId);assert.equal(app.historyWrites.at(-1).method,'pushState');
  const count=app.historyWrites.length;
  app.pop(base+'?question=F-000008');assert.match(app.html('#sw2-detail'),/Second question/);
  app.pop(base+'?question='+questionId);assert.equal(app.drafts().messages[questionId],'Preserve on Back');
  assert.equal(app.historyWrites.length,count);assert.equal(app.writes.length,0);
  await app.click('refresh');assert.equal(app.historyWrites.length,count);
});

test('resizing discussion persists across navigation/reload without submitting pending prose', async () => {
  const layoutPreferences = new Map();
  const app = await workbench({layoutPreferences});
  app.input('sw2-message', '需要保留的讨论草稿');
  app.resizeEvent('pointerdown');
  app.resizeEvent('pointermove', {clientX:780});
  app.resizeEvent('pointerup');
  assert.equal(app.discussionWidth(), 600);
  await app.click('refresh');
  assert.equal(app.discussionWidth(), 600);
  assert.equal(app.drafts().messages[questionId], '需要保留的讨论草稿');
  assert.equal(app.writes.length, 0);
  const reopened = await workbench({layoutPreferences});
  assert.equal(reopened.discussionWidth(), 600);
  reopened.resizeEvent('dblclick');
  assert.equal(reopened.discussionWidth(), 380);
  assert.equal(layoutPreferences.size, 0);
});

test('discussion resizing preserves reading space and supports keyboard and cancelled drags', async () => {
  const layoutPreferences = new Map();
  const app = await workbench({layoutPreferences});
  app.resizeEvent('pointerdown');
  app.resizeEvent('pointermove', {clientX:-3000});
  assert.equal(app.discussionWidth(), 880);
  app.resizeEvent('pointercancel');
  assert.equal(app.discussionWidth(), 380);
  assert.equal(layoutPreferences.size, 0);
  app.resizeEvent('keydown', {key:'ArrowLeft'});
  assert.equal(app.discussionWidth(), 396);
  app.resizeEvent('keydown', {key:'Home'});
  assert.equal(app.discussionWidth(), 300);
  app.resizeEvent('keydown', {key:'Enter'});
  assert.equal(app.discussionWidth(), 380);
  assert.equal(app.layout().resizingDiscussion, undefined);
  assert.deepEqual(app.writes, []);
});

test('discussion Markdown previews, saves and renders without changing its stored source', async () => {
  const text = '## 建议\n\n- **保留草稿**\n- 手动确认\n\n| 方案 | 影响 |\n| --- | --- |\n| A | 自动恢复 |\n\n> 仍待确认\n\n```js\nconst saved = false;\n```\n\n<script>alert(1)</script>';
  const app = await workbench({opinion:'### 初始建议\n\n按 **方案 A** 讨论。'});
  assert.match(app.html('#sw2-detail'), /<h3>初始建议<\/h3>/);
  app.input('sw2-message', text);
  const preview = app.html('#sw2-message-preview');
  for (const tag of ['<h2>','<ul>','<strong>','<table>','<blockquote>','<pre>']) assert.ok(preview.includes(tag));
  assert.ok(!preview.includes('<script>'));
  assert.equal(app.writes.length, 0);
  await app.click('post');
  assert.equal(app.writes[0].value,text);
  await app.click('refresh');
  assert.match(app.html('#sw2-detail'), /<h2>建议<\/h2>/);
  assert.match(app.html('#sw2-detail'), /&lt;script&gt;/);
  assert.equal(app.text('#sw2-draft-label'), '无未保存修改');
});


test('Chinese punctuation next to bold delimiters works without changing code, escaping or nesting', () => {
  for (const punctuation of ['：','，','。','；','！','？','）','】','”']) {
    assert.ok(markdown.render('前文**规则'+punctuation+'**后文').includes('<strong>规则'+punctuation+'</strong>后文'));
  }
  assert.ok(markdown.render('按**（建议）**继续').includes('按<strong>（建议）</strong>继续'));
  assert.ok(markdown.render('**规则 *A*：**保留').includes('<strong>规则 <em>A</em>：</strong>保留'));
  const source = '`**建议：**`\n\n```txt\n**建议：**正文\n```\n\n\\*\\*建议：\\*\\*正文';
  assert.doesNotMatch(markdown.render(source), /<strong>/);
  assert.doesNotMatch(markdown.render('** 未闭合：正文'), /<strong>/);
});

test('references link only known complete IDs in prose, headings and tables', () => {
  const context = {questionIds:['F-000013']};
  const source = '## **见 F-000013：**正文\n\n| 依据 |\n| --- |\n| F-000013 |\n\n未知 F-999999、F13、F-13、F-0000139、AF-000013、Freeze/F-000013.json。\n\n`F-000013` [F-000013](https://example.com)\n\n```txt\nF-000013\n```';
  const html = markdown.render(source, context);
  assert.equal((html.match(/data-action="reference-question"/g) || []).length, 2);
  assert.match(html, /href="\?question=F-000013" data-action="reference-question" data-id="F-000013" target="_blank" rel="noopener noreferrer"/);
  assert.match(html, /<code>F-000013<\/code>/);
  assert.match(html, /href="https:\/\/example.com" target="_blank"/);
  assert.doesNotMatch(markdown.render('F-000013'), /<a /);
  assert.doesNotMatch(markdown.render('https://example.com/?question=F-000013', context), /<a /);
});

test('reference links open a separate tab without changing current drafts or history', async () => {
  const other={id:'F-000008',title:'Linked question',group:'goal',round:1,status:'open',messages:[],definition:{draft:null,versions:[],current_version:null}};
  const app=await workbench({additionalQuestions:[other],opinion:'**依据：**F-000008'});
  assert.match(app.html('#sw2-detail'), /<strong>依据：<\/strong><a href="\?question=F-000008"/);
  app.input('sw2-message','Draft to keep'); const before=app.url();
  assert.equal(await app.click('reference-question',{id:other.id},{metaKey:true}),false);
  assert.equal(app.url(),before);
  const detail=app.html('#sw2-detail'),historyCount=app.historyWrites.length;
  assert.equal(await app.click('reference-question',{id:other.id}),false);
  assert.equal(app.url(),before);
  assert.equal(app.html('#sw2-detail'),detail);
  assert.equal(app.historyWrites.length,historyCount);
  assert.equal(app.drafts().messages[questionId],'Draft to keep');
  assert.equal(app.writes.length,0);
});

test('discussion keyboard save uses the platform modifier and preserves Markdown exactly', async () => {
  for (const [platform,modifier,other] of [['Win32','ctrlKey','metaKey'],['MacIntel','metaKey','ctrlKey']]) {
    const app=await workbench({platform}); const text='**依据：**F-000007\n第二行';
    app.input('sw2-message',text);
    for (const modifiers of [{},{[modifier]:true,[other]:true},{[modifier]:true,shiftKey:true},{[modifier]:true,isComposing:true},{[modifier]:true,keyCode:229},{[modifier]:true,repeat:true}]) await app.key('sw2-message','Enter',modifiers);
    await app.key('sw2-answer','Enter',{[modifier]:true});
    assert.equal(app.writes.length,0);
    assert.equal(await app.key('sw2-message','Enter',{[modifier]:true}),true);
    assert.equal(app.writes.length,1); assert.equal(app.writes[0].value,text);
    assert.equal(app.text('#sw2-draft-label'),'无未保存修改');
    await app.key('sw2-message','Enter',{[modifier]:true});
    assert.equal(app.writes.length,1);
    app.input('sw2-message','嵌入浏览器也识别另一种修饰键');
    await app.key('sw2-message','Enter',{[other]:true});
    assert.equal(app.writes.length,2);
  }
});

test('keyboard saves preserve uncertain discussion drafts for receipt recovery', async () => {
  const app=await workbench(); app.input('sw2-message','Keep until acknowledged'); app.failNextResponse();
  await app.key('sw2-message','Enter',{ctrlKey:true});
  assert.equal(app.drafts().messages[questionId],'Keep until acknowledged');
  assert.equal(app.text('#sw2-message-hint'),'留言未保存');
  await app.click('refresh');
  assert.equal(app.text('#sw2-draft-label'),'无未保存修改'); assert.equal(app.writes.length,1);
});


test('inline parameters render inside Markdown tables, restore valid choices, and isolate scopes', () => {
  const source='| 参数 |\n|---|\n| {{choice:horizon;随访时长;12个月;24个月;36个月}} |';
  const signature=JSON.stringify(['随访时长','12个月','24个月','36个月']);
  const context={choiceScope:'B-000001',choiceValues:{'B-000001:horizon':{signature,value:'24个月'}}};
  const html=markdown.render(source,context);
  assert.match(html,/<table>/); assert.match(html,/value="24个月"/);
  assert.doesNotMatch(html,/<select|<option/); assert.match(html,/aria-haspopup="listbox"/);
  assert.match(markdown.render(source,{...context,choiceScope:'B-000002'}),/value=""/);
  assert.match(markdown.render(source.replace('36个月','48个月'),context),/value=""/);
  assert.match(markdown.render(source,{...context,choiceValues:{'B-000001:horizon':{signature,value:'不存在'}}}),/value=""/);
});

test('parameter extension is inert in code, escaped syntax, links, and formal document contexts', () => {
  const token='{{choice:wait;等待时长;5秒;10秒}}', context={choiceScope:'F-000001'};
  for (const source of ['`'+token+'`','```txt\n'+token+'\n```','\\'+token,'['+token+'](https://example.com)','{{choice:wait;等待;5秒;5秒}}','{{choice:wait;等待;5秒}}']) assert.doesNotMatch(markdown.render(source,context),/data-choice-control/);
  assert.doesNotMatch(markdown.render(token),/data-choice-control/);
  const html=markdown.render('{{choice:wait;<img src=x>;5秒;10秒}}',context);
  assert.doesNotMatch(html,/<img/);assert.match(html,/&lt;img src=x&gt;/);
});

test('parameter choices remember local preference, sync repeated controls, and only draft punctuation-separated discussion', async () => {
  const layoutPreferences=new Map();
  const source='{{choice:wait;等待时长;5秒;10秒}}';
  const app=await workbench({layoutPreferences,opinion:source});
  const one=app.parameter('wait','等待时长',['5秒','10秒']);
  const repeated=app.parameter('wait','等待时长',['5秒','10秒']);
  const two=app.parameter('limit','最多重试',['1次','2次']);
  one.select('10秒'); two.select('2次');
  assert.equal(repeated.value(),'10秒'); assert.equal(app.writes.length,0);
  assert.equal(app.text('#sw2-draft-label'),'无未保存修改');
  const restored=await workbench({layoutPreferences,opinion:source});
  assert.match(restored.html('#sw2-detail'),/value="10秒"/);
  app.input('sw2-message','请保留已有记录');
  await one.append(); await two.append();
  const expected='请保留已有记录；倾向等待时长：10秒；倾向最多重试：2次';
  assert.equal(app.drafts().messages[questionId],expected);
  assert.equal(app.writes.length,0);
  await app.key('sw2-message','Enter',{ctrlKey:true});
  assert.equal(app.writes.length,1);assert.equal(app.writes[0].value,expected);
  one.select('');assert.equal(repeated.value(),'');
});


test('selected quotations preserve drafts, stay literal, and persist only through explicit discussion save', async () => {
  const app = await workbench({draftMessages:{[questionId]:'已有意见'}});
  const text = '第一条规则\n\n<script>bad()</script> {{choice:x;参数;1;2}} **原文**';
  app.selectQuote(text);
  assert.equal(app.hidden('#sw2-quote-selection'),false);
  await app.click('quote-selection');
  const draft = app.value('#sw2-message');
  assert.ok(draft.startsWith('已有意见\n\n> F\\-000007 · 候选口径 v1'));
  assert.equal(app.writes.length,0);
  assert.equal(app.drafts().messages[questionId],draft);
  const html = markdown.render(draft,{questionIds:[questionId],choiceScope:questionId});
  assert.match(html,/<blockquote>/);assert.doesNotMatch(html,/<script>|data-choice-control|<strong>原文/);
  app.input('sw2-message',draft+'请明确这条边界。');
  await app.click('post');
  assert.equal(app.writes[0].value,draft+'请明确这条边界。');
  assert.equal(app.hidden('#sw2-quote-selection'),true);
  assert.equal(app.drafts().messages[questionId],undefined);
});

test('empty, cross-source, scrolled and stale selections cannot quote into another topic', async () => {
  const app = await workbench({additionalQuestions:[{id:'F-000008',title:'另一题',group:'goal',definition:{versions:[],draft:null}}]});
  app.selectQuote('');assert.equal(app.hidden('#sw2-quote-selection'),true);
  app.selectQuote('跨区域','来源',false);assert.equal(app.hidden('#sw2-quote-selection'),true);
  app.selectQuote('正确选文');app.clearQuote();await app.click('quote-selection');
  assert.equal(app.value('#sw2-message'),'');
  app.selectQuote('原题选文');await app.click('select',{id:'F-000008'});await app.click('quote-selection');
  assert.equal(app.value('#sw2-message'),'');assert.equal(app.writes.length,0);
});


test('custom parameter menu separates keyboard exploration, selection and discussion submission',async()=>{
  const app=await workbench();const choice=app.parameter('wait','等待',['5秒','10秒','30秒']);
  await choice.open();assert.equal(app.hidden('#sw2-select-popover'),false);
  app.menuKey('ArrowDown');assert.equal(choice.value(),'');assert.equal(app.writes.length,0);
  app.menuKey('Enter');assert.equal(choice.value(),'10秒');
  assert.equal(app.hidden('#sw2-select-popover'),false);assert.equal(app.drafts().messages[questionId],undefined);
  app.menuKey('End');app.menuKey('Escape');assert.equal(choice.value(),'10秒');
  assert.equal(app.hidden('#sw2-select-popover'),true);
  await choice.open();app.outside();assert.equal(app.hidden('#sw2-select-popover'),true);
  await choice.append();assert.equal(app.value('#sw2-message'),'倾向等待：10秒');assert.equal(app.writes.length,0);
});

test('custom status menu filters without losing drafts and native selector markup is absent',async()=>{
  const app=await workbench();app.input('sw2-message','保留我的讨论');
  await app.click('open-status');
  assert.equal(app.hidden('#sw2-select-footer'),true);
  app.menuKey('Home');app.menuKey('ArrowDown');app.menuKey('Enter');
  assert.equal(app.hidden('#sw2-select-popover'),true);
  assert.equal(app.value('#sw2-status-filter'),'candidate');
  assert.equal(app.writes.length,0);
  // The native-select-free requirement applies to static status and dynamic Markdown controls.
  const page=fs.readFileSync(path.join(__dirname,'../oppencouncil/assets/freeze_workbench.html'),'utf8');
  assert.doesNotMatch(page,/<select|<option/);
  assert.match(page,/data-action="open-status"/);
  assert.equal(app.drafts().messages[questionId],'保留我的讨论');
});


test('expired authentication keeps drafts and exposes new-tab login; logout waits for saved work',async()=>{
  const app=await workbench({authRequired:true});
  assert.equal(app.hidden('#sw2-logout'),false);
  app.input('sw2-message','Keep this draft');
  await app.click('logout');assert.equal(app.reloads(),0);assert.equal(app.writes.length,0);
  app.expire();await app.click('refresh');
  assert.equal(app.hidden('#sw2-login'),false);
  assert.equal(app.drafts().messages[questionId],'Keep this draft');
  app.reauthenticate();await app.click('refresh');assert.equal(app.hidden('#sw2-login'),true);
  app.input('sw2-message','');await app.click('logout');
  assert.equal(app.reloads(),1);assert.deepEqual(app.writes,[{logout:true}]);
});

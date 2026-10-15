const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../oppencouncil/assets/index.js'), 'utf8');

async function directory(projects) {
  const elements = new Map();
  const document = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, {addEventListener() {}});
      return elements.get(selector);
    },
    addEventListener() {},
  };
  vm.runInNewContext(source, {
    document, AbortController, Date,
    setTimeout: () => 1, clearTimeout() {}, setInterval() {},
    fetch: async () => ({ok: true, status: 200, json: async () => ({projects, auth_required: true})}),
  });
  await new Promise(setImmediate);
  return elements;
}

test('directory renders mixed generations using their actual work counters', async () => {
  const elements = await directory([
    {name:'Research <v5>', url:'/projects/research/freeze', available:true, governance_version:5,
      total:4, round:1, in_progress:3, awaiting_review:1, formal:1},
    {name:'Legacy', url:'/projects/legacy/freeze', available:true,
      total:7, round:2, open:4, discussing:2, formal:1},
    {name:'Disconnected', available:false},
  ]);
  const html = elements.get('#projects').innerHTML;
  assert.equal(elements.get('#count').textContent, '· 3');
  assert.match(html, /<strong>3<\/strong>进行中/);
  assert.match(html, /<strong>1<\/strong>待确认/);
  assert.match(html, /<strong>4<\/strong>待讨论/);
  assert.match(html, /<strong>2<\/strong>讨论中/);
  assert.match(html, /Research &lt;v5&gt;/);
  assert.match(html, /项目暂不可用/);
  assert.doesNotMatch(html, /undefined|NaN/);
  assert.match(elements.get('#status').textContent, /已同步/);
});

test('an empty V5 project remains an available card rather than an empty directory', async () => {
  const elements = await directory([
    {name:'Empty', url:'/projects/empty/freeze', available:true, governance_version:5,
      total:0, round:1, in_progress:0, awaiting_review:0, formal:0},
  ]);
  const html = elements.get('#projects').innerHTML;
  assert.match(html, /href="\/projects\/empty\/freeze"/);
  assert.match(html, /<strong>0<\/strong>进行中/);
  assert.doesNotMatch(html, /还没有协作项目|undefined|NaN/);
});

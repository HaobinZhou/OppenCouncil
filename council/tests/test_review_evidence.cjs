const {test}=require('node:test');
const assert=require('node:assert/strict');
const {model,content,links,create}=require('../oppencouncil/assets/review_evidence.js');
const markdown=require('../oppencouncil/assets/markdown.js');

const s=(id,version=1)=>({path:`evidence/sources/S-${id}/r${version}.json`,id:`S-${id}`,version,citation:'Source '+id,verification:'full_text_location',source_type:'method_paper',read_scope:'Checked sections',location:'Section 2'});
const [one,two,three]=[s('000001'),s('000002'),s('000003')];
const payload={id:'B-000001',revision:1,option:0,title:'A',bound:true,sources:[one,two,three],claims:[
  {claim:'First judgment',applicability:'First conditions',sources:[two.path,one.path],counter_sources:[]},
  {claim:'Second judgment',applicability:'Limits',sources:[one.path],counter_sources:[three.path]},
],unavailable:[]};

test('numbers follow the displayed judgment order, share repeats, and include counter evidence',()=>{
  const view=model(payload);
  assert.deepEqual(view.sources.map(x=>[x.path,x.number]),[[two.path,1],[one.path,2],[three.path,3]]);
  assert.equal(view.claims[1].citations[0].number,2);
  assert.equal(view.claims[1].counters[0].number,3);
  const html=content(payload,three.path,markdown.render);
  assert.match(html,/依据 \[3\]/);
  assert.match(html,/相反或限制性依据/);
  assert.match(html,/Limits/);
});

test('each option starts at one and excludes the other option and unbound choices',()=>{
  const b={...payload,option:1,claims:[{claim:'B only',sources:[three.path]}],sources:[three]};
  assert.equal(model(b).numbers.get(three.path),1);
  const html=content(b,one.path);
  assert.doesNotMatch(html,/Source 000001|Source 000002|First judgment/);
  assert.match(html,/依据 \[1\]/);
  assert.match(content({...b,claims:[],sources:[],bound:false}),/此方案尚未关联/);
});

test('source findings precede interpretation and checking notes do not substitute for findings',()=>{
  const source={...one,summary:'Among **30** synthetic observations, 18 had a measurement.',read_scope:'Audit-only process note'};
  const input={...payload,sources:[source],claims:[{claim:'Coverage differs by group',applicability:'Compare measured groups',sources:[one.path]}]};
  const html=content(input,one.path,markdown.render);
  assert.match(html,/Among <strong>30<\/strong> synthetic observations, 18 had a measurement/);
  assert.ok(html.indexOf('Among')<html.indexOf('Coverage differs'));
  assert.doesNotMatch(html,/Audit-only process note/);
  assert.match(html,/Section 2/);
  assert.match(html,new RegExp(one.path.replaceAll('.','\\.')));
  const legacy=content({...input,sources:[{...one,read_scope:'Legacy substantive observation'}]},one.path,markdown.render);
  assert.match(legacy,/Legacy substantive observation/);
  assert.doesNotMatch(legacy,/Among|ce-source-summary/);
});

test('versions remain distinct and citations cannot inject markup or unsafe links',()=>{
  const newer=s('000001',2);
  assert.equal(model({...payload,claims:[],sources:[one,newer]}).sources.length,2);
  const malicious={...one,citation:'<img src=x onerror=alert(1)> javascript:alert(1) https://example.org/paper',location:'https://user:secret@example.org/private'};
  const html=content({...payload,claims:[],sources:[malicious]});
  assert.doesNotMatch(html,/<img|href="javascript:|href="https:\/\/user:/);
  assert.deepEqual(links(malicious),['https://example.org/paper']);
  assert.match(html,/&lt;img/);
  assert.match(html,/target="_blank" rel="noopener noreferrer"/);
});

test('missing cited versions stay visible and cannot borrow a different record',()=>{
  const html=content({...payload,sources:[one],unavailable:[two.path,three.path]});
  assert.match(html,/部分已关联依据暂时无法读取/);
  assert.match(html,/依据暂时无法读取/);
  assert.equal(model({...payload,sources:[one]}).numbers.get(two.path),1);
});

test('original links stop before citation punctuation without losing URL paths or fragments',()=>{
  assert.deepEqual(links({
    citation:'Guide https://example.org/guide#missing-values（2026-10-16访问）。',
    location:'https://example.org/guide#categorical-inputs；#missing-values，段落及列表',
  }),['https://example.org/guide#missing-values','https://example.org/guide#categorical-inputs']);
  assert.deepEqual(links({citation:'[Paper](https://example.org/paper)，另见《https://example.org/doi/(2020)123》。'}),[
    'https://example.org/paper','https://example.org/doi/(2020)123',
  ]);
  assert.deepEqual(links({citation:'https://example.org/文献?q=a,b&section=2#结果'}),[
    new URL('https://example.org/文献?q=a,b&section=2#结果').href,
  ]);
});

test('late responses cannot render into a newly selected option; evidence reads do not write',async()=>{
  let resolveA, resolveB;
  const nodes=[], requests=[];
  const root={addEventListener(){},querySelectorAll(selector){return selector==='.ce-review'?nodes:[];}};
  const controller=create({root,markdown:markdown.render,api:url=>{
    requests.push(url);
    return new Promise(resolve=>{if(url.endsWith('=0'))resolveA=resolve;else resolveB=resolve;});
  }});
  const boxA={innerHTML:''}, boxB={innerHTML:''};
  const node=(option,box)=>({isConnected:true,dataset:{evidenceId:'B-000001',evidenceRevision:'1',evidenceOption:String(option)},querySelector:()=>box});
  const a=node(0,boxA),b=node(1,boxB);
  nodes.push(a); controller.hydrateAll();
  a.isConnected=false;nodes.splice(0,1,b);controller.hydrateAll();
  resolveB({...payload,option:1,claims:[],sources:[three]});
  await new Promise(setImmediate);
  resolveA(payload);await new Promise(setImmediate);
  assert.equal(boxA.innerHTML,'');
  assert.match(boxB.innerHTML,/Source 000003/);
  assert.doesNotMatch(boxB.innerHTML,/Source 000001/);
  assert.deepEqual(requests,['/api/review-evidence/B-000001?option=0','/api/review-evidence/B-000001?option=1']);
});

test('mixed direct sources and claims follow first reference order without renumbering repeats',()=>{
  const claim={path:'evidence/claims/E-000001/r000001.json',claim:'Reuse two then one',sources:[two.path,one.path]};
  const view=model({...payload,claims:[claim],references:[three.path,claim.path,two.path]});
  assert.deepEqual(view.sources.map(s=>[s.id,s.number]),[[three.id,1],[two.id,2],[one.id,3]]);
  assert.equal(view.claims[0].citations[0].number,2);
});

test('source shorthand resolves only the exact bound unique IDs and leaves code, links and unknown IDs intact',()=>{
  const {annotate}=require('../oppencouncil/assets/review_evidence.js');
  const html=annotate('<p>S2、本地S1及S-000003；S99</p><a href="/S2">S2</a><code>S1</code>',payload);
  assert.match(html,/查看依据 1/);
  assert.match(html,/本地<button[^>]+查看依据 2/);
  assert.match(html,/查看依据 3/);
  assert.match(html,/S99/);
  assert.match(html,/<a href="\/S2">S2<\/a><code>S1<\/code>/);
  const multiple=annotate('S1',{...payload,claims:[],sources:[one,s('000001',2)]});
  assert.match(multiple,/\[1 · v1\]/); assert.match(multiple,/\[2 · v2\]/);
});

test('missing reading version is explicit, and empty group choices offer F access without borrowing evidence',()=>{
  assert.match(content(payload,'evidence/sources/S-000001/r99.json'),/上次阅读的引用版本已不在/);
  const html=content({...payload,claims:[],sources:[],references:[],member_ids:['F-000047']});
  assert.match(html,/data-evidence-jump="F-000047"/);
  assert.doesNotMatch(html,/ce-source-detail|此方案引用的判断/);
});

test('reading position persists per project and question or option across controller reloads',async()=>{
  const storage=new Map();
  const old=global.localStorage;
  global.localStorage={getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)};
  try {
    let click;
    const box={innerHTML:'',focus(){}};
    const node={isConnected:true,dataset:{evidenceId:'B-000001',evidenceRevision:'1',evidenceOption:'0'},querySelector:()=>box,querySelectorAll:()=>[]};
    const root={dataset:{projectId:'p1'},contains:()=>true,addEventListener:(_,fn)=>{click=fn;},querySelectorAll:selector=>selector==='.ce-review'?[node]:[]};
    const init=()=>create({root,markdown:markdown.render,api:async()=>payload});
    init().hydrateAll(); await new Promise(setImmediate);
    const button={dataset:{evidenceSource:three.path},classList:{contains:()=>false},closest:()=>node};
    click({target:{closest:selector=>selector==='[data-evidence-source]'?button:null}});
    init().hydrateAll();await new Promise(setImmediate);
    assert.match(box.innerHTML,/ce-detail-heading">依据 \[3\]/);
    root.dataset.projectId='p2'; init().hydrateAll();await new Promise(setImmediate);
    assert.match(box.innerHTML,/ce-detail-heading">依据 \[1\]/);
    root.dataset.projectId='p1';node.dataset.evidenceOption='1';
    create({root,api:async()=>({...payload,option:1})}).hydrateAll();await new Promise(setImmediate);
    assert.match(box.innerHTML,/ce-detail-heading">依据 \[1\]/);
  } finally {global.localStorage=old;}
});

test('catalog is collapsed by default while selected full citation and exact record stay readable',()=>{
  const html=content(payload,three.path);
  assert.match(html,/<details class="ce-source-picker"><summary>/);
  assert.doesNotMatch(html,/<details class="ce-source-picker" open/);
  assert.match(html,/全部 3 条依据/);
  assert.match(html,/ce-detail-heading">依据 \[3\]/);
  assert.match(html,new RegExp(three.path.replaceAll('.','\\.')));
  assert.ok(html.indexOf('</details><article class="ce-source-detail"')>0);
});

test('refresh restores source detail scroll without moving the source catalog',async()=>{
  const handlers={}, box={innerHTML:''}, picker={open:false};
  let node;
  const detail={scrollTop:0,classList:{contains:name=>name==='ce-source-detail'},closest:()=>node};
  node={isConnected:true,dataset:{evidenceId:payload.id,evidenceRevision:String(payload.revision),evidenceOption:String(payload.option)},querySelector:s=>s==='.ce-content'?box:s==='.ce-source-detail'?detail:s==='.ce-source-picker'?picker:null,querySelectorAll:()=>[]};
  const root={dataset:{projectId:'scroll-test'},addEventListener:(name,fn)=>handlers[name]=fn,querySelectorAll:s=>s==='.ce-review'?[node]:[]};
  const ui=create({root,api:async()=>payload});
  ui.hydrateAll();await new Promise(setImmediate);
  detail.scrollTop=240;handlers.scroll({target:detail});
  detail.scrollTop=0;
  ui.hydrateAll();await new Promise(setImmediate);
  assert.equal(detail.scrollTop,240);assert.equal(picker.open,false);
});

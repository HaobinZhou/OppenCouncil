const {test}=require('node:test');
const assert=require('node:assert/strict');
const tables=require('../oppencouncil/assets/tables.js');
const markdown=require('../oppencouncil/assets/markdown.js');
function table(){return {schema_version:1,id:'baseline',title:'模拟基线表',simulated:true,
 columns:[{id:'a',label:'方案 A'},{id:'b',label:'方案 B'}],
 headers:[{id:'treatment',label:'治疗组',children:[{id:'ha',label:'方案 A',column_id:'a'},{id:'hb',label:'方案 B',column_id:'b'}]}],
 rows:[{id:'age',label:'年龄',cells:{}},{id:'mean',parent_id:'age',label:'均值',cells:{a:'62',b:'63'}}],
 footnotes:[{id:'n',text:'均值，岁',refs:[{row_id:'mean',column_id:'a'}]}]};}
const source=t=>'Before unchanged\n\n```table\n'+JSON.stringify(t)+'\n```\n\nAfter unchanged\n';
test('multilevel headers, row groups, notes and simulation label render without executing content',()=>{
 const t=table();t.title='<script>alert(1)</script>';
 const html=markdown.render(source(t));
 assert.match(html,/colspan="2"/);assert.match(html,/rowspan="2"/);assert.match(html,/模拟数据，仅示意/);
 assert.match(html,/padding-left:1.6em/);assert.match(html,/<sup>1<\/sup>/);assert.match(html,/均值，岁/);
 assert.doesNotMatch(html,/<script>/);assert.match(html,/&lt;script&gt;/);
 assert.doesNotMatch(html,/<input/);
});
test('row/column edits preserve surrounding Markdown and remove dangling references',()=>{
 let text=source(table());text=tables.edit(text,0,'add-column');text=tables.edit(text,0,'add-row');
 text=tables.edit(text,0,'header',{header:'ha',value:'修订标题'});
 text=tables.edit(text,0,'cell',{row:'mean',column:'a',value:'61.5'});
 assert.equal(tables.blocks(text)[0].value.rows[1].cells.a,'61.5');
 text=tables.edit(text,0,'remove-column',{column:'a'});
 text=tables.edit(text,0,'remove-row',{row:'age'});
 const t=tables.blocks(text)[0].value;
 assert.equal(t.rows[0].parent_id,undefined);assert.equal(t.rows[0].cells.a,undefined);
 assert.deepEqual(t.footnotes[0].refs,[]);
 assert.ok(text.startsWith('Before unchanged\n\n'));assert.ok(text.endsWith('\n\nAfter unchanged\n'));
 tables.validate(t);
});
test('footnote objects mark row, column or cell and invalid shapes are rejected',()=>{
 const t=table();t.footnotes=[
  {id:'row',text:'row note',refs:[{row_id:'mean'}]},
  {id:'column',text:'column note',refs:[{column_id:'a'}]},
  {id:'cell',text:'cell note',refs:[{row_id:'mean',column_id:'b'}]}];
 const html=tables.render(t);
 assert.match(html,/方案 A<sup>2<\/sup>/);assert.match(html,/均值<sup>1<\/sup>/);
 assert.match(html,/63<sup>3<\/sup>/);
 for(const refs of [['mean'],'mean',[null],[{}],[{row_id:null}],[{other:'mean'}]]) {
  const bad=table();bad.footnotes[0].refs=refs;
  assert.throws(()=>tables.validate(bad),/row_id\/column_id/);
 }
});
test('header merge/split preserves leaves and row grouping rejects forward or cyclic references',()=>{
 let text=tables.edit(source(table()),0,'ungroup-header',{header:'treatment'});
 text=tables.edit(text,0,'group-columns',{first:0,last:1,value:'合并标题'});
 assert.equal(tables.blocks(text)[0].value.headers[0].label,'合并标题');
 assert.deepEqual(tables.blocks(text)[0].value.columns.map(c=>c.id),['a','b']);
 assert.throws(()=>tables.edit(text,0,'parent',{row:'age',value:'mean'}),/之前/);
 assert.throws(()=>tables.edit(text,0,'parent',{row:'mean',value:'mean'}),/之前/);
});
test('editing one block keeps other blocks and CRLF bytes intact',()=>{
 const first=source(table()).replaceAll('\n','\r\n'), second=source({...table(),id:'second'});
 const updated=tables.edit(first+second,0,'title',{value:'Updated'});
 assert.ok(updated.endsWith(second));assert.ok(updated.startsWith('Before unchanged\r\n\r\n```table\r\n'));
 assert.equal(tables.blocks(updated)[1].value.id,'second');
 assert.equal(tables.blocks('````markdown\n```table\n{}\n```\n````').length,0);
 assert.throws(()=>tables.blocks('```table\n'+JSON.stringify(table())),/闭合/);
});
test('table editor offers row/column/header operations and validates the last row/column',()=>{
 const html=tables.editors(source(table()));
 for(const name of ['add-row','remove-row','add-column','remove-column','group-columns','ungroup-header']) assert.match(html,new RegExp('data-action="table-'+name+'"'));
 assert.match(html,/data-table-field="parent"/);
 let text=tables.edit(source(table()),0,'remove-column',{column:'a'});
 assert.throws(()=>tables.edit(text,0,'remove-column',{column:'b'}),/至少/);
});
test('only frozen hash images load inline and project URL context cannot escape',()=>{
 const hash='a'.repeat(64), image='![模拟数据，仅示意](Freeze/assets/'+hash+'.svg)', base='/api/projects/'+'b'.repeat(20)+'/assets/';
 const html=markdown.render(image,{assetBase:base});
 assert.match(html,/<img loading="lazy"/);assert.ok(html.includes('src="'+base+hash+'.svg"'));
 for(const target of ['Explore/raw.svg','Data/private.svg','https://example.org/leak.svg']) assert.doesNotMatch(markdown.render('![x]('+target+')',{assetBase:base}),/<img/);
 assert.doesNotMatch(markdown.render(image,{assetBase:'https://example.org/'}),/<img/);
 assert.doesNotMatch(markdown.render(image),/<img/);
});
test('reordering carries row groups and column cells with their stable identities',()=>{
 const t=table();t.rows.push({id:'other',label:'其他',cells:{a:'1',b:'2'}});
 let text=tables.edit(source(t),0,'move-row',{row:'age',direction:1});
 assert.deepEqual(tables.blocks(text)[0].value.rows.map(r=>r.id),['other','age','mean']);
 text=tables.edit(text,0,'move-header',{header:'hb',direction:-1});
 const moved=tables.blocks(text)[0].value;
 assert.deepEqual(moved.columns.map(c=>c.id),['b','a']);
 assert.equal(moved.rows[2].cells.a,'62');assert.equal(moved.rows[2].parent_id,'age');
 assert.deepEqual(moved.footnotes,t.footnotes);
 assert.throws(()=>tables.edit(text,0,'move-header',{header:'hb',direction:-1}),/边界/);
 assert.ok(text.startsWith('Before unchanged\n\n'));assert.ok(text.endsWith('\n\nAfter unchanged\n'));
});
test('column metadata and footnote edits round-trip and escape unsafe text',()=>{
 let text=source(table());
 for(const [key,value] of [['unit','<kg>'],['format','0.0 (SD)'],['align','right']])
  text=tables.edit(text,0,key,{column:'a',value});
 text=tables.edit(text,0,'add-footnote');
 text=tables.edit(text,0,'footnote',{note:'note-1',value:'<script>not executable</script>'});
 text=tables.edit(text,0,'remove-footnote',{note:'n'});
 const t=tables.blocks(text)[0].value,html=tables.render(t);
 assert.equal(t.columns[0].unit,'<kg>');assert.equal(t.columns[0].format,'0.0 (SD)');
 assert.deepEqual(t.footnotes,[{id:'note-1',text:'<script>not executable</script>',refs:[]}]);
 assert.match(html,/text-align:right/);assert.match(html,/&lt;kg&gt;/);assert.match(html,/0.0 \(SD\)/);
 assert.doesNotMatch(html,/<script>/);assert.doesNotMatch(html,/<input/);
 assert.throws(()=>tables.edit(text,0,'align',{column:'a',value:'right;background:red'}),/对齐/);
 assert.throws(()=>tables.validate({...t,columns:[{...t.columns[0],unit:2},t.columns[1]]}),/文字/);
});

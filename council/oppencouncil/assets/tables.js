/* Structured tables remain JSON fenced blocks in the authoritative Markdown. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./vendor/markdown-it.min.js'));
  else root.CouncilTables = factory(root.markdownit);
})(typeof globalThis !== 'undefined' ? globalThis : this, function (markdownit) {
  const md = markdownit({html:false}), esc = md.utils.escapeHtml;
  const fail = text => { throw new Error(text); };
  function validate(t) {
    if (!t || t.schema_version !== 1 || typeof t.id !== 'string' || !t.id || typeof t.title !== 'string' || !t.title.trim() || typeof t.simulated !== 'boolean') fail('表格需要标题和明确的模拟数据标记。');
    if (!Array.isArray(t.columns) || !t.columns.length || !Array.isArray(t.rows) || !t.rows.length) fail('至少保留一列和一行。');
    const cols = t.columns.map(c => c.id), rows = t.rows.map(r => r.id);
    if ([...cols,...rows].some(id => typeof id !== 'string' || !id) || new Set(cols).size !== cols.length || new Set(rows).size !== rows.length) fail('行列编号必须唯一。');
    for (const c of t.columns) {
      if (['label','format','unit'].some(k=>k in c && typeof c[k] !== 'string')) fail('列标题、格式和单位需要文字。');
      if ('align' in c && !['left','center','right'].includes(c.align)) fail('列对齐方式无效。');
    }
    const seen = new Set(), leaves = [];
    function headers(nodes, depth = 0) {
      if (!Array.isArray(nodes) || !nodes.length || depth > 8) fail('表头层次无效。');
      for (const n of nodes) {
        if (!n || typeof n.id !== 'string' || !n.id || seen.has(n.id) || typeof n.label !== 'string') fail('表头编号或标题无效。');
        seen.add(n.id);
        if (n.children) { if ('column_id' in n) fail('表头不能同时是分组和叶列。'); headers(n.children, depth + 1); }
        else leaves.push(n.column_id);
      }
    }
    headers(t.headers);
    if (JSON.stringify(leaves) !== JSON.stringify(cols)) fail('表头顺序必须对应所有列。');
    const earlier = new Set();
    for (const r of t.rows) {
      if (r.parent_id != null && !earlier.has(r.parent_id)) fail('分组行必须在子行之前。');
      if (typeof r.label !== 'string' || !r.cells || typeof r.cells !== 'object' || Array.isArray(r.cells) || Object.entries(r.cells).some(([k,v]) => !cols.includes(k) || typeof v !== 'string')) fail('表格单元格无效。');
      earlier.add(r.id);
    }
    const notes = new Set();
    for (const n of t.footnotes || []) {
      if (!n.id || notes.has(n.id) || typeof n.text !== 'string') fail('脚注无效。');
      notes.add(n.id);
      if ('refs' in n && !Array.isArray(n.refs)) fail('脚注 refs 必须是 row_id/column_id 对象数组。');
      for (const ref of n.refs || []) {
        if (!ref || typeof ref !== 'object' || Array.isArray(ref) || !Object.keys(ref).length || Object.entries(ref).some(([k,v])=>!['row_id','column_id'].includes(k) || typeof v !== 'string' || !v)) fail('脚注 refs 必须是 row_id/column_id 对象数组。');
        if ((ref.row_id && !rows.includes(ref.row_id)) || (ref.column_id && !cols.includes(ref.column_id))) fail('脚注引用不存在的行列。');
      }
    }
    return t;
  }
  function blocks(source) {
    source = String(source);
    const lines = source.match(/[^\n]*(?:\n|$)/g).filter(Boolean), offsets = [0];
    for (const line of lines) offsets.push(offsets.at(-1) + line.length);
    return md.parse(source, {}).filter(t => t.type === 'fence' && t.info.trim() === 'table').map(token => {
      const [start, end] = token.map;
      if (!new RegExp('^ {0,3}' + token.markup[0] + '{' + token.markup.length + ',}\\s*$').test(lines[end-1]?.trimEnd() || '')) fail('表格代码块尚未闭合。');
      let value;
      try { value = validate(JSON.parse(token.content)); } catch (e) { fail('表格无法编辑：' + e.message); }
      return {value, start:offsets[start], end:offsets[end], opening:lines[start], closing:lines[end-1]};
    });
  }
  function replace(source, index, value) {
    const block = blocks(source)[index];
    if (!block) fail('表格已变化，请重新打开候选。');
    validate(value);
    const newline = block.opening.endsWith('\r\n') ? '\r\n' : '\n';
    return source.slice(0,block.start) + block.opening + JSON.stringify(value,null,2).replace(/\n/g,newline) + newline + block.closing + source.slice(block.end);
  }
  const allHeaders = nodes => nodes.flatMap(n => [n,...(n.children ? allHeaders(n.children) : [])]);
  const unique = (prefix, ids) => { let n=1; while(ids.includes(prefix+n)) n++; return prefix+n; };
  function moveSibling(nodes, id, direction) {
    const i=nodes.findIndex(n=>n.id===id);
    if(i>=0) {
      const j=i+direction;
      if(j<0 || j>=nodes.length) fail('已到达当前分组边界。');
      [nodes[i],nodes[j]]=[nodes[j],nodes[i]];return true;
    }
    return nodes.some(n=>n.children && moveSibling(n.children,id,direction));
  }
  function edit(source, index, operation, values={}) {
    const t = structuredClone(blocks(source)[index]?.value || fail('表格已不存在。'));
    const headers = allHeaders(t.headers), row = t.rows.find(r=>r.id===values.row), column=t.columns.find(c=>c.id===values.column);
    if (operation === 'title') t.title=values.value;
    else if (operation === 'header') {
      const h=headers.find(h=>h.id===values.header) || fail('表头已不存在。'); h.label=values.value;
      if(h.column_id) t.columns.find(c=>c.id===h.column_id).label=values.value;
    } else if (['format','unit','align'].includes(operation)) {
      if(!column) fail('列已不存在。');
      if(values.value) column[operation]=values.value; else delete column[operation];
    } else if (operation === 'label') (row || fail('行已不存在。')).label=values.value;
    else if (operation === 'cell') { if(!row || !column) fail('单元格已不存在。'); row.cells[column.id]=values.value; }
    else if (operation === 'parent') { if(!row) fail('行已不存在。'); if(values.value) row.parent_id=values.value; else delete row.parent_id; }
    else if (operation === 'add-row') {
      const id=unique('row-',t.rows.map(r=>r.id)); t.rows.push({id,label:'新行',cells:{}});
    } else if (operation === 'remove-row') {
      if(!row) fail('行已不存在。');
      // Removing a group row retains its children at the former parent's level.
      t.rows=t.rows.filter(r=>r!==row);
      for(const r of t.rows) if(r.parent_id===row.id) { if(row.parent_id) r.parent_id=row.parent_id; else delete r.parent_id; }
      for(const n of t.footnotes || []) n.refs=(n.refs || []).filter(r=>r.row_id!==row.id);
    } else if (operation === 'add-column') {
      const id=unique('column-',t.columns.map(c=>c.id)); t.columns.push({id,label:'新列'});
      t.headers.push({id:unique('header-',headers.map(h=>h.id)),label:'新列',column_id:id});
    } else if (operation === 'remove-column') {
      if(!column) fail('列已不存在。'); t.columns=t.columns.filter(c=>c!==column);
      const prune=nodes=>nodes.flatMap(n=>n.children ? ((n.children=prune(n.children)).length ? [n] : []) : n.column_id===column.id ? [] : [n]);
      t.headers=prune(t.headers);
      for(const r of t.rows) delete r.cells[column.id];
      for(const n of t.footnotes || []) n.refs=(n.refs || []).filter(r=>r.column_id!==column.id);
    } else if (operation === 'move-row') {
      if(!row || ![-1,1].includes(Number(values.direction))) fail('行移动无效。');
      const children=parent=>t.rows.filter(r=>(r.parent_id || null)===parent).map(r=>({...r,children:children(r.id)}));
      const tree=children(null);moveSibling(tree,row.id,Number(values.direction));
      const flatten=nodes=>nodes.flatMap(({children,...r})=>[r,...flatten(children)]);
      t.rows=flatten(tree);
    } else if (operation === 'move-header') {
      if(!headers.some(h=>h.id===values.header) || ![-1,1].includes(Number(values.direction))) fail('列移动无效。');
      moveSibling(t.headers,values.header,Number(values.direction));
      t.columns=allHeaders(t.headers).filter(h=>h.column_id).map(h=>t.columns.find(c=>c.id===h.column_id));
    } else if(operation === 'group-columns') {
      const first=Number(values.first), last=Number(values.last);
      if(!Number.isInteger(first) || !Number.isInteger(last) || first<0 || last<=first || last>=t.columns.length) fail('请选择相邻的两列或更多列。');
      const ids=t.columns.slice(first,last+1).map(c=>c.id);
      const visit=nodes=>{
        const begin=nodes.findIndex(n=>n.column_id===ids[0]);
        if(begin>=0 && ids.every((id,i)=>nodes[begin+i]?.column_id===id)) {
          const children=nodes.splice(begin,ids.length);
          nodes.splice(begin,0,{id:unique('header-',headers.map(h=>h.id)),label:values.value || '分组标题',children}); return true;
        }
        return nodes.some(n=>n.children && visit(n.children));
      };
      if(!visit(t.headers)) fail('只能合并同一层的相邻叶列；请先拆分已有分组。');
    } else if(operation === 'ungroup-header') {
      const ungroup=nodes=>nodes.flatMap(n=>n.id===values.header && n.children ? n.children : n.children ? [{...n,children:ungroup(n.children)}] : [n]);
      t.headers=ungroup(t.headers);
    } else if(operation === 'footnote') {
      const n=(t.footnotes || []).find(n=>n.id===values.note) || fail('脚注已不存在。'); n.text=values.value;
    } else if(operation === 'add-footnote') {
      t.footnotes ||= [];t.footnotes.push({id:unique('note-',t.footnotes.map(n=>n.id)),text:'新脚注',refs:[]});
    } else if(operation === 'remove-footnote') {
      if(!(t.footnotes || []).some(n=>n.id===values.note)) fail('脚注已不存在。');
      t.footnotes=t.footnotes.filter(n=>n.id!==values.note);
    } else fail('未知表格修改。');
    return replace(source,index,t);
  }
  function render(value, {editable=false,index=0}={}) {
    const t=validate(value), attrs=' data-table-index="'+index+'"';
    const input=(field,value,extra='')=>'<input data-table-field="'+field+'"'+attrs+extra+' aria-label="'+esc(({title:'表格标题',header:'列标题',label:'行标题',format:'列格式',unit:'列单位',footnote:'脚注'})[field] || '单元格')+'" value="'+esc(value)+'">';
    const action=(name,label,extra='')=>'<button type="button" class="sw2-table-action" data-action="table-'+name+'"'+attrs+extra+'>'+label+'</button>';
    const label=(field,value,extra='')=>editable?input(field,value,extra):esc(value);
    const depth=nodes=>Math.max(...nodes.map(n=>n.children?1+depth(n.children):1));
    const notes=(row,column)=> (t.footnotes || []).flatMap((n,i)=>(n.refs||[]).some(r=>r.row_id===row && (column?r.column_id===column:!r.column_id)) ? ['<sup>'+(i+1)+'</sup>']:[]).join('');
    const levels=depth(t.headers), lines=Array.from({length:levels},()=>[]);
    const leaves=n=>n.children?n.children.reduce((sum,c)=>sum+leaves(c),0):1;
    const visit=(nodes,level)=>nodes.forEach(n=>{
      const c=t.columns.find(c=>c.id===n.column_id), key=' data-table-header="'+esc(n.id)+'"';
      const meta=c?(editable?'<div class="sw2-table-column-tools"><label>单位 '+input('unit',c.unit || '',' data-table-column="'+esc(c.id)+'"')+'</label><label>格式 '+input('format',c.format || '',' data-table-column="'+esc(c.id)+'"')+'</label><label>对齐 <select aria-label="列对齐" data-table-field="align"'+attrs+' data-table-column="'+esc(c.id)+'">'+[['left','左'],['center','中'],['right','右']].map(([v,l])=>'<option value="'+v+'"'+((c.align || 'left')===v?' selected':'')+'>'+l+'</option>').join('')+'</select></label></div>':(c.unit?'<span class="sw2-table-unit">'+esc(c.unit)+'</span>':'')+(c.format?'<small class="sw2-table-format">'+esc(c.format)+'</small>':'')):'';
      lines[level].push('<th scope="'+(n.children?'colgroup':'col')+'" colspan="'+leaves(n)+'" rowspan="'+(n.children?1:levels-level)+'">'+label('header',n.label,key)+(c?notes(undefined,c.id):'')+meta+(editable?'<div class="sw2-table-row-tools">'+action('move-header','←',key+' data-table-direction="-1"')+action('move-header','→',key+' data-table-direction="1"')+(n.children?action('ungroup-header','拆分',key):'')+'</div>':'')+'</th>');
      if(n.children)visit(n.children,level+1);
    }); visit(t.headers,0);
    const head='<thead>'+lines.map((cells,i)=>'<tr>'+(i===0?'<th scope="col" rowspan="'+levels+'">项目</th>':'')+cells.join('')+'</tr>').join('')+'</thead>';
    const parents=new Map(t.rows.map(r=>[r.id,r.parent_id]));
    const indent=r=>{let n=0,p=r.parent_id;while(p){n++;p=parents.get(p);}return n;};
    const body='<tbody>'+t.rows.map((r,i)=>'<tr><th scope="row" style="padding-left:'+(.6+indent(r))+'em">'+label('label',r.label,' data-table-row="'+esc(r.id)+'"')+notes(r.id)+
      (editable?'<div class="sw2-table-row-tools"><select aria-label="行分组" data-table-field="parent"'+attrs+' data-table-row="'+esc(r.id)+'"><option value="">无分组</option>'+t.rows.slice(0,i).map(p=>'<option value="'+esc(p.id)+'"'+(r.parent_id===p.id?' selected':'')+'>'+esc(p.label)+'</option>').join('')+'</select>'+action('move-row','↑',' data-table-row="'+esc(r.id)+'" data-table-direction="-1"')+action('move-row','↓',' data-table-row="'+esc(r.id)+'" data-table-direction="1"')+action('remove-row','删除行',' data-table-row="'+esc(r.id)+'"')+'</div>':'')+'</th>'+t.columns.map(c=>'<td style="text-align:'+(c.align || 'left')+'">'+label('cell',r.cells[c.id]||'',' data-table-row="'+esc(r.id)+'" data-table-column="'+esc(c.id)+'"')+notes(r.id,c.id)+'</td>').join('')+'</tr>').join('')+'</tbody>';
    const foot=editable?'<tfoot><tr><td></td>'+t.columns.map(c=>'<td>'+action('remove-column','删除列',' data-table-column="'+esc(c.id)+'"')+'</td>').join('')+'</tr></tfoot>':'';
    const options=t.columns.map((c,i)=>'<option value="'+i+'">'+esc(c.label || c.id)+'</option>').join('');
    const toolbar=editable?'<div class="sw2-table-toolbar">'+action('add-row','＋ 行')+action('add-column','＋ 列')+action('add-footnote','＋ 脚注')+'<label>合并表头 <select data-table-first="'+index+'" aria-label="起始列">'+options+'</select> 至 <select data-table-last="'+index+'" aria-label="结束列">'+options+'</select></label>'+action('group-columns','合并')+'</div>':'';
    return '<figure class="sw2-structured-table"'+attrs+'><figcaption>'+label('title',t.title)+' '+(t.simulated?'<span class="sw2-simulated">模拟数据，仅示意</span>':'')+'</figcaption>'+toolbar+'<div class="sw2-markdown-table" tabindex="0" role="region" aria-label="'+esc(t.title)+'"><table>'+head+body+foot+'</table></div>'+((t.footnotes||[]).length?'<ol class="sw2-table-notes">'+t.footnotes.map(n=>'<li>'+label('footnote',n.text,' data-table-note="'+esc(n.id)+'"')+(editable?action('remove-footnote','删除脚注',' data-table-note="'+esc(n.id)+'"'):'')+'</li>').join('')+'</ol>':'')+'</figure>';
  }
  function editors(source) {
    try { return blocks(source).map((b,index)=>render(b.value,{editable:true,index})).join(''); }
    catch(e) { return '<p role="alert" class="sw2-table-error">'+esc(e.message)+' 请在下方原文中修正。</p>'; }
  }
  return {validate,blocks,replace,edit,render,editors};
});

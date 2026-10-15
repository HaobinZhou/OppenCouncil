/* Evidence display is scoped to one question or one explicitly selected option. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.CouncilEvidence = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
  const types = {method_guideline:'方法指南',reporting_guideline:'报告指南',comparable_study:'同类研究',method_paper:'方法文献',project_experience:'项目经验',project_fact:'项目事实',engineering_constraint:'实现依据'};
  const checks = {full_text_location:'已核对原文位置',abstract_only:'仅阅读摘要',model_claim_only:'仅有模型陈述',code_check:'已核查代码',data_check:'已核查数据',measurement:'已实测'};

  function model(payload) {
    const available = new Map((payload.sources || []).map(source => [source.path, source]));
    const numbers = new Map(), ordered = [];
    const add = path => {
      if (!numbers.has(path)) { numbers.set(path, numbers.size + 1); ordered.push({path, number:numbers.get(path), ...available.get(path)}); }
      return numbers.get(path);
    };
    const claimsByPath = new Map((payload.claims || []).map(c=>[c.path,c]));
    const claims = [], entries = [], seenClaims = new Set();
    const addClaim = claim => {
      if (seenClaims.has(claim)) return;
      seenClaims.add(claim);
      const item = {...claim,
        citations:[...new Set(claim.sources || [])].map(path=>({path,number:add(path)})),
        counters:[...new Set(claim.counter_sources || [])].map(path=>({path,number:add(path)})),
      };
      claims.push(item); entries.push({claim:item});
    };
    if (payload.references) {
      for (const path of payload.references) {
        if (claimsByPath.has(path)) addClaim(claimsByPath.get(path));
        else if (path.startsWith('evidence/sources/')) entries.push({citation:{path,number:add(path)}});
      }
    } else {
      for (const claim of payload.claims || []) addClaim(claim);
    }
    for (const source of payload.sources || []) {
      if (!numbers.has(source.path)) entries.push({citation:{path:source.path,number:add(source.path)}});
    }
    return {claims, sources:ordered, numbers, entries};
  }

  function links(source) {
    const matches = [source.citation, source.location].filter(Boolean).join(' ').match(/https?:\/\/[^\s<>"'）】]+/g) || [];
    const unique = [];
    for (let value of matches) {
      value = value.replace(/[.,;，。；]+$/, '');
      if (value.endsWith(')') && !value.includes('(')) value = value.slice(0,-1);
      try {
        const url = new URL(value);
        if (!['http:','https:'].includes(url.protocol) || url.username || url.password) continue;
        if (!unique.includes(url.href)) unique.push(url.href);
      } catch (_) { /* Malformed citations remain readable text. */ }
    }
    return unique;
  }

  const cite = ref => '<button type="button" class="ce-citation" data-evidence-source="'+escape(ref.path)+'" aria-label="查看依据 '+ref.number+'">['+ref.number+']</button>';

  function judgments(payload, markdown = text=>escape(text)) {
    const view=model(payload);
    return view.entries.map(entry => entry.claim ? '<article class="ce-claim"><div class="sw2-record-body">'+markdown(entry.claim.claim)+'</div><div class="ce-citations">'+entry.claim.citations.map(cite).join('')+(entry.claim.counters.length?'<span class="ce-counter">相反或限制性依据</span>'+entry.claim.counters.map(cite).join(''):'')+'</div></article>' : cite(entry.citation)).join('');
  }

  function content(payload, selectedPath, markdown = text => escape(text)) {
    const view = model(payload), selected = view.sources.find(s=>s.path===selectedPath) || view.sources[0];
    if (!view.sources.length) return '<p class="ce-empty">'+(payload.option == null ? '此条尚未关联文献或核查依据。' : '此方案尚未关联文献或核查依据。')+'</p>'+(payload.unavailable?.length ? '<p class="ce-error">已关联的依据暂时无法读取，请刷新后重试。</p>' : '');
    const list = view.sources.map(source=>{
      const active=source.path===selected?.path;
      const related=view.claims.filter(c=>[...c.citations,...c.counters].some(r=>r.path===source.path));
      const detail = '<div class="ce-source-detail" aria-label="所选依据详情"><div class="ce-detail-heading">依据 ['+source.number+'] <span>'+escape(types[source.source_type] || '')+'</span></div>'+
        (source.verification?'<p class="ce-verification">'+escape(checks[source.verification] || source.verification)+'</p>':'')+
        related.map(claim=>'<div class="ce-related"><h5>'+(claim.counters.some(r=>r.path===source.path)?'相反或限制性依据':'支持的判断')+'</h5><div class="sw2-record-body">'+markdown(claim.claim)+'</div>'+(claim.applicability?'<h5>适用条件与边界</h5><div class="sw2-record-body">'+markdown(claim.applicability)+'</div>':'')+'</div>').join('')+
        (source.read_scope?'<h5>已核查的范围</h5><div class="sw2-record-body">'+markdown(source.read_scope)+'</div>':'')+
        (source.location?'<h5>原文位置</h5><div class="ce-location">'+escape(source.location)+'</div>':'')+
        (links(source).length?'<div class="ce-links">'+links(source).map((url,i)=>'<a href="'+escape(url)+'" target="_blank" rel="noopener noreferrer">'+(i?'原文链接 '+(i+1):'打开原文')+' ↗</a>').join(''):'')+
        (source.version?'<p class="ce-version">引用版本：'+escape(source.id)+' · 第 '+source.version+' 版'+(source.retrieved_at?'<br>核查日期：'+escape(source.retrieved_at):'')+'</p>':'')+'</div>';
      return '<article class="ce-source-record"><button type="button" class="ce-source" data-evidence-source="'+escape(source.path)+'" aria-expanded="'+active+'"><span class="ce-number">['+source.number+']</span><span><strong>'+escape(source.citation || '依据暂时无法读取')+'</strong><small>'+escape([types[source.source_type],checks[source.verification]].filter(Boolean).join(' · '))+'</small></span></button>'+(active?detail:'')+'</article>';
    }).join('');
    return (payload.unavailable?.length?'<p class="ce-error" role="status">部分已关联依据暂时无法读取；未用其他版本替代。</p>':'')+'<div class="ce-source-list" aria-label="按引用顺序排列的依据">'+list+'</div>';
  }

  function create({root, api, markdown}) {
    const cache = new Map(), selections = new Map();
    const key = (id, revision, option) => id+':'+revision+':'+(option ?? 'question');
    function shell(record, option=null, view="sources") {
      const k=key(record.id,record.revision,option), cached=cache.get(k);
      const heading=view==='judgments' ? '<h4>此方案引用的判断</h4>' : '<div class="ce-heading"><h3>'+(option==null?'参考文献与依据':'方案 '+String.fromCharCode(65+option)+' 的引用依据')+'</h3><span>按首次引用排序</span></div>';
      return '<section class="ce-review ce-'+view+'" data-evidence-view="'+view+'" data-evidence-id="'+escape(record.id)+'" data-evidence-revision="'+record.revision+'"'+(option == null?'':' data-evidence-option="'+option+'"')+'>'+heading+'<div class="ce-content" aria-live="polite">'+(cached?.payload?(view==='judgments'?judgments(cached.payload,markdown):content(cached.payload,selections.get(k),markdown)):'<p class="ce-empty" role="status">正在读取此选择的依据…</p>')+'</div></section>';

    }
    function attributes(node) {
      const id=node.dataset.evidenceId, revision=Number(node.dataset.evidenceRevision), option=node.dataset.evidenceOption===undefined?null:Number(node.dataset.evidenceOption);
      return {id,revision,option,key:key(id,revision,option)};
    }
    async function hydrate(node) {
      const context=attributes(node), k=context.key;
      let entry=cache.get(k);
      if (!entry) {
        entry={}; cache.set(k,entry);
        entry.pending=api('/api/review-evidence/'+context.id+(context.option==null?'':'?option='+context.option)).then(payload=>{
          if (payload.id!==context.id || payload.revision!==context.revision || payload.option!==context.option) throw new Error('项目记录已更新，请刷新项目记录后查看依据。');
          entry.payload=payload; return payload;
        }).catch(error=>{cache.delete(k); throw error;});
      }
      try {
        const payload=entry.payload || await entry.pending;
        if (node.isConnected && attributes(node).key===k) node.querySelector('.ce-content').innerHTML=node.dataset.evidenceView==='judgments'?judgments(payload,markdown):content(payload,selections.get(k),markdown);
      } catch (_) {
        if (node.isConnected && attributes(node).key===k) node.querySelector('.ce-content').innerHTML='<p class="ce-error" role="status">依据暂时无法读取，或记录已更新。请刷新项目记录后重试。</p>';
      }
    }
    function hydrateAll() { for (const node of root.querySelectorAll('.ce-review')) hydrate(node); }
    root.addEventListener('click',event=>{
      const button=event.target.closest('[data-evidence-source]');
      if (!button || !root.contains(button)) return;
      const node=button.closest('.ce-review'), k=attributes(node).key, payload=cache.get(k)?.payload;
      if (!payload || !model(payload).sources.some(s=>s.path===button.dataset.evidenceSource)) return;
      const isCitation=button.classList.contains('ce-citation');
      selections.set(k,button.dataset.evidenceSource);
      for (const target of root.querySelectorAll('.ce-review')) {
        if (attributes(target).key!==k || target.dataset.evidenceView==='judgments') continue;
        target.querySelector('.ce-content').innerHTML=content(payload,button.dataset.evidenceSource,markdown);
        const next=[...target.querySelectorAll('.ce-source')].find(b=>b.dataset.evidenceSource===button.dataset.evidenceSource);
        if (isCitation) next?.scrollIntoView?.({block:'nearest',behavior:'auto'});
        next?.focus({preventScroll:true});
      }

    });
    return {shell,hydrateAll};
  }
  return {model,links,content,judgments,create};
});

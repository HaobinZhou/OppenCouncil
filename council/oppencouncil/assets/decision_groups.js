/* Joint review: people discuss and confirm; AI manages membership and proposals. */
window.CouncilGroups = function ({ root, state, api, refresh, render, notice, friendlyError = error => error.message, escape: esc, setDraft, getDraft, pendingQuestions, saveCandidate, discardEdits, workflowHTML = () => '', discussionResizerHTML = '', discussionShortcut = 'Ctrl+Enter', discussionShortcutAttribute = 'Control+Enter', choiceContext = scope => ({choiceScope:scope}), onOpen = () => {}, onDraftChange = () => {} }) {
  let active = null, restored = false, local = {}, failedStorage = false, busy = false;
  const views = {}, composing = {};
  let comparisons = {};
  const renderMarkdown = (text, choices = false) => window.CouncilMarkdown ? window.CouncilMarkdown.render(text, {questionIds: state.snapshot.questions.map(q => q.id), ...(choices ? choiceContext(active) : {})}) : esc(text);
  const groups = () => state.snapshot.decision_groups || [];
  const find = id => groups().find(g => g.id === id);
  const question = id => state.snapshot.questions.find(q => q.id === id);
  const key = () => 'council-groups:drafts:' + state.snapshot.project;
  const uuid = () => crypto.randomUUID ? crypto.randomUUID() : Date.now() + '-' + Math.random();
  const button = (action, text, data = '') => `<button type="button" class="sw2-button ${['post','save-candidate','approve','approve-member'].includes(action) ? 'sw2-button-primary' : 'sw2-button-outline'}" data-action="dg-${action}" ${data}>${text}</button>`;
  const status = q => ({ waiting: '等待前序', needs_review: '依据已更新 · 待复核', ready: '候选可审阅', effective: '已确认', discuss: '待讨论' })[q.readiness?.status] || '待讨论';
  const when = value => value ? new Date(value).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false }) : '';
  const actor = value => ({ user:'你', codex:'Codex', chatgpt:'ChatGPT' })[value] || '来源未记录';
  function saveLocal() {
    try { sessionStorage.setItem(key(), JSON.stringify({ active, local, comparisons })); failedStorage = false; }
    catch (_) { failedStorage = true; }
  }
  function restore() {
    if (!state.snapshot.project || restored) return;
    restored = true;
    try {
      const saved = JSON.parse(sessionStorage.getItem(key()) || '{}');
      local = saved.local || {};
      comparisons = saved.comparisons || {};
      active = Object.hasOwn(saved, "active") ? (find(saved.active) ? saved.active : null) : groups()[0]?.id || null;
    } catch (_) { failedStorage = true; }
  }
  function reconcile() {
    restore();
    for (const g of groups()) {
      const draft = local[g.id];
      if (draft?.message?.trim() && g.messages.some(m => m.id === draft.request_id && m.actor === 'user' && m.text === draft.message.trim())) {
        delete draft.message; delete draft.request_id;
      }
    }
    saveLocal();
  }
  function pending() {
    return Object.entries(local).filter(([, d]) => d.message?.trim()).map(([id]) => ({ id, title: find(id)?.title || id }));
  }
  function dependencies(q) {
    const deps = (q.readiness?.dependencies || []).filter(d => d.status === 'waiting' || d.status === 'needs_review');
    return deps.length ? '<div class="dg-dependencies">' + deps.map(d =>
      `<p><strong>${d.status === 'waiting' ? '先确认前序' : '需要复核'}：</strong>${button('question',esc(d.title),`data-id="${d.question_id}"`)} ${esc(d.reason)}${d.condition ? '<br>适用条件：'+esc(d.condition) : ''}</p>`).join('') + '</div>' : '';
  }
  function listHTML(items = state.snapshot.questions, questionHTML = q => button('question',esc(q.title),`data-id="${q.id}"`)) {
    reconcile();
    const ids = new Set(items.map(q => q.id));
    const shown = groups().filter(g => g.member_ids.some(id => ids.has(id)));
    const expanded = new Set(Array.from(root.querySelectorAll?.('.dg-member-list[open]') || []).map(e => e.dataset.group));
    if (!shown.length) return '';
    return '<section class="dg-list"><div class="dg-list-head">一起审阅</div>' + shown.map(g => {
      const missing = missingWording(g), members = g.member_ids.map(question).filter(q => ids.has(q.id));
      return `<section class="dg-nav-group"><button class="sw2-question dg-group-link" data-action="dg-open" data-id="${g.id}" aria-current="${active === g.id}"><strong>${esc(g.title)}</strong><span>${g.member_ids.length} 条口径${missing.length ? ' · '+missing.length+' 条待 AI 补齐' : ''}${local[g.id]?.message?.trim() ? ' · 未保存' : ''}</span></button><details class="dg-member-list" data-group="${g.id}"${expanded.has(g.id) || (!active && g.member_ids.includes(state.selected)) ? ' open' : ''}><summary>成员口径 · ${members.length}</summary>${members.map(questionHTML).join('')}</details></section>`;
    }).join('') + '</section>';
  }
  function missingWording(g) {
    return g.member_ids.map(question).filter(q => q?.definition?.draft
      ? !q.definition.draft.text?.trim()
      : !q?.definition?.versions?.some(v => v.number === q.definition.current_version && v.text?.trim()));
  }
  function approvalProblem(g) {
    const missing = missingWording(g);
    if (missing.length) return '请先让 AI 补齐本组候选：' + missing.map(q => q.id).join('、') + '。';
    const unsaved = pendingQuestions().filter(q => g.member_ids.includes(q.id));
    if (unsaved.length) return '请先保存本组的候选修改或留言：' + unsaved.map(q => q.id).join('、') + '。';
    if (local[g.id]?.message?.trim()) return '本组讨论有未保存留言，请先保存或清空留言，再确认。';
    return '';
  }
  function memberProblem(q) {
    if (!q.definition?.draft?.text?.trim()) return '请先补齐并保存本条候选口径。';
    if (pendingQuestions().some(p => p.id === q.id)) return '本条候选或留言有未保存修改，请先保存后确认。';
    const deps = (q.readiness?.dependencies || []).filter(d => ['waiting','needs_review'].includes(d.status));
    return deps.length ? '请先确认或复核前序口径：' + deps.map(d => d.question_id).join('、') + '。' : '';
  }
  function approvalHTML(g, location, q = null) {
    const reason = q ? memberProblem(q) : approvalProblem(g), id = 'dg-confirm-' + location;
    const hint = q ? `data-dg-member-hint="${q.id}"` : 'data-dg-confirm-hint';
    return `<div class="sw2-confirm-actions"><span id="${id}" ${hint} role="status">${esc(reason || (q ? '仅冻结本条，其他口径保持原状态' : '本组关联口径将一并生效'))}</span>${button(q ? 'approve-member' : 'approve',q ? '确认并冻结本条口径' : '确认本组 '+g.member_ids.length+' 条口径',`${q ? 'data-question="'+q.id+'" ' : ''}aria-describedby="${id}"${state.busy || reason ? ' disabled' : ''}`)}</div>`;
  }
  function memberHTML(q) {
    const d = q.definition || { versions: [], draft: null }, current = d.versions.find(v => v.number === d.current_version);
    const date = v => v.published_at ? new Date(v.published_at).toLocaleDateString('zh-CN', {year:'numeric',month:'2-digit',day:'2-digit'}) : '日期未记录';
    const versionMark = number => `<span class="sw2-version-mark" aria-label="版本 v${number}">V${number}</span>`;
    const heading = (number, draft = false) => `<div class="sw2-record-caption"><h4 class="sw2-record-heading">${esc(q.title)}</h4>${number ? `<span class="sw2-version-stack">${draft ? '<span class="sw2-draft-state">待确认</span>' : ''}${versionMark(number)}</span>` : ''}</div>`;
    const footer = (v, extra = '') => `<div class="sw2-record-end"><details class="sw2-record-details" data-record="${q.id}-meta-${v?.number || 'draft'}"><summary>详情</summary><div class="sw2-record-detail-text">编号：${q.id}<br>状态：${!v ? '候选 · 尚未生效' : v.number !== d.current_version ? '历史版本' : ['waiting','needs_review'].includes(q.readiness?.status) ? '已确认 · 依据待复核' : '当前有效'}${v ? `<br>确认人：${actor(v.published_by)}` : ''}</div>${extra}</details>${v ? `<span class="sw2-record-date">确认日期 ${esc(date(v))}</span>` : ''}</div>`;
    const old = d.versions.filter(v => v.number !== d.current_version);
    const history = old.length ? '<details class="dg-history" data-record="'+q.id+'-history"><summary>历史版本 · '+old.length+'</summary>'+[...old].reverse().map(v=>`<section class="sw2-record-revision">${heading(v.number)}<div class="dg-text sw2-record-body" data-quote-source="${q.id} · 历史口径 v${v.number}">${renderMarkdown(v.text)}</div>${footer(v)}</section>`).join('')+'</details>' : '';
    const currentReference = current ? `<details class="dg-current-reference" data-record="${q.id}-current"><summary>查看当前生效的正式口径 · v${current.number}</summary><section class="sw2-record-revision">${heading(current.number)}<div class="dg-text sw2-record-body" data-quote-source="${q.id} · 正式口径 v${current.number}">${renderMarkdown(current.text)}</div>${footer(current)}</section></details>` : '';
    const candidate = d.draft ? `<div class="dg-candidate"><div class="dg-text sw2-record-body" data-quote-source="${q.id} · 候选口径 v${d.versions.length + 1}">${renderMarkdown(d.draft.text || '等待完整候选')}</div></div><details class="dg-editor" data-record="${q.id}-editor"><summary>修改候选 · Markdown</summary><textarea aria-label="${esc(q.title)}的候选口径" class="dg-definition" data-question="${q.id}">${esc(getDraft(q.id))}</textarea><details class="sw2-markdown-preview" data-record="${q.id}-preview"><summary>预览排版（未保存）</summary><div class="sw2-record-body" data-preview="${q.id}">${renderMarkdown(getDraft(q.id))}</div></details><div class="dg-actions"><span class="dg-muted">保存后仍需确认才会生效</span>${button('save-candidate','保存候选',`data-question="${q.id}"`)}</div></details>` : '';
    const body = d.draft ? candidate + footer(null, currentReference + history) : current ? `<div class="dg-text sw2-record-body" data-quote-source="${q.id} · 正式口径 v${current.number}">${renderMarkdown(current.text)}</div>${footer(current, history)}` : '<p class="dg-muted">等待 AI 根据讨论起草完整口径</p>';
    return `<article class="dg-card sw2-record" data-state="${d.draft ? 'draft' : current ? 'effective' : 'empty'}">${heading(d.draft ? d.versions.length + 1 : current?.number, Boolean(d.draft))}${dependencies(q)}${body}${d.draft ? approvalHTML(find(active), q.id, q) : ''}</article>`;
  }
  function updateControls() {
    const postButton = root.querySelector('[data-action="dg-post"]');
    if (postButton) postButton.disabled = state.busy || !local[active]?.message?.trim();
    for (const b of root.querySelectorAll?.('[data-action="dg-save-candidate"]') || []) {
      b.disabled = state.busy || getDraft(b.dataset.question).trim() === question(b.dataset.question)?.definition?.draft?.text;
    }
    const g = find(active);
    if (g) for (const b of root.querySelectorAll?.('[data-action="dg-compare"]') || []) {
      const indices = compared(g), included = indices.includes(Number(b.dataset.option));
      b.disabled = state.busy || (!included && indices.length >= 2) || (included && indices.length === 1);
    }
    if (g) {
      const reason = approvalProblem(g);
      for (const b of root.querySelectorAll?.('[data-action="dg-approve"]') || []) {
        b.disabled = state.busy || Boolean(reason);
        b.title = reason;
      }
      for (const hint of root.querySelectorAll?.('[data-dg-confirm-hint]') || []) {
        hint.textContent = state.busy ? '正在保存，请稍候…' : reason || '本组关联口径将一并生效';
      }
    }
    for (const b of root.querySelectorAll?.('[data-action="dg-approve-member"]') || []) {
      const reason = memberProblem(question(b.dataset.question));
      b.disabled = state.busy || Boolean(reason); b.title = reason;
    }
    for (const hint of root.querySelectorAll?.('[data-dg-member-hint]') || []) {
      hint.textContent = state.busy ? '正在保存，请稍候…' : memberProblem(question(hint.dataset.dgMemberHint)) || '仅冻结本条，其他口径保持原状态';
    }
  }
  function compared(g) {
    const signature = JSON.stringify(g.options);
    let view = comparisons[g.id];
    if (!view || view.signature !== signature || !Array.isArray(view.indices)) {
      const indices = g.options.slice(0, 2).map((_, i) => i);
      if (Number.isInteger(g.selected_option) && g.options[g.selected_option] && !indices.includes(g.selected_option)) indices[indices.length - 1] = g.selected_option;
      view = comparisons[g.id] = { signature, indices };
    }
    view.indices = [...new Set(view.indices)].filter(i => Number.isInteger(i) && g.options[i]).slice(0, 2);
    if (!view.indices.length && g.options.length) view.indices = [0];
    return view.indices;
  }
  function comparisonHTML(g, qs) {
    const indices = compared(g);
    const each = fn => indices.map((i, slot) => fn(g.options[i], i, slot)).join('');
    const cell = (o, i, slot, content, extra = '', label = '', sourceId = '') => `<div class="dg-option-cell ${extra}" data-quote-source="${esc(g.id+(sourceId ? ' · '+sourceId : '')+' · 方案 '+String.fromCharCode(65+i)+' · '+o.label+(label ? ' · '+label : ''))}" data-option="${i}" data-tone="${i}" data-chosen="${g.selected_option === i}" style="--order:${slot}"${label ? ` data-label="${esc(label)}"` : ''}>${content}</div>`;
    const row = (title, value, id = '') => `<div class="dg-option-label">${esc(title)}${id ? '<small>'+esc(id)+'</small>' : ''}</div>` + each((o,i,slot) => cell(o,i,slot,renderMarkdown(value(o), true), '', title, id));
    const heads = '<div class="dg-option-label">可选方案</div>' + each((o,i,slot) => cell(o,i,slot,`<span class="dg-option-letter">${String.fromCharCode(65+i)}</span>${g.selected_option === i ? '<span class="dg-preference">此前记录的偏好</span>' : ''}<h4>${esc(o.label)}</h4>`, 'dg-option-head'));
    const rows = qs.map(q => row(q.title, o => o.rules[q.id], q.id)).join('') + row('实际影响',o => o.consequences) + row('条件与代价',o => o.tradeoffs);
    const feet = '<div class="dg-option-label"></div>' + each((o,i,slot) => cell(o,i,slot,button('choose','倾向此方案',`data-option="${i}"`), 'dg-option-foot'));
    const picker = g.options.length > 2 ? `<details class="dg-comparison-picker" data-record="compare-options"><summary>选择比较方案 <span>展示 ${indices.length} / ${g.options.length}</span></summary><div class="dg-picker-body"><p>最多同时比较 2 个方案。先取消一项，即可选入其他方案；这里仅调整展示。</p><div class="dg-picker-options" role="group" aria-label="选择比较方案">${g.options.map((o,i) => button('compare',`<span class="dg-picker-check" aria-hidden="true">${indices.includes(i) ? '✓' : '+'}</span><span><b>${String.fromCharCode(65+i)} · ${esc(o.label)}</b>${g.selected_option === i ? '<small>此前记录的偏好</small>' : ''}</span>`,`data-option="${i}" role="checkbox" aria-checked="${indices.includes(i)}"${(!indices.includes(i) && indices.length >= 2) || (indices.includes(i) && indices.length === 1) ? ' disabled' : ''}`)).join('')}</div></div></details>` : '';
    return picker + `<div class="dg-options"><div class="dg-matrix" style="--option-count:${indices.length};--matrix-min:${130+indices.length*167}px">${heads}${rows}${feet}</div></div>`;
  }
  function renderDetail(panel) {
    if (!active) { panel.dataset.view = 'question'; return false; }
    const g = find(active);
    if (!g) { active = null; return false; }
    const same = panel.dataset.view === 'group' && panel.dataset.group === active;
    const scrollPositions = ['.sw2-work-in','.dg-options-section','.dg-wording-column','.dg-thread'].map(selector => [selector, same ? panel.querySelector(selector)?.scrollTop || 0 : 0]);
    const expanded = same ? Array.from(panel.querySelectorAll?.('details[data-record][open]') || []).map(e => e.dataset.record) : [];
    panel.dataset.view = 'group'; panel.dataset.group = active; panel.dataset.question = '';
    if (!same) panel.scrollTop = 0;
    const qs = g.member_ids.map(question), draft = local[g.id] || {};
    const hasDraft = qs.some(q => q.definition?.draft), missing = missingWording(g);
    panel.dataset.wording = qs.some(q => q.definition?.draft || q.definition?.current_version) ? 'present' : 'empty';
    const allConfirmed = qs.every(q => q.definition?.current_version);
    const options = g.options.length ? `<section class="dg-options-section" aria-label="方案比较"><div class="dg-column-head"><h3>方案比较</h3><span>表达偏好后，仍需确认完整口径</span></div><div class="dg-comparison">${comparisonHTML(g,qs)}</div></section>` : '';
    const wording = `<section class="dg-wording-column" aria-label="本组口径"><div class="dg-column-head"><h3>${hasDraft ? '候选口径' : allConfirmed ? '正式口径' : '候选尚未备齐'}</h3>${hasDraft ? button('discard',allConfirmed ? '取消修订' : '撤回候选') : allConfirmed ? button('begin','修订口径') : ''}</div><div class="dg-members">${missing.length ? `<div class="dg-preparation"><strong>待 AI 补齐 ${missing.length} 条候选口径</strong><p>${missing.map(q => esc(q.id+' · '+q.title)).join('<br>')}</p><p>本组尚未准备好交付确认。完整候选需要写好并核对后，再请你审阅。</p></div>` : ''}${qs.map(memberHTML).join('')}</div><div class="dg-confirm" data-effective="${allConfirmed && !hasDraft}">${hasDraft && !missing.length ? approvalHTML(g, 'group') : '<span>'+ (allConfirmed ? '本组口径已确认' : '完整候选准备好后可确认')+'</span>'}</div></section>`;
    const messages = g.messages.map(m => `<article class="sw2-bubble sw2-bubble-${['user','chatgpt'].includes(m.actor) ? m.actor : 'ai'}"><div class="sw2-bubble-head"><strong>${actor(m.actor)}</strong><span>${esc(when(m.at))}${m.question_id ? ' · '+esc(question(m.question_id)?.title || m.question_id) : ''}</span></div><div class="sw2-bubble-body" data-quote-source="${esc(g.id+' · '+actor(m.actor)+' · '+when(m.at))}">${renderMarkdown(m.text, true)}</div></article>`).join('') || '<div class="sw2-empty"><strong>开始共同讨论</strong>比较方案后，在这里留下你的意见。</div>';
    panel.innerHTML = `<div class="sw2-work"><div class="sw2-work-in"><header class="dg-header"><div class="sw2-detail-top"><span>${esc(g.id)} · ${qs.length} 条关联口径</span><span>第 ${state.snapshot.round || 1} 轮</span></div><h2>${esc(g.title)}</h2><p>${esc(g.purpose)}</p>${workflowHTML(qs)}</header><div class="dg-layout${g.options.length ? ' dg-with-options' : ''}">${options}${wording}</div></div></div><aside class="sw2-discussion-column dg-conversation" aria-label="共同讨论">${discussionResizerHTML}<div class="sw2-talk-header"><div class="sw2-section-title">共同讨论<small>${g.messages.length} 条记录</small></div><p>建议与交流 · 保存后手动通知 AI 继续</p></div><div class="dg-thread" tabindex="0" aria-label="共同讨论记录">${messages}</div><div class="dg-discussion">${button('compose','＋ 写讨论留言','hidden')}<div class="dg-message-editor"><div class="sw2-compose-head"><label for="dg-message">讨论留言 · Markdown</label>${button('close-compose','收起')}</div><textarea id="dg-message" aria-label="讨论意见" placeholder="写下你的意见，或指出哪条口径需要修改…">${esc(draft.message || '')}</textarea><details class="sw2-discussion-preview" data-record="discussion-preview"><summary>预览讨论（未保存）</summary><div id="dg-message-preview">${renderMarkdown(draft.message || '', true)}</div></details><div class="dg-actions"><span id="dg-message-state">${draft.message?.trim() ? '留言未保存' : ''}</span><small class="sw2-shortcut">${discussionShortcut} 保存</small>${button('post','保存讨论',`aria-keyshortcuts="${discussionShortcutAttribute}"`)}</div></div></div></aside>`;
    for (const el of panel.querySelectorAll?.('details[data-record]') || []) el.open = expanded.includes(el.dataset.record);
    for (const [selector, top] of scrollPositions) { const el = panel.querySelector(selector); if (el) el.scrollTop = top; }
    updateControls();
    return true;
  }
  async function mutate(id, operation, value, request) {
    const g = find(id);
    const payload = { operation, value, expected_revision: g.revision, request_id: request || uuid() };
    const data = await api('/api/groups/' + id + '/change', payload);
    state.snapshot = data.snapshot; active = data.group.id;
    return data.group;
  }
  async function post(id) {
    const d = local[id]; if (!d?.message?.trim()) throw new Error('请先写下讨论内容。');
    d.request_id ||= uuid(); saveLocal();
    const sentRequest = d.request_id, sentText = d.message;
    await mutate(id, 'comment', { text: sentText.trim(), question_id: d.target || null }, sentRequest);
    if (d.request_id === sentRequest && d.message === sentText) { delete d.message; delete d.request_id; }
    saveLocal();
  }
  async function saveAll() {
    for (const [id,d] of Object.entries(local)) if (d.message?.trim()) await post(id);
  }
  function appendDiscussion(text, quoteSource) {
    if (!find(active)) return;
    local[active] ||= {};
    local[active].message = quoteSource ? window.CouncilMarkdown.appendQuote(local[active].message, quoteSource, text) : window.CouncilMarkdown.appendPreference(local[active].message, text);
    local[active].request_id = uuid(); saveLocal(); composing[active] = true;
    const area = root.querySelector('#dg-message'); area.value = local[active].message;
    root.querySelector('#dg-message-preview').innerHTML = renderMarkdown(area.value, true);
    root.querySelector('.dg-message-editor').hidden = false;
    root.querySelector('[data-action="dg-compose"]').hidden = true;
    root.querySelector('#dg-message-state').textContent = '留言未保存';
    updateControls(); onDraftChange(); area.focus?.({preventScroll:true});
  }
  root.addEventListener('input', event => {
    const el = event.target;
    if (el.classList.contains('dg-definition')) { root.querySelector('[data-preview="'+el.dataset.question+'"]').innerHTML = renderMarkdown(el.value); setDraft(el.dataset.question, el.value); return; }
    if (el.id !== 'dg-message' || !active) return;
    local[active] ||= {}; local[active].message = el.value;
    root.querySelector('#dg-message-preview').innerHTML = renderMarkdown(el.value, true);
    local[active].request_id = uuid(); saveLocal();
    root.querySelector('#dg-message-state').textContent = el.value.trim() ? '留言未保存' : '';
    updateControls();
  });
  root.addEventListener('click', async event => {
    const b = event.target.closest('[data-action]'); if (!b || !root.contains(b)) return;
    const action = b.dataset.action;
    if (action === 'select') { active = null; saveLocal(); return; }
    if (!action.startsWith('dg-')) return;
    event.stopImmediatePropagation(); if (busy || state.busy) return;
    if (action === 'dg-open') { active = b.dataset.id; if (b.dataset.mode) views[active] = b.dataset.mode; saveLocal(); state.mobileView = 'detail'; render(); if (b.dataset.reading) { root.querySelector('#sw2-detail').dataset.reading = b.dataset.reading; render(); } onOpen(); return; }
    if (action === 'dg-question') { active = null; state.selected = b.dataset.id; state.mobileView = 'detail'; saveLocal(); render(); onOpen(); return; }
    if (action === 'dg-compare') {
      const g = find(active), index = Number(b.dataset.option), indices = compared(g);
      if (!g.options[index] || (!indices.includes(index) && indices.length >= 2) || (indices.includes(index) && indices.length === 1)) return;
      comparisons[g.id].indices = indices.includes(index) ? indices.filter(i => i !== index) : [...indices, index].sort((a,b) => a-b);
      saveLocal();
      const holder = root.querySelector('.dg-comparison');
      if (holder) {
        holder.innerHTML = comparisonHTML(g, g.member_ids.map(question));
        const picker = holder.querySelector?.('details'); if (picker) picker.open = true;
        holder.querySelector?.('[data-action="dg-compare"][data-option="'+index+'"]')?.focus?.({ preventScroll:true });
        if (!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) holder.querySelector?.('.dg-matrix')?.animate?.([{opacity:.5,transform:'translateY(4px)'},{opacity:1,transform:'translateY(0)'}],{duration:180,easing:'ease-out'});
      }
      return;
    }
    if (action === 'dg-view') { views[active] = b.dataset.mode; render(); const scroll = root.querySelector(views[active] === 'options' ? '.dg-options' : '.dg-thread'); if (scroll) scroll.scrollTop = 0; return; }
    if (action === 'dg-compose' || action === 'dg-close-compose') { composing[active] = action === 'dg-compose'; root.querySelector('.dg-message-editor').hidden = !composing[active]; root.querySelector('[data-action="dg-compose"]').hidden = composing[active]; if (composing[active]) root.querySelector('#dg-message').focus(); return; }
    if (action === 'dg-choose') {
      const g = find(active), index = Number(b.dataset.option), option = g.options[index];
      if (!option) return;
      const text = '倾向方案：'+option.label+'（尚未确认口径）';
      local[active] ||= {};
      // Preserve the person's own prose; repeated clicks on the same option do not duplicate it.
      const message = local[active].message || '';
      if (!message.split('\n').includes(text)) local[active].message = [message,text].filter(Boolean).join('\n');
      local[active].request_id = uuid(); saveLocal(); composing[active] = true;
      const area = root.querySelector('#dg-message'); area.value = local[active].message;
      root.querySelector('#dg-message-preview').innerHTML = renderMarkdown(area.value, true);
      root.querySelector('.dg-message-editor').hidden = false;
      root.querySelector('[data-action="dg-compose"]').hidden = true;
      root.querySelector('#dg-message-state').textContent = '留言未保存';
      updateControls(); onDraftChange(); area.focus?.({ preventScroll:true });
      notice('偏好已填入讨论框，可修改后点击保存讨论。', 'info'); return;
    }
    if (!['dg-post','dg-save-candidate','dg-begin','dg-discard','dg-approve','dg-approve-member'].includes(action)) return;
    const g = find(active);
    busy = true; state.busy = true; b.disabled = true;
    const label = b.textContent;
    if (action === 'dg-discard') b.textContent = '取消中…';
    if (action === 'dg-approve' || action === 'dg-approve-member') b.textContent = '确认中…';
    updateControls();
    for (const field of root.querySelectorAll?.('.dg-definition') || []) field.readOnly = true;
    try {
      if (action === 'dg-save-candidate') {
        await saveCandidate(b.dataset.question);
        const editor = root.querySelector('[data-record="'+b.dataset.question+'-editor"]');
        if (editor) editor.open = false;
      }
      if (action === 'dg-post') { await post(active); composing[active] = false; views[active] = 'discussion'; }
      if (action === 'dg-begin') await mutate(active, 'begin', null);
      if (action === 'dg-discard') await mutate(active, 'discard', { token: g.approval_token, edits: discardEdits(g.member_ids) });
      if (action === 'dg-approve-member') {
        const q = question(b.dataset.question), reason = memberProblem(q);
        if (reason) throw new Error(reason);
        await api('/api/questions/' + q.id + '/change', { operation:'definition_approve', value:q.definition.draft.approval_token || q.definition.draft.text_sha256, expected_revision:q.revision, request_id:uuid() });
      }
      if (action === 'dg-approve') {
        const reason = approvalProblem(g);
        if (reason) throw new Error(reason);
        await mutate(active, 'approve', g.approval_token);
      }
      await refresh();
      notice(({ 'dg-save-candidate':'候选已保存，确认前原口径继续有效。', 'dg-approve-member':b.dataset.question+' 已冻结；其他口径保持原状态。', 'dg-approve':'本组口径已生效，各条版本已保存。', 'dg-begin':'修订已开启，原正式版本继续有效。', 'dg-discard':'已取消修订，候选内容已留存；原正式口径和讨论未变。' })[action] || '讨论已保存。');
    } catch (error) { notice('操作未完成：'+friendlyError(error), 'error'); }
    finally {
      b.textContent = label; busy = false; state.busy = false; render();
      if (action === 'dg-post') {
        const scroll = root.querySelector('.dg-thread');
        if (scroll) scroll.scrollTop = scroll.scrollHeight;
        if (action === 'dg-post') root.querySelector('#dg-message')?.focus?.({ preventScroll: true });
      }
    }
  });
  return { listHTML, renderDetail, dependencies, pending, saveAll, reconcile, updateControls, appendDiscussion,
    message: id => local[id]?.message || '',
    openDiscussion: id => { active = id; views[id] = 'discussion'; composing[id] = true; saveLocal(); render(); onOpen(); root.querySelector('#dg-message')?.focus(); },
    select: id => { active = find(id) ? id : null; saveLocal(); },
    selected: () => find(active), clear: () => { active = null; saveLocal(); },
    status, missing: g => missingWording(g).length, storageFailed: () => failedStorage,
    handoff: () => groups().map(g => ({ id:g.id, title:g.title, purpose:g.purpose, member_ids:g.member_ids, options:g.options, messages:g.messages, selected_option:g.selected_option })) };
};

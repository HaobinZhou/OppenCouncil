(() => {
  const root = document.getElementById("sw-freeze-v2");
  const apiPrefix = "/api/projects/" + root.dataset.projectId;
  const names = { goal: "研究目标", data: "数据与人群", time: "时间与策略", outcome: "结局与偏倚", analysis: "统计与解释", delivery: "复现与交付" };
  const colors = ["#7464ef", "#20b9d1", "#f39b35", "#ee638e", "#48bb82", "#5888ec"];
  const state = { snapshot: { round: 0, questions: [] }, selected: null, group: "all", status: "all", search: "", csrf: "", busy: false, mobileView: "list" };
  const drawerMedia = window.matchMedia("(max-width: 1279px)");
  const mobileMedia = window.matchMedia("(max-width: 680px)");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const discussionMedia = window.matchMedia('(min-width: 1024px)');
  const macKeyboard = /Mac|iPhone|iPad/.test(typeof navigator === 'undefined' ? '' : (navigator.userAgentData?.platform || navigator.platform || ''));
  const discussionShortcut = macKeyboard ? '⌘+Enter' : 'Ctrl+Enter';
  const discussionShortcutAttribute = macKeyboard ? 'Meta+Enter' : 'Control+Enter';
  const discussionWidthKey = 'oppencouncil:discussion-width:v1';
  let discussionWidth = null, discussionDrag = null;
  try {
    const saved = Number(localStorage.getItem(discussionWidthKey));
    if (Number.isFinite(saved) && saved >= 300) discussionWidth = saved;
  } catch (_) { /* Layout preferences are optional; project drafts use separate storage. */ }
  const discussionResizerHTML = '<div class="sw2-discussion-resizer" role="separator" tabindex="0" aria-label="调整讨论区宽度" aria-orientation="vertical" aria-description="拖动调整讨论宽度；双击恢复默认。方向键也可调整。"></div>';
  function discussionBounds() {
    const width = root.querySelector('#sw2-detail').getBoundingClientRect().width;
    return { min:300, max:Math.max(300, Math.floor(width * .55)) };
  }
  function applyDiscussionWidth() {
    const panel = root.querySelector('#sw2-detail');
    if (discussionWidth === null) panel.style.removeProperty('--discussion-width');
    else panel.style.setProperty('--discussion-width', discussionWidth+'px');
    const handle = panel.querySelector('.sw2-discussion-resizer');
    if (!handle || !discussionMedia.matches) return;
    const {min,max} = discussionBounds(), width = Math.round(panel.querySelector('.sw2-discussion-column').getBoundingClientRect().width);
    for (const [key,value] of Object.entries({valuemin:min,valuemax:max,valuenow:width,valuetext:width+' 像素'})) handle.setAttribute('aria-'+key, String(value));
  }
  function saveDiscussionWidth() {
    try {
      if (discussionWidth === null) localStorage.removeItem(discussionWidthKey);
      else localStorage.setItem(discussionWidthKey, String(discussionWidth));
    } catch (_) { /* Resizing remains usable when browser preference storage is unavailable. */ }
  }
  function resizeDiscussion(width) {
    const {min,max} = discussionBounds();
    discussionWidth = Math.round(Math.max(min, Math.min(max, width)));
    applyDiscussionWidth();
  }
  function endDiscussionDrag(cancel = false) {
    if (!discussionDrag) return;
    const {pointerId,previous,handle} = discussionDrag; discussionDrag = null;
    delete root.dataset.resizingDiscussion;
    if (cancel) { discussionWidth = previous; applyDiscussionWidth(); }
    else saveDiscussionWidth();
    if (handle.hasPointerCapture?.(pointerId)) handle.releasePointerCapture(pointerId);
  }
  root.addEventListener('pointerdown', event => {
    if (event.target.id === 'sw2-quote-selection') { event.preventDefault(); return; }
    const handle = event.target.closest('.sw2-discussion-resizer');
    if (!handle || !discussionMedia.matches || event.button !== 0) return;
    event.preventDefault(); handle.focus({preventScroll:true});
    discussionDrag = {pointerId:event.pointerId, handle, x:event.clientX, width:root.querySelector('.sw2-discussion-column').getBoundingClientRect().width, previous:discussionWidth};
    root.dataset.resizingDiscussion = 'true'; handle.setPointerCapture(event.pointerId);
  });
  root.addEventListener('pointermove', event => {
    if (discussionDrag?.pointerId === event.pointerId) resizeDiscussion(discussionDrag.width + discussionDrag.x - event.clientX);
  });
  root.addEventListener('pointerup', event => { if (discussionDrag?.pointerId === event.pointerId) endDiscussionDrag(); });
  root.addEventListener('pointercancel', () => endDiscussionDrag(true));
  root.addEventListener('lostpointercapture', () => endDiscussionDrag());
  root.addEventListener('dblclick', event => {
    if (!event.target.closest('.sw2-discussion-resizer')) return;
    discussionWidth = null; applyDiscussionWidth(); saveDiscussionWidth();
  });
  root.addEventListener('keydown', event => {
    if (selectKey(event)) return;
    if (['sw2-message', 'dg-message'].includes(event.target.id) && event.key === 'Enter' &&
        (event.metaKey || event.ctrlKey) && !(event.metaKey && event.ctrlKey) && !event.altKey && !event.shiftKey) {
      if (event.isComposing || event.keyCode === 229) return;
      event.preventDefault();
      if (event.repeat || state.busy) return;
      const action = event.target.id === 'dg-message' ? 'dg-post' : 'post';
      const save = root.querySelector('[data-action="' + action + '"]');
      if (save && !save.disabled && event.target.value.trim()) save.click();
      return;
    }
    if (event.key === 'Escape' && discussionDrag) { event.preventDefault(); event.stopPropagation(); endDiscussionDrag(true); return; }
    if (!event.target.closest('.sw2-discussion-resizer') || !discussionMedia.matches) return;
    const {min,max} = discussionBounds(), width = root.querySelector('.sw2-discussion-column').getBoundingClientRect().width;
    if (!['ArrowLeft','ArrowRight','Home','End','Enter'].includes(event.key)) return;
    event.preventDefault();
    if (event.key === 'Enter') { discussionWidth = null; applyDiscussionWidth(); }
    else resizeDiscussion(event.key === 'Home' ? min : event.key === 'End' ? max : width + (event.key === 'ArrowLeft' ? 1 : -1) * (event.shiftKey ? 64 : 16));
    saveDiscussionWidth();
  });
  window.addEventListener('resize', () => { endDiscussionDrag(true); applyDiscussionWidth(); });
  if (window.ResizeObserver) new window.ResizeObserver(applyDiscussionWidth).observe(root.querySelector('#sw2-detail'));
  const disclosureMotions = new WeakMap();
  function setDisclosure(details, expanded) {
    const previous = disclosureMotions.get(details);
    const start = details.getBoundingClientRect().height;
    if (previous) { previous.animation.cancel(); disclosureMotions.delete(details); }
    const oldHeight = previous?.height ?? details.style.height;
    const oldOverflow = previous?.overflow ?? details.style.overflow;
    const finish = () => {
      details.open = expanded; details.style.height = oldHeight; details.style.overflow = oldOverflow;
      delete details.dataset.closing; disclosureMotions.delete(details);
    };
    if (reducedMotion.matches || !details.animate) { finish(); return; }
    details.style.height = oldHeight; details.open = true;
    details.dataset.closing = String(!expanded);
    const summary = details.querySelector('summary'), style = getComputedStyle(details);
    const end = expanded ? details.getBoundingClientRect().height : summary.getBoundingClientRect().height + ['paddingTop','paddingBottom','borderTopWidth','borderBottomWidth'].reduce((total, key) => total + (parseFloat(style[key]) || 0), 0);
    details.style.overflow = 'hidden';
    const animation = details.animate([{height:start+'px'},{height:end+'px'}], {duration:220,easing:'cubic-bezier(.22,1,.36,1)'});
    disclosureMotions.set(details, {animation, expanded, height:oldHeight, overflow:oldOverflow});
    animation.onfinish = finish;
  }
  let mobileListScroll = 0;
  const drafts = {}, messageDrafts = {}, draftBases = {}, draftRequests = {}, editing = {}, composing = {};
  const statusLabels = { candidate: "候选待确认", ready: "现在可审阅", waiting: "等待前序", needs_review: "需要复核", all: "全部状态", open: "待讨论", discussing: "讨论中", answered: "历史答复", frozen: "正式口径", historical: "历史讨论", completed: "有正式口径" };
  const matchesStatus = q => state.status === "all" || (state.status === "candidate" ? Boolean(definition(q).draft) : ["ready", "waiting", "needs_review"].includes(state.status) ? q.readiness?.status === state.status : (state.status === "completed" ? Boolean(definition(q).current_version) : state.status === "frozen" ? Boolean(definition(q).current_version) : q.status === state.status));
  let storageKey, storageOK = true, loadedDrafts = false, noticeTimer, returnFocus, leavingForDirectory = false;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let choiceProject, choiceValues = {};
  const choiceStorageKey = () => 'oppencouncil:parameter-choices:v1:' + state.snapshot.project;
  function choiceContext(scope) {
    if (choiceProject !== state.snapshot.project) {
      choiceProject = state.snapshot.project;
      try { choiceValues = JSON.parse(localStorage.getItem(choiceStorageKey()) || '{}') || {}; }
      catch (_) { choiceValues = {}; }
      if (typeof choiceValues !== 'object' || Array.isArray(choiceValues)) choiceValues = {};
    }
    return {choiceScope:scope, choiceValues};
  }
  const renderMarkdown = (text, scope) => window.CouncilMarkdown ? window.CouncilMarkdown.render(text, {questionIds: questions().map(q => q.id), ...(scope ? choiceContext(scope) : {})}) : escape(text);
  const discussionScope = () => groupUI?.selected()?.id || byId(state.selected)?.decision_group_id || state.selected;
  function updateChoiceControls() {
    for (const select of root.querySelectorAll('[data-choice-control]')) {
      const saved = choiceContext(discussionScope()).choiceValues[select.dataset.choiceKey];
      select.value = saved?.signature === select.dataset.choiceSignature ? saved.value : '';
      select.disabled = state.busy;
      select.textContent = select.value || select.dataset.choiceLabel;
      select.setAttribute('aria-label', select.dataset.choiceLabel + '：' + (select.value || '未选择'));
    }
  }
  function selectParameter(select) {
    const {choiceKey:key, choiceSignature:signature} = select.dataset;
    const [label, ...values] = JSON.parse(signature);
    if (!label || (select.value && !values.includes(select.value))) return;
    choiceContext(discussionScope());
    if (select.value) choiceValues[key] = {signature, value:select.value};
    else delete choiceValues[key];
    try { localStorage.setItem(choiceStorageKey(), JSON.stringify(choiceValues)); }
    catch (_) { showNotice('浏览器未能记住参数偏好；本次仍可添加到讨论并保存。', 'info'); }
    updateChoiceControls();
  }
  const selectPopover = root.querySelector('#sw2-select-popover');
  const selectList = root.querySelector('#sw2-select-list');
  let selectMenu = null;
  function closeSelect(restoreFocus = false) {
    const previous = selectMenu; selectMenu = null; selectPopover.hidden = true;
    if (previous) {
      previous.trigger.setAttribute('aria-expanded', 'false');
      if (restoreFocus && previous.trigger.isConnected !== false) previous.trigger.focus({preventScroll:true});
    }
  }
  function statusOptions() {
    return [['all',statusLabels.all], ...Object.entries(statusLabels).filter(([key]) => !['all','frozen'].includes(key))].map(([value,label]) => ({value,label,
      count:questions().filter(q => value === 'all' || (value === 'candidate' ? Boolean(definition(q).draft) :
        value === 'completed' ? Boolean(definition(q).current_version) : ['ready','waiting','needs_review'].includes(value) ? q.readiness?.status === value : q.status === value)).length}));
  }
  function positionSelect() {
    if (!selectMenu) return;
    const rect = selectMenu.trigger.getBoundingClientRect(), viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
    const width = viewport?.width || window.innerWidth, height = viewport?.height || window.innerHeight;
    const menuWidth = Math.min(Math.max(280, rect.width), 360, width - 24);
    selectPopover.style.width = menuWidth+'px';
    const below = top + height - rect.bottom - 20, above = rect.top - top - 20;
    const upwards = below < Math.min(360,height * .6) && above > below;
    selectPopover.style.maxHeight = Math.max(120, upwards ? above : below)+'px';
    const actualHeight = selectPopover.getBoundingClientRect().height;
    selectPopover.style.left = Math.max(left+12, Math.min(rect.left, left+width-menuWidth-12))+'px';
    selectPopover.style.top = Math.max(top+12, Math.min(upwards ? rect.top-actualHeight-8 : rect.bottom+8, top+height-actualHeight-12))+'px';
  }
  function updateSelectMenu() {
    if (!selectMenu) return;
    const {trigger,options,active,kind} = selectMenu;
    selectList.innerHTML = options.map((option,i) => '<button type="button" role="option" tabindex="-1" class="sw2-select-option" id="sw2-select-option-'+i+'" data-action="select-value" data-index="'+i+'" aria-selected="'+(trigger.value === option.value)+'" data-active="'+(active === i)+'"><span>'+escape(option.label)+'</span>'+(option.count !== undefined ? '<small>'+option.count+'</small>' : '')+'</button>').join('');
    selectList.setAttribute('aria-activedescendant','sw2-select-option-'+active);
    root.querySelector('[data-action="choice-discuss"]').disabled = state.busy || !trigger.value;
    root.querySelector('[data-action="clear-choice"]').disabled = state.busy || !trigger.value;
    root.querySelector('#sw2-select-footer').hidden = kind !== 'parameter';
    selectList.querySelector?.('[data-active="true"]')?.scrollIntoView?.({block:'nearest'});
  }
  function openSelect(trigger, last = false) {
    if (trigger.disabled || state.busy) return;
    if (selectMenu?.trigger === trigger) { closeSelect(true); return; }
    closeSelect(); hideQuote();
    const kind = trigger.id === 'sw2-status-filter' ? 'status' : 'parameter';
    const [label,...values] = kind === 'parameter' ? JSON.parse(trigger.dataset.choiceSignature) : ['按问题状态筛选'];
    const options = kind === 'parameter' ? values.map(value=>({value,label:value})) : statusOptions();
    const selectedIndex = options.findIndex(option=>option.value === trigger.value);
    selectMenu = {trigger,kind,options,active:selectedIndex >= 0 ? selectedIndex : last ? options.length - 1 : 0};
    root.querySelector('#sw2-select-title').textContent = label;
    selectPopover.hidden = false; trigger.setAttribute('aria-expanded','true');
    updateSelectMenu(); positionSelect(); selectList.focus({preventScroll:true});
    if (!reducedMotion.matches) selectPopover.animate?.([{opacity:0,transform:'translateY(4px)'},{opacity:1,transform:'translateY(0)'}],{duration:160,easing:'ease-out'});
  }
  function commitSelect(index) {
    if (!selectMenu || state.busy || !Number.isInteger(index) || !selectMenu.options[index]) return;
    const {trigger,kind,options} = selectMenu; trigger.value = options[index].value;
    if (kind === 'status') {
      const value = trigger.value; closeSelect(true); groupUI?.clear(); state.status = value;
      state.selected = visible()[0]?.id || null; persistDrafts(); render(); return;
    }
    selectMenu.active = index; selectParameter(trigger); updateSelectMenu(); positionSelect(); selectList.focus({preventScroll:true});
  }
  function selectKey(event) {
    if (event.isComposing) return false;
    const trigger = event.target.closest?.('[data-choice-control],#sw2-status-filter');
    if (trigger && ['ArrowDown','ArrowUp'].includes(event.key)) {
      event.preventDefault(); openSelect(trigger,event.key === 'ArrowUp'); return true;
    }
    if (!selectMenu) return false;
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation?.(); closeSelect(true); return true; }
    if (!selectPopover.contains(event.target)) return false;
    if (event.key === 'Tab') {
      const fromList = event.target === selectList;
      if (selectMenu.kind === 'status' || (fromList && (event.shiftKey || !selectMenu.trigger.value))) closeSelect(true);
      else if (!event.shiftKey && event.target.dataset.action === 'choice-discuss') closeSelect(true);
      return true;
    }
    if (event.target !== selectList && !event.target.matches?.('[role="option"]')) return false;
    const n = selectMenu.options.length;
    if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
      event.preventDefault(); selectMenu.active = event.key === 'Home' ? 0 : event.key === 'End' ? n-1 : (selectMenu.active + (event.key === 'ArrowDown' ? 1 : -1) + n) % n;
      updateSelectMenu(); return true;
    }
    if (['Enter',' '].includes(event.key)) { event.preventDefault(); commitSelect(selectMenu.active); return true; }
    return false;
  }
  document.addEventListener('pointerdown', event => {
    if (selectMenu && !selectPopover.contains(event.target) && !selectMenu.trigger.contains(event.target)) closeSelect();
  });
  document.addEventListener('focusin', event => {
    if (selectMenu && !selectPopover.contains(event.target) && event.target !== selectMenu.trigger) closeSelect();
  });
  document.addEventListener('scroll', event => { if (selectMenu && !selectPopover.contains(event.target)) closeSelect(); }, true);
  window.addEventListener('resize', () => closeSelect());
  window.visualViewport?.addEventListener('resize', () => closeSelect());
  function appendToDiscussion(text, quoteSource) {
    const group = groupUI?.selected() || state.snapshot.decision_groups?.find(g => g.member_ids.includes(state.selected));
    const existing = group ? groupUI.message(group.id) : messageDrafts[state.selected];
    const value = quoteSource ? window.CouncilMarkdown.appendQuote(existing, quoteSource, text) : window.CouncilMarkdown.appendPreference(existing, text);
    if (value.trim().length > 20000) { showNotice('讨论内容过长，请缩短选文或先保存当前留言。', 'info'); return false; }
    if (group) {
      if (!groupUI.selected()) groupUI.openDiscussion(group.id);
      groupUI.appendDiscussion(text, quoteSource);
    } else {
      composing[state.selected] = true;
      root.querySelector('.sw2-message-editor').hidden = false;
      root.querySelector('[data-action="compose"]').hidden = true;
      const area = root.querySelector('#sw2-message'); area.value = value;
      messageDraft(state.selected, value); area.focus({preventScroll:true});
    }
    const area = root.querySelector(group ? '#dg-message' : '#sw2-message');
    area.setSelectionRange?.(area.value.length, area.value.length);
    area.scrollTop = area.scrollHeight;
    if (!discussionMedia.matches) area.scrollIntoView?.({block:'center', behavior:reducedMotion.matches ? 'instant' : 'smooth'});
    return true;
  }
  function addParameterToDiscussion(button) {
    const select = button;
    if (!select?.value) return;
    if (appendToDiscussion('倾向' + select.dataset.choiceLabel + '：' + select.value))
      showNotice('参数偏好已添加到讨论输入框，尚未保存或确认。', 'info');
  }
  let quotedSelection = null;
  const quoteButton = root.querySelector('#sw2-quote-selection');
  function hideQuote() { quotedSelection = null; quoteButton.hidden = true; }
  const selectionElement = node => node?.nodeType === 1 ? node : node?.parentElement;
  function selectedPlainText(node) {
    if (node.nodeType === 3) return node.textContent;
    if (node.matches?.('.sw2-inline-choice')) {
      const select = node.querySelector('[data-choice-control]'); return select?.value || select?.dataset.choiceLabel || '';
    }
    if (node.matches?.('button,input,select,textarea,[hidden]')) return '';
    if (node.nodeName === 'BR') return '\n';
    const text = Array.from(node.childNodes || []).map(selectedPlainText).join('');
    return /^(P|DIV|H[1-6]|LI|BLOCKQUOTE|PRE|TR)$/.test(node.nodeName) ? '\n'+text+'\n' : /^(TD|TH)$/.test(node.nodeName) ? text+'\t' : text;
  }
  function offerQuote() {
    const selection = window.getSelection?.();
    if (state.busy || !selection?.rangeCount || selection.isCollapsed) { hideQuote(); return; }
    const range = selection.getRangeAt(0);
    const start = selectionElement(range.startContainer), end = selectionElement(range.endContainer);
    const source = start?.closest('[data-quote-source]');
    if (!source || !root.contains(source) || !source.contains(end) ||
        start.closest('input,textarea,select,button,[contenteditable]') || end.closest('input,textarea,select,button,[contenteditable]')) { hideQuote(); return; }
    const text = selectedPlainText(range.cloneContents()).replace(/\n{3,}/g, '\n\n').trim();
    if (!text) { hideQuote(); return; }
    const rect = range.getBoundingClientRect();
    if (!rect.width || rect.bottom < 0 || rect.top > window.innerHeight) { hideQuote(); return; }
    quotedSelection = {text, source:source.dataset.quoteSource, scope:selected()?.id};
    quoteButton.hidden = false;
    quoteButton.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - quoteButton.offsetWidth - 8))+'px';
    quoteButton.style.top = Math.max(8, rect.bottom + 8 + quoteButton.offsetHeight < window.innerHeight ? rect.bottom + 8 : rect.top - quoteButton.offsetHeight - 8)+'px';
  }
  document.addEventListener('selectionchange', offerQuote);
  document.addEventListener('scroll', hideQuote, true);
  window.addEventListener('resize', hideQuote);
  const questions = () => state.snapshot.questions;
  const byId = id => questions().find(q => q.id === id);
  let groupUI;
  const selected = () => groupUI?.selected() || byId(state.selected);
  let routeInitialized = false, readingHistory = false;
  function applyRoute() {
    const url = new URL(window.location.href), group = url.searchParams.get('group'), question = url.searchParams.get('question');
    if (group && state.snapshot.decision_groups?.some(g => g.id === group)) {
      groupUI?.select(group); state.group = 'all'; state.status = 'all'; state.search = ''; return;
    }
    if (question && byId(question)) {
      groupUI?.clear(); state.selected = question;
      if (!visible().some(q => q.id === question)) { state.group = 'all'; state.status = 'all'; state.search = ''; }
      return;
    }
    if (group || question) showNotice('链接中的问题或组合已不存在，已返回当前项目。', 'info');
  }
  function syncRoute() {
    if (!routeInitialized || !window.history || readingHistory) return;
    const url = new URL(window.location.href), group = groupUI?.selected();
    url.searchParams.delete('group'); url.searchParams.delete('question');
    if (group) url.searchParams.set('group', group.id);
    else if (state.selected) url.searchParams.set('question', state.selected);
    if (url.href === window.location.href) return;
    window.history.pushState({ councilProject: state.snapshot.project }, '', url.href);
  }
  const groupName = key => names[key] || key;
  const groups = () => [...new Set(questions().map(q => groupName(q.group)))];
  const groupColor = key => colors[Math.max(0, groups().indexOf(groupName(key))) % colors.length];
  const label = status => status === "historical" ? "历史讨论" : status === "frozen" ? "正式口径" : status === "answered" ? "历史答复" : status === "discussing" ? "讨论中" : "待讨论";
  const pill = (status, formal = false) => '<span class="sw2-pill sw2-pill-' + (status === "discussing" ? "talk" : status === "frozen" ? "answered" : status) + '">' + (status === "frozen" && !formal ? "已有冻结记录" : label(status)) + "</span>";
  const actorKind = actor => ["user", "codex", "chatgpt"].includes(actor) ? actor : "unknown";
  const actorLabel = actor => ({ user: "你", codex: "Codex", chatgpt: "ChatGPT", web_ai: "网页 AI（历史来源）" })[actor] || "AI（来源未记录）";
  const actorBadge = actor => '<span class="sw2-actor sw2-actor-' + actorKind(actor) + '">' + actorLabel(actor) + "</span>";
  const historicalActor = actor => ({ user: "用户", codex: "Codex", chatgpt: "ChatGPT", web_ai: "网页 AI" })[actor] || "作者未明";
  const historicalBadge = actor => '<span class="sw2-actor sw2-actor-' + actorKind(actor) + '">' + historicalActor(actor) + "（历史）</span>";
  const sourceName = source => source.path + (source.section ? " · " + source.section : "");
  const recoveryTitle = kind => ({ frozen: "已冻结口径 · 历史回填", discussion: "可复原讨论 · 历史回填", unconfirmed: "待确认记录 · 历史回填", historical: "已结束 / 已取代的历史讨论" })[kind];
  const shortTime = value => {
    if (!value) return "时间未记录";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  };
  function recoverySummary(q) {
    const records = q.recovered_records || [];
    const superseded = new Set(records.map(record => record.supersedes).filter(Boolean));
    const summaries = [...records].reverse().filter(record => !superseded.has(record.key));
    const seen = new Set();
    return summaries.filter(record => {
      if (!record.summary || seen.has(record.summary)) return false;
      seen.add(record.summary); return true;
    }).map(record => '<section class="sw2-decision-context sw2-decision-' + record.kind + '"><strong>' +
      ({ frozen: "已有冻结口径", discussion: "讨论背景", unconfirmed: "已有记录", historical: "历史结论" })[record.kind] +
      '</strong><div>' + escape(record.summary) + '</div></section>').join("");
  }
  function provenanceHTML(q) {
    const records = q.recovered_records || [];
    const superseded = new Set(records.map(record => record.supersedes).filter(Boolean));
    const paths = [...new Set((q.source_summary || "").split(/[；;\n]+/).map(value => value.trim()).filter(Boolean))];
    return '<details class="sw2-provenance"><summary>来源与恢复记录' + (records.length ? ' · ' + records.length + ' 条' : '') + '</summary><div class="sw2-provenance-body">' +
      (paths.length ? '<div class="sw2-provenance-paths">' + paths.map(path => '<div>' + escape(path) + '</div>').join("") + '</div>' : '') +
      [...records].reverse().map(record => '<section class="sw2-history"><h3>' + (superseded.has(record.key) ? "原恢复分类 · 已修正" : recoveryTitle(record.kind)) + '</h3><div>' + escape(record.summary) + '</div>' +
        (record.correction ? '<div class="sw2-history-meta">状态修正：' + label(record.correction.before) + ' → ' + label(record.correction.after) + (record.correction.review_preserved ? ' · 保留当前答复与分歧' : '') + '</div>' : '') +
        (record.reason ? '<div class="sw2-history-meta">' + escape(record.reason) + '</div>' : '') +
        '<div class="sw2-history-meta">' + actorBadge(record.recovered_by) + ' 整理 · ' + escape(record.recovered_at) + '</div>' +
        record.sources.map(source => '<details><summary>' + escape(sourceName(source)) + '</summary><pre>' + escape(source.excerpt) + '</pre></details>').join("") + '</section>'
      ).join("") + '</div></details>';
  }
  const requestId = () => crypto.randomUUID ? crypto.randomUUID() : Date.now() + "-" + Math.random();
  const visible = () => groups().flatMap(group => questions().filter(q => groupName(q.group) === group &&
    (state.group === "all" || group === state.group) && matchesStatus(q) &&
    (!state.search || (q.id + " " + q.title + " " + q.why + " " + (state.snapshot.decision_groups?.find(g => g.member_ids.includes(q.id))?.title || "")).toLocaleLowerCase().includes(state.search.toLocaleLowerCase()))));
  const pendingQuestions = () => questions().filter(q => Object.hasOwn(drafts, q.id) || Boolean(messageDrafts[q.id]?.trim()));
  const pending = () => pendingQuestions().concat(groupUI?.pending() || []);
  const definition = q => q?.definition || { draft: null, versions: [], current_version: null };
  const candidateText = q => definition(q).draft?.text || "";
  const conflict = q => Object.hasOwn(drafts, q.id) && draftBases[q.id] &&
    (draftBases[q.id].text !== candidateText(q) || draftBases[q.id].current !== definition(q).current_version);
  function discussionMessages(q, includeShared = false) {
    const messages = [...(q.messages || [])];
    if (q.ai_position && !messages.some(m => m.actor === q.ai_position_by && m.text === q.ai_position)) {
      messages.unshift({ actor: q.ai_position_by, text: q.ai_position, at: q.ai_position_at, kind: "proposal" });
    }
    if (q.user_answer) messages.push({ actor: "user", text: q.user_answer, kind: "legacy_answer" });
    const joint = state.snapshot.decision_groups?.find(g => g.member_ids.includes(q.id));
    if (joint && includeShared) {
      messages.push(...(joint.messages || []).map(m => ({ ...m, shared: true })));
      messages.sort((a, b) => String(a.at || "").localeCompare(String(b.at || "")));
    }
    return messages;
  }
  function workflowHTML(items) {
    const incomplete = items.some(q => !definition(q).draft?.text?.trim() && !definition(q).current_version);
    const hasDraft = items.some(q => definition(q).draft);
    const effective = items.length > 0 && items.every(q => definition(q).current_version);
    const needsReview = items.some(q => ['waiting','needs_review'].includes(q.readiness?.status));
    const step = hasDraft && !incomplete ? 1 : effective ? 2 : 0;
    const note = incomplete && items.length > 1 ? 'AI 尚未补齐本组候选口径' : needsReview ? '前序依据需要确定或复核' : hasDraft ? (effective ? '修订中，原正式版本继续有效' : '审阅完整候选后确认') : effective ? '正式口径已记录，可开启下一版修订' : '讨论清楚后，由 AI 整理完整候选';
    return '<div class="sw2-workflow" data-effective="'+(effective && !hasDraft)+'"><ol aria-label="口径进度">' + ['讨论与比较','审阅候选','确认生效'].map((text,i) => '<li'+(i === step ? ' aria-current="step"' : '')+'><b>'+(i+1)+'</b>'+text+'</li>').join('')+' </ol><span class="sw2-workflow-note">'+note+'</span></div>';
  }
  function setNavigation(open) {
    if (drawerMedia.matches) {
      root.dataset.navHidden = 'false';
      root.dataset.navOpen = String(open);
      root.querySelector('#sw2-nav-scrim').hidden = !open;
    } else {
      root.dataset.navHidden = String(!open);
      root.dataset.navOpen = 'false';
      root.querySelector('#sw2-nav-scrim').hidden = true;
    }
    root.querySelector('#sw2-navigation').inert = !open;
    root.querySelector('#sw2-nav-toggle').setAttribute('aria-expanded', String(open));
  }
  const answerText = value => (value ?? "").trim();
  const hasSavedDiscussion = q => (q.messages || []).some(message => message.actor === "user");
  const overlay = () => root.querySelector("#sw2-overlay");

  function updateMobileNav() {
    if (!selected() && !groupUI?.selected()) state.mobileView = "list";
    root.dataset.mobileView = state.mobileView;
    root.querySelector("#sw2-mobile-question").textContent = groupUI?.selected() ? "一起审阅" : selected()?.id || "";
  }

  function showMobileView(view) {
    if (view === "detail" && drawerMedia.matches) setNavigation(false);
    state.mobileView = view;
    updateMobileNav();
    if (!mobileMedia.matches) return;
    requestAnimationFrame(() => {
      if (view === "list") {
        root.querySelector('[data-action="select"][data-id="' + state.selected + '"]')?.focus({ preventScroll: true });
        window.scrollTo(0, mobileListScroll);
      } else {
        window.scrollTo(0, 0);
        root.querySelector("#sw2-detail").focus({ preventScroll: true });
      }
    });
  }

  function persistDrafts() {
    if (!storageKey) return;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({ definitions: drafts, messages: messageDrafts, definitionBases: draftBases, requests: draftRequests, selected: state.selected, group: state.group, status: state.status, search: state.search }));
      storageOK = true;
    } catch (_) { storageOK = false; }
  }

  function restoreDrafts() {
    storageKey = "stepwise-freeze:drafts:v1:" + state.snapshot.project;
    if (loadedDrafts) return;
    loadedDrafts = true;
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}");
      for (const q of questions()) {
        if (typeof saved.definitions?.[q.id] === "string" && answerText(saved.definitions[q.id]) !== candidateText(q)) {
          drafts[q.id] = saved.definitions[q.id];
          draftBases[q.id] = saved.definitionBases?.[q.id] || { text: candidateText(q), current: definition(q).current_version };
          editing[q.id] = true;
        }
        if (typeof saved.messages?.[q.id] === "string") messageDrafts[q.id] = saved.messages[q.id];
        for (const kind of ["definition", "comment"]) {
          const key = q.id + ":" + kind;
          if (typeof saved.requests?.[key] === "string") draftRequests[key] = saved.requests[key];
        }
        // Old answer inputs remain unconfirmed discussion; never promote them to definitions.
        if (typeof saved.answers?.[q.id] === "string" && answerText(saved.answers[q.id]) && answerText(saved.answers[q.id]) !== answerText(q.user_answer)) {
          messageDrafts[q.id] = [messageDrafts[q.id], "此前未提交的答复：" + saved.answers[q.id]].filter(Boolean).join("\n\n");
          draftRequests[q.id + ":comment"] = requestId();
        }
      }
      if (byId(saved.selected)) state.selected = saved.selected;
      if (saved.group === "all" || groups().includes(saved.group)) state.group = saved.group;
      if (Object.hasOwn(statusLabels, saved.status)) state.status = saved.status === "frozen" ? "completed" : saved.status;
      if (typeof saved.search === "string") state.search = saved.search.slice(0, 500);
    } catch (_) { storageOK = false; }
  }

  function discardEdits(ids) {
    const edits = {};
    for (const id of ids) if (Object.hasOwn(drafts, id)) {
      if (conflict(byId(id))) throw new Error(id + "：候选已改变，请先刷新并比较修改，再取消修订。");
      edits[id] = { text: drafts[id], request_id: draftRequests[id + ":definition"] ||= requestId() };
    }
    persistDrafts();
    return edits;
  }

  function reconcileDrafts() {
    for (const q of questions()) {
      const withdrawn = (definition(q).withdrawn_drafts || []).some(d =>
        d.local_edit?.by === "user" && d.local_edit.request_id === draftRequests[q.id + ":definition"] && d.local_edit.text === drafts[q.id]);
      if (Object.hasOwn(drafts, q.id) && withdrawn) {
        delete drafts[q.id]; delete draftBases[q.id]; delete draftRequests[q.id + ":definition"]; editing[q.id] = false;
      }
      if (Object.hasOwn(drafts, q.id) && answerText(drafts[q.id]) === candidateText(q) && draftBases[q.id]?.current === definition(q).current_version) {
        delete drafts[q.id]; delete draftBases[q.id]; delete draftRequests[q.id + ":definition"];
      }
      const request = draftRequests[q.id + ":comment"], value = messageDrafts[q.id]?.trim();
      // A lost save response can leave a draft whose request is already in the project.
      // Match its receipt and text, never just an older message with identical wording.
      if (request && value && (q.messages || []).some(message =>
        message.id === request && message.actor === "user" && message.text === value)) {
        delete messageDrafts[q.id]; delete draftRequests[q.id + ":comment"];
      }
      if (!Object.hasOwn(drafts, q.id)) delete draftRequests[q.id + ":definition"];
    }
  }

  function answerDraft(id, value) {
    const q = byId(id);
    if (!q) return;
    if (answerText(value) === candidateText(q)) {
      delete drafts[id]; delete draftBases[id]; delete draftRequests[id + ":definition"];
    } else {
      if (!Object.hasOwn(drafts, id)) draftBases[id] = { text: candidateText(q), current: definition(q).current_version };
      if (drafts[id] !== value) draftRequests[id + ":definition"] = requestId();
      drafts[id] = value;
    }
    persistDrafts(); updateDraftUI();
  }

  function messageDraft(id, value) {
    const preview = root.querySelector("#sw2-message-preview");
    if (preview) preview.innerHTML = renderMarkdown(value, discussionScope());
    if (messageDrafts[id] !== value) draftRequests[id + ":comment"] = requestId();
    if (value.trim()) messageDrafts[id] = value;
    else { delete messageDrafts[id]; delete draftRequests[id + ":comment"]; }
    persistDrafts(); updateDraftUI();
  }

  function updateDraftUI() {
    updateChoiceControls();
    groupUI?.updateControls();
    const count = pending().length;
    const badge = root.querySelector("#sw2-draft-count");
    badge.textContent = count; badge.hidden = !count;
    root.querySelector("#sw2-save-all").disabled = state.busy || !count;
    root.querySelector("#sw2-draft-label").textContent = count
      ? count + " 项未保存 · " + (storageOK && !groupUI?.storageFailed() ? "草稿已在本窗口暂存" : "浏览器暂存失败，请保存")
      : "无未保存修改";
    for (const button of root.querySelectorAll("[data-action=select]")) {
      const tag = button.querySelector(".sw2-draft-tag");
      if (tag) {
        const id = button.dataset.id;
        const kinds = [Object.hasOwn(drafts, id) ? "候选口径" : "", messageDrafts[id]?.trim() ? "留言" : ""].filter(Boolean);
        tag.hidden = !kinds.length; tag.textContent = kinds.join("、") + "未保存";
      }
    }
    for (const button of root.querySelectorAll(".dg-group-link")) {
      const g = state.snapshot.decision_groups?.find(g => g.id === button.dataset.id);
      if (g) button.querySelector("span").textContent = g.member_ids.length + " 条口径" +
        (groupUI?.missing?.(g) ? " · " + groupUI.missing(g) + " 条待 AI 补齐" : "") +
        (groupUI?.pending().some(p => p.id === g.id) ? " · 未保存" : "");
    }
    const q = selected();
    const hint = root.querySelector("#sw2-answer-hint");
    if (hint && q) hint.textContent = Object.hasOwn(drafts, q.id) ? "候选口径未保存" : definition(q).draft ? "候选已保存 · 尚未确认" : definition(q).current_version ? "当前有效 v" + definition(q).current_version : "尚无正式版本";
    const confirm = root.querySelector('[data-action="approve-definition"]');
    if (confirm && q) confirm.disabled = state.busy || !definition(q).draft?.text || Object.hasOwn(drafts, q.id) || Boolean(messageDrafts[q.id]?.trim());
    const saveAnswerButton = root.querySelector('[data-action="save-answer"]');
    if (saveAnswerButton && q) saveAnswerButton.disabled = state.busy || !drafts[q.id]?.trim();
    const postButton = root.querySelector('[data-action="post"]');
    if (postButton && q) postButton.disabled = state.busy || !messageDrafts[q.id]?.trim();
    const messageHint = root.querySelector("#sw2-message-hint");
    if (messageHint && q) messageHint.textContent = messageDrafts[q.id]?.trim() ? "留言未保存" : hasSavedDiscussion(q) ? "讨论已保存 · " + discussionMessages(q).length + " 条记录" : "";
  }

  function showNotice(message, kind = "success", target = "", questionId = null) {
    const notice = root.querySelector("#sw2-notice");
    clearTimeout(noticeTimer);
    // A modal owns its feedback; elsewhere one dismissible notice avoids duplicate announcements.
    if (!overlay().hidden) {
      notice.hidden = true;
      const nearby = root.querySelector("#sw2-handoff-status");
      nearby.textContent = message; nearby.dataset.kind = kind; nearby.hidden = false;
      return;
    }
    root.querySelector("#sw2-notice-text").textContent = message;
    notice.dataset.kind = kind;
    notice.setAttribute("role", kind === "error" ? "alert" : "status");
    notice.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
    notice.hidden = false;
    if (kind !== "error") noticeTimer = setTimeout(() => { notice.hidden = true; }, 5000);
  }

  function connection(message, kind = "success") {
    const footer = root.querySelector("#sw2-save-label");
    footer.textContent = message; footer.dataset.kind = kind;
  }

  function friendlyError(error) {
    const message = error.message || String(error);
    if (error.network || /Failed to fetch|NetworkError|Load failed/i.test(message)) {
      return "工作台连接中断，内容尚未确认保存。恢复服务或转发连接后，点击“刷新项目记录”，再重试保存。未保存输入仍在本窗口。";
    }
    if (message.includes("changed since read")) return "这题已被其他窗口更新。点击“刷新项目记录”后比较候选文本，再重试；本地草稿会保留。";
    if (message.includes("Login required")) return "登录已失效，请点击上方“重新登录”，登录后刷新项目记录；本窗口草稿会保留。";
    if (message.includes("CSRF check failed")) return "页面会话已失效。点击“刷新项目记录”后再保存；本窗口草稿会保留。";
    if (error.status >= 500) return "工作台服务暂时无法完成操作。恢复服务后点击“刷新项目记录”，再重试；本地草稿会保留。";
    return message;
  }

  async function api(path, body, site = false) {
    if (!site) path = apiPrefix + path.slice(4);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      let response;
      try {
        response = await fetch(path, body === undefined ? { credentials: "same-origin", cache: "no-store", signal: controller.signal } : {
          method: "POST", credentials: "same-origin", cache: "no-store", signal: controller.signal,
          headers: { "Content-Type": "application/json", "X-Freeze-CSRF": state.csrf }, body: JSON.stringify(body),
        });
      } catch (cause) { const error = new Error(cause.message); error.network = true; throw error; }
      let data;
      try { data = await response.json(); } catch (_) { const error = new Error("响应内容无法读取，请刷新项目记录后重试。"); error.status = response.status; throw error; }
      if (!response.ok) {
        if (response.status === 401) {
          const login = root.querySelector('#sw2-login');
          login.href = window.location.href; login.hidden = false;
          root.querySelector('#sw2-logout').hidden = true;
        }
        const error = new Error(data.error || "HTTP " + response.status); error.status = response.status; throw error;
      }
      return data;
    } finally { clearTimeout(timer); }
  }

  async function refresh() {
    const data = await api("/api/snapshot");
    state.snapshot = data.snapshot; state.csrf = data.csrf;
    root.querySelector('#sw2-logout').hidden = !data.auth_required;
    root.querySelector('#sw2-login').hidden = true;
    connection("项目记录已同步");
    state.remoteUpdate = false; root.querySelector("#sw2-update").textContent = "刷新项目记录";
    root.querySelector("#sw2-mobile-refresh").textContent = "刷新";
    root.querySelector("#sw2-mobile-refresh").dataset.updated = "false";
    restoreDrafts();
    reconcileDrafts(); groupUI?.reconcile();
    if (!routeInitialized && window.location?.href) {
      applyRoute();
      if (!state.selected) state.selected = visible()[0]?.id || null;
      const url = new URL(window.location.href), group = groupUI?.selected();
      url.searchParams.delete('group'); url.searchParams.delete('question');
      if (group) url.searchParams.set('group', group.id); else if (state.selected) url.searchParams.set('question', state.selected);
      window.history?.replaceState({ councilProject: state.snapshot.project }, '', url.href);
      routeInitialized = true;
    }
    if (!visible().some(q => q.id === state.selected)) state.selected = visible()[0]?.id || null;
    persistDrafts(); render();
  }

  function renderGroups() {
    const buttons = [["all", "全部问题", "#7464ef", questions().length], ...groups().map(key => [key, key, groupColor(key), questions().filter(q => groupName(q.group) === key).length])];
    root.querySelector("#sw2-group-list").innerHTML = buttons.map(([key, name, color, count]) =>
      '<button type="button" class="sw2-group" data-action="group" data-group="' + escape(key) + '" aria-label="' + escape(name) + '" aria-current="' + (state.group === key) + '"><span class="sw2-dot" style="--group-color:' + color + '"></span><span class="sw2-group-name">' + escape(name) + "</span><small>" + count + "</small></button>").join("");
  }

  function renderList() {
    const items = visible();
    root.querySelector("#sw2-search-clear").hidden = !state.search;
    root.querySelector("#sw2-search-shortcut").hidden = Boolean(state.search);
    root.querySelector("#sw2-list-heading").textContent = state.group === "all" ? "全部问题" : state.group;
    root.querySelector("#sw2-visible").textContent = items.length + " / " + questions().length + " 项";
    const statusControl = root.querySelector('#sw2-status-filter');
    statusControl.textContent = statusLabels[state.status]; statusControl.value = state.status;
    const filtered = state.status !== "all" || state.group !== "all" || Boolean(state.search);
    root.querySelector("#sw2-clear-filter").hidden = !filtered;
    const filterToggle = root.querySelector("#sw2-filter-toggle");
    filterToggle.dataset.active = String(filtered);
    const filterDescription = "筛选与搜索" + (filtered ? "（已启用：" + [state.status !== "all" ? statusLabels[state.status] : "", state.group !== "all" ? state.group : "", state.search ? "搜索“" + state.search + "”" : ""].filter(Boolean).join("、") + "）" : "");
    filterToggle.setAttribute("aria-label", filterDescription);
    let previous = "";
    const grouped = new Set((state.snapshot.decision_groups || []).flatMap(g => g.member_ids));
    const questionHTML = q => {
      return '<button type="button" class="sw2-question" data-action="select" data-id="' + q.id + '" aria-current="' + (selected()?.id === q.id) + '"><span class="sw2-question-top"><span class="sw2-question-id">' + q.id + "</span>" + (["waiting", "needs_review"].includes(q.readiness?.status) ? '<span class="sw2-pill sw2-pill-discussing">' + escape(groupUI?.status(q) || "待复核") + '</span>' : definition(q).draft ? '<span class="sw2-pill sw2-pill-open">候选待确认</span>' : definition(q).current_version ? '<span class="sw2-pill sw2-pill-answered">有效 v' + definition(q).current_version + '</span>' : pill(q.status)) + '</span><span class="sw2-question-name">' + escape(q.title) + '</span><span class="sw2-draft-tag" hidden>未保存</span></button>';
    };
    const groupedHTML = groupUI?.listHTML(items, questionHTML) || "";
    root.querySelector("#sw2-question-list").innerHTML = groupedHTML + (items.filter(q => !grouped.has(q.id)).map(q => {
      const heading = groupName(q.group) !== previous ? '<div class="sw2-list-group-title"><span class="sw2-dot" style="--group-color:' + groupColor(q.group) + '"></span>' + escape(groupName(q.group)) + "</div>" : "";
      previous = groupName(q.group);
      return heading + questionHTML(q);
    }).join("") || (groupedHTML ? "" : '<div class="sw2-empty">' + (questions().length ? '没有匹配的问题。<button class="sw2-button sw2-button-outline" data-action="clear-filter">清除筛选</button>' : "暂无问题") + "</div>"));
  }

  function renderDetail() {
    closeSelect(); hideQuote();
    const q = selected(), panel = root.querySelector("#sw2-detail");
    if (groupUI?.renderDetail(panel)) { syncRoute(); applyDiscussionWidth(); return; }
    syncRoute();
    const sameQuestion = panel.dataset.question === (q?.id || "");
    const scrollPositions = sameQuestion ? [".sw2-work-in", ".sw2-thread", ".sw2-review-body"].map(selector => [selector, panel.querySelector(selector)?.scrollTop || 0]) : [];
    const expanded = sameQuestion ? Array.from(panel.querySelectorAll?.('details[data-record][open]') || []).map(e => e.dataset.record) : [];
    const sourceOpen = sameQuestion && panel.querySelector(".sw2-provenance")?.open;
    if (!sameQuestion) { panel.scrollTop = 0; panel.dataset.reading = "discussion"; }
    panel.dataset.question = q?.id || "";
    if (!q) {
      panel.innerHTML = '<div class="sw2-empty">' + (questions().length ? "没有匹配的问题，请调整搜索或筛选。" : "尚无问题。请让 AI 读取项目后，一次性补充本轮问题。") + "</div>";
      return;
    }
    const thread = discussionMessages(q, true), def = definition(q), draft = def.draft;
    const jointGroup = state.snapshot.decision_groups?.find(g => g.member_ids.includes(q.id));
    const editingNow = Boolean(editing[q.id] || Object.hasOwn(drafts, q.id));
    panel.dataset.wording = (draft || def.versions.length || editingNow || q.recovered_records?.length) ? "present" : "empty";
    const composingNow = !jointGroup || Boolean(messageDrafts[q.id]?.trim());
    const conflictHTML = conflict(q) ? '<section class="sw2-conflict"><strong>候选口径或当前版本已更新，请比较后再保存</strong><p>' + escape(candidateText(q) || "原候选已生效或移除") + '</p><div class="sw2-action-pair"><button class="sw2-button sw2-button-outline" data-action="use-project">使用项目文本</button><button class="sw2-button sw2-button-outline" data-action="keep-draft">保留我的修改</button></div></section>' : "";
    const recordHeading = (number, pending = false) => '<div class="sw2-record-caption"><h3 class="sw2-record-heading">' + escape(q.title) + '</h3><span class="sw2-version-stack">' + (pending ? '<span class="sw2-draft-state">待确认</span>' : '') + '<span class="sw2-version-mark" aria-label="版本 v' + number + '">V' + number + '</span></span></div>';
    const versionHTML = (v, extra = '') => {
      const current = v.number === def.current_version;
      const confirmedDate = v.published_at ? new Date(v.published_at).toLocaleDateString("zh-CN", {year:"numeric",month:"2-digit",day:"2-digit"}) : "日期未记录";
      const status = current ? (["waiting", "needs_review"].includes(q.readiness?.status) ? "已确认 · 依据待复核" : "当前有效") : "旧版本";
      const content = '<div class="sw2-definition-text sw2-record-body" data-quote-source="' + q.id + ' · ' + (current ? '正式' : '历史') + '口径 v' + v.number + '">' + renderMarkdown(v.text) + '</div><div class="sw2-record-end"><details class="sw2-record-details" data-record="meta-' + v.number + '"><summary>详情</summary><div class="sw2-record-detail-text">编号：' + q.id + '<br>状态：' + status + '<br>确认人：' + escape(actorLabel(v.published_by || "user")) + '<br>正式来源：' + escape(v.source || "项目口径记录") + '</div>' + extra + '</details><span class="sw2-record-date">确认日期 ' + escape(confirmedDate) + '</span></div>';
      return '<article class="sw2-definition-version sw2-record' + (current ? ' sw2-definition-current' : '') + '" data-state="' + (current ? 'effective' : 'history') + '">' + recordHeading(v.number) + content + '</article>';
    };
    const current = def.versions.find(v => v.number === def.current_version);
    const history = [...def.versions].reverse().filter(v => v.number !== def.current_version);
    const historyHTML = history.length ? '<details class="sw2-version-history" data-record="history"><summary>历史版本 · ' + history.length + '</summary>' + history.map(v => versionHTML(v)).join('') + '</details>' : '';
    const currentHTML = current ? (draft ? '<details class="sw2-current-reference" data-record="current"><summary>对照当前有效版本 · v' + current.number + '</summary>' + versionHTML(current) + '</details>' : versionHTML(current, historyHTML)) : '';
    panel.innerHTML = [
      '<div class="sw2-work"><div class="sw2-work-in"><header class="sw2-question-context"><div class="sw2-detail-top"><span class="sw2-detail-code">' + q.id + ' · 第 ' + q.round + ' 轮</span>' + (["waiting", "needs_review"].includes(q.readiness?.status) ? '<span class="sw2-pill sw2-pill-discussing">' + escape(groupUI?.status(q) || "待复核") + '</span>' : definition(q).current_version ? '<span class="sw2-pill sw2-pill-answered">有效 v' + definition(q).current_version + '</span>' : pill(q.status)) + '<span class="sw2-origin">提出 ' + actorBadge(q.created_by) + "</span></div>",
      '<div class="sw2-question-heading"><h2>' + escape(q.title) + '</h2></div>',
      q.why && q.why !== "恢复旧项目口径与讨论记录" ? '<div class="sw2-question-why">' + escape(q.why) + '</div>' : "",
      (groupUI?.dependencies(q) || '') + workflowHTML([q]) + '</header>' + '<div class="sw2-review-body"><section class="sw2-decision-column" aria-label="正式口径与候选文档"><div class="sw2-section-title">口径</div><div class="sw2-opinion-scroll" tabindex="0" aria-label="口径版本内容">',
      !draft && !current ? (q.recovered_records?.length ? '<div class="sw2-empty"><strong>已保留历史依据</strong>尚未建立正式版本，既有决定沿用原有依据。</div>' : '<div class="sw2-empty"><strong>候选尚未备齐</strong>AI 尚未写入完整候选口径；应先补齐内容，再交付你审阅。</div>') : '',
      !def.versions.length && q.recovered_records?.length ? recoverySummary(q) : "",
      draft ? '<article class="sw2-definition-candidate sw2-record" data-state="draft">' + recordHeading(def.versions.length + 1, true) + '<div class="sw2-definition-text sw2-record-body" data-quote-source="' + q.id + ' · 候选口径 v' + (def.versions.length + 1) + '">' + renderMarkdown(draft.text || "候选已开启，等待编写完整口径。") + '</div><div class="sw2-definition-actions"><button class="sw2-button sw2-button-outline" data-action="edit-definition">修改候选</button><button class="sw2-button sw2-button-outline" data-action="discard-definition">' + (current ? "取消修订" : "撤回候选") + '</button><button class="sw2-button sw2-button-primary" data-action="' + (q.decision_group_id ? "dg-open" : "approve-definition") + '" data-reading="wording" data-id="' + (q.decision_group_id || "") + '">' + (q.decision_group_id ? "前往整组确认" : "确认并生效") + '</button></div><div class="sw2-record-end"><details class="sw2-record-details" data-record="candidate-meta"><summary>详情</summary><div class="sw2-record-detail-text">编号：' + q.id + '<br>状态：候选 · 尚未生效</div>' + currentHTML + historyHTML + '</details></div></article>' : '',
      !draft ? currentHTML : '',
      !draft && !jointGroup ? '<button class="sw2-button sw2-button-outline sw2-begin-definition" data-action="' + (def.current_version ? "begin-definition" : "edit-definition") + '">' + (def.current_version ? '开启 v' + (def.versions.length + 1) + ' 修订' : "起草候选口径") + '</button>' : '',
      !draft && !current ? historyHTML : '',
      conflictHTML,
      '</div><div class="sw2-composer sw2-answer-composer"' + (editingNow ? '' : ' hidden') + '><label class="sw2-section-title" for="sw2-answer">编辑完整候选口径<small>支持 Markdown · 保存后需确认</small></label><textarea id="sw2-answer" class="sw2-answer sw2-definition-editor" placeholder="写入可直接进入正式文档的完整规则、范围、条件和例外…">' + escape(drafts[q.id] ?? (editingNow ? candidateText(q) : "")) + '</textarea><details class="sw2-markdown-preview" data-record="local-preview"><summary>预览排版（未保存）</summary><div class="sw2-record-body" id="sw2-answer-preview">' + renderMarkdown(drafts[q.id] ?? (editingNow ? candidateText(q) : "")) + '</div></details><div class="sw2-answer-actions"><span id="sw2-answer-hint"></span><div class="sw2-action-pair"><button class="sw2-button sw2-button-outline" data-action="close-editor">收起编辑</button><button class="sw2-button sw2-button-primary" data-action="save-answer">保存候选</button></div></div></div><div id="sw2-answer-status" class="sw2-action-status" role="status" aria-live="polite" hidden></div>',
      '</section></div>' + provenanceHTML(q) + '</div></div><aside class="sw2-discussion-column" aria-label="逐项讨论">' + discussionResizerHTML + '<div class="sw2-talk-header"><div class="sw2-section-title">讨论<small>' + thread.length + ' 条记录</small></div><p>建议与交流 · 保存后手动通知 AI 继续</p></div><div class="sw2-thread" tabindex="0" aria-label="' + escape(q.title) + '的讨论记录">',
      jointGroup ? '<div class="sw2-shared-context">共同讨论：' + escape(jointGroup.title) + '<button class="sw2-button sw2-button-outline" data-action="dg-open" data-id="' + jointGroup.id + '" data-mode="discussion">参与共同讨论</button></div>' : '',
      thread.length ? thread.map(message => (q.superseded_presentations?.includes(message.id) ? '<details class="sw2-previous-proposal"><summary>早期方案建议 · 查看完整历史</summary>' : '') + '<div class="sw2-bubble sw2-bubble-' + actorKind(message.actor) + '"><div class="sw2-bubble-head">' + (message.recovered ? historicalBadge(message.actor) : actorBadge(message.actor)) + "<span>" + (message.shared ? "共同讨论 · " + escape(shortTime(message.at)) : message.kind === "legacy_answer" ? "历史答复 · 非正式口径" : message.kind === "proposal" ? "方案建议" : message.recovered ? "历史 · " + escape(shortTime(message.at)) : escape(shortTime(message.at))) + '</span></div><div class="sw2-bubble-body" data-quote-source="' + escape((message.shared ? jointGroup.id : q.id) + ' · ' + actorLabel(message.actor) + ' · ' + (message.at ? shortTime(message.at) : '方案建议')) + '">' + renderMarkdown(message.shared ? message.text : (q.discussion_display?.[message.id] ?? message.text), discussionScope()) + "</div>" + (message.recovered ? '<details class="sw2-message-source"><summary>查看原文来源</summary>' + escape(sourceName(message.source)) + ' · 由 ' + escape(actorLabel(message.recovered_by)) + ' 回填</details>' : "") + "</div>" + (q.superseded_presentations?.includes(message.id) ? "</details>" : "")).join("") : '<div class="sw2-empty"><strong>开始这题的讨论</strong>建议、选项与实际影响都保留在这里。</div>',
      '</div><div class="sw2-composer sw2-discussion-composer">' + ((q.suggestions || []).length ? '<details class="sw2-choices"><summary>选择讨论方向 · ' + q.suggestions.length + ' 个选项</summary><div class="sw2-suggestions">' + q.suggestions.map(value => '<button class="sw2-suggestion" type="button" data-action="suggest" data-value="' + escape(value) + '">' + escape(value) + '</button>').join('') + '</div></details>' : ''),
      '<button class="sw2-button sw2-button-outline sw2-write-discussion" data-action="compose"' + (composingNow ? ' hidden' : '') + '>' + (jointGroup ? '＋ 写共同讨论留言' : '＋ 写讨论留言') + '</button><div class="sw2-message-editor"' + (composingNow ? '' : ' hidden') + '><div class="sw2-compose-head"><label class="sw2-section-title" for="sw2-message">讨论留言 · Markdown</label><button class="sw2-clear-filter" data-action="close-compose">收起</button></div><textarea id="sw2-message" class="sw2-message-input" placeholder="回复建议、提出问题，或请 AI 整理完整候选口径…">' + escape(messageDrafts[q.id] || '') + '</textarea>',
      '<details class="sw2-discussion-preview" data-record="discussion-preview"><summary>预览讨论（未保存）</summary><div id="sw2-message-preview">' + renderMarkdown(messageDrafts[q.id] || '', discussionScope()) + '</div></details><div class="sw2-message-actions"><span id="sw2-message-hint"></span><small class="sw2-shortcut">' + discussionShortcut + ' 保存</small><button type="button" aria-keyshortcuts="' + discussionShortcutAttribute + '" class="sw2-button sw2-button-primary" data-action="post">保存讨论留言</button></div></div><div id="sw2-message-status" class="sw2-action-status" role="status" aria-live="polite" hidden></div></div></aside>',
    ].join("");
    for (const el of panel.querySelectorAll?.('details[data-record]') || []) el.open = expanded.includes(el.dataset.record);
    for (const [selector, top] of scrollPositions) { const el = panel.querySelector(selector); if (el) el.scrollTop = top; }
    panel.querySelector(".sw2-provenance").open = Boolean(sourceOpen);
    applyDiscussionWidth();
  }

  function applyBusy() {
    if (state.busy) closeSelect();
    root.setAttribute("aria-busy", String(state.busy));
    for (const button of root.querySelectorAll("button")) button.disabled = state.busy;
    for (const field of root.querySelectorAll("#sw2-answer, #sw2-message, .dg-definition")) field.readOnly = state.busy;
    root.querySelector("#sw2-status-filter").disabled = state.busy;
    updateDraftUI();
  }

  function render() {
    const all = questions();
    if (!visible().some(q => q.id === state.selected)) state.selected = visible()[0]?.id || null;
    for (const button of root.querySelectorAll('[data-action="status-filter"]')) button.setAttribute("aria-pressed", String(state.status === button.dataset.status));
    root.querySelector("#sw2-round").textContent = state.snapshot.round || "—";
    root.querySelector("#sw2-total").textContent = all.length;
    root.querySelector("#sw2-open").textContent = all.filter(q => definition(q).draft).length;
    root.querySelector("#sw2-talk").textContent = all.filter(q => q.status === "discussing").length;
    const frozen = all.filter(q => definition(q).current_version).length;
    root.querySelector("#sw2-answered").textContent = frozen;
    root.querySelector("#sw2-completed-label").textContent = "有正式口径";
    root.querySelector("#sw2-search").value = state.search;
    renderGroups(); renderList(); renderDetail(); updateMobileNav(); applyBusy();
  }

  async function change(id, operation, value, stableRequest) {
    const q = byId(id);
    if (!q) throw new Error("问题已不存在：" + id);
    const data = await api("/api/questions/" + id + "/change", { operation, value, expected_revision: q.revision, request_id: stableRequest || requestId() });
    connection("已连接 · 修改已保存");
    const index = questions().findIndex(item => item.id === id);
    if (index >= 0) state.snapshot.questions[index] = data.question;
    // Member edits change group approval tokens and downstream readiness.
    // Read them before rendering the next confirmation; never auto-retry approval.
    if (state.snapshot.decision_groups?.length) {
      const latest = await api("/api/snapshot");
      state.snapshot = latest.snapshot; state.csrf = latest.csrf;
    }
    return byId(id);
  }

  async function saveAnswer(id) {
    const q = byId(id), value = (drafts[id] ?? "").trim();
    if (!value) throw new Error(id + "：请先填写完整候选口径。");
    if (conflict(q)) throw new Error(id + "：候选文本或当前版本已改变，请先比较并选择保留哪份修改。");
    const request = draftRequests[id + ":definition"] ||= requestId();
    await change(id, "definition_draft", value, request);
    editing[id] = false;
    delete drafts[id]; delete draftBases[id]; delete draftRequests[id + ":definition"]; persistDrafts();
  }

  async function saveMessage(id) {
    const value = (messageDrafts[id] || "").trim();
    if (!value) throw new Error(id + "：请先填写讨论内容。");
    const request = draftRequests[id + ":comment"] ||= requestId();
    await change(id, "comment", value, request);
    delete messageDrafts[id]; delete draftRequests[id + ":comment"]; composing[id] = false; persistDrafts();
  }

  async function saveAll() {
    const ids = pending().map(q => q.id), failures = [];
    let saved = 0;
    for (const id of ids) {
      if (!byId(id)) continue;
      try {
        if (Object.hasOwn(drafts, id)) await saveAnswer(id);
        if (messageDrafts[id]?.trim()) await saveMessage(id);
        saved++;
      } catch (error) { const message = friendlyError(error); failures.push(message.startsWith(id + "：") ? message : id + "：" + message); }
    }
    try { await groupUI?.saveAll(); } catch (error) { failures.push(error.message); }
    saved = ids.length - pending().length;
    render();
    if (failures.length) throw new Error("已保存 " + saved + " 项；" + failures.length + " 题未全部保存，草稿保留。\n" + failures.join("\n"));
    return saved;
  }

  function handoffText(excluded = []) {
    const all = questions();
    const lines = ["请复核第 " + state.snapshot.round + " 轮已保存的口径记录。项目路径：" + state.snapshot.project + "。请读取 Freeze/manifest.json 和各问题记录，以项目文件为准。",
      "当前记录 " + all.length + " 项：已回答 " + all.filter(q => q.status === "answered").length + "，有正式口径 " + all.filter(q => definition(q).current_version).length + "，历史讨论 " + all.filter(q => q.status === "historical").length + "，讨论中 " + all.filter(q => q.status === "discussing").length + "，待讨论 " + all.filter(q => q.status === "open").length + "。"];
    if (excluded.length) lines.push("我选择仅交接已保存内容。以下题目的本地未保存草稿未提交：" + excluded.join("、") + "。");
    lines.push("", "全部问题、答复与讨论：");
    for (const q of all) {
      lines.push("", q.id + " " + q.title + " [" + label(q.status) + "]", "提出：" + actorLabel(q.created_by), "历史答复（非正式口径）：" + (q.user_answer || "无"));
      if (q.recovery_classification) lines.push("恢复分类：" + q.recovery_classification.kind + "；当前审阅状态：" + label(q.status));
      const superseded = new Set((q.recovered_records || []).map(record => record.supersedes).filter(Boolean));
      for (const record of q.recovered_records || []) {
        lines.push((superseded.has(record.key) ? "原恢复分类（已修正） · " : "") + recoveryTitle(record.kind) + "：" + record.summary);
        if (record.supersedes) lines.push("修正原恢复记录 " + record.supersedes + "：" + record.reason);
        for (const source of record.sources) lines.push("历史来源：" + sourceName(source));
      }
      const def = definition(q);
      for (const version of def.versions) lines.push("正式口径 v" + version.number + (version.number === def.current_version ? "（当前有效）" : "（旧版本）") + "：\n" + version.text + "\n唯一来源：" + version.source);
      if (def.draft) lines.push("候选 v" + (def.versions.length + 1) + "（尚未确认）" + "：\n" + def.draft.text);
      for (const m of discussionMessages(q)) lines.push("讨论（" + (m.recovered ? historicalActor(m.actor) + "，历史回填；" + (m.at || "时间未记录") + "；" + sourceName(m.source) : actorLabel(m.actor) + "，第 " + m.round + " 轮") + "）：" + (q.discussion_display?.[m.id] ?? m.text));
    }
    if (groupUI) lines.push("", "共同决策组：", JSON.stringify(groupUI.handoff(), null, 2));
    lines.push("", "继续处理要求：",
      "1. 读取项目原治理 skill 及 references/freeze-workbench.md；MCP 可用 get_skill_guide 的 resource 参数读取引用文档。重新读取项目最新记录，保留原编号、讨论和正式历史；本摘要不替代项目文件。",
      "2. 回应已保存的反馈并核查可取得的依据，一次列齐当前可识别的问题。讨论使用 Markdown，写清做法、实际影响、条件与建议；独立含义分段，引用完整编号如 F-000013。机器日志、哈希和自检报告只存 review_note 或 Audit。",
      "3. 比较区集中说明共同规则，用 ## / ### 分级标题组织长讨论、方案和口径，再以短段落或列表展开，不仅靠加粗分段。独立子选择或局部数值使用 {{choice:wait_seconds;等待时长;5秒;10秒}}，解释取值影响和兼容性；只有需要整体比较的联动路线另列，不展开所有组合、不复制整份候选。选择仅表达偏好，不会自动重算或确认规则。",
      "4. AI 将同一决策所需的联动规则组成主题，保留真实依赖并先备齐独立上游。单题正文及建议用 presentation 更新；共同方案用 group-change / freeze_change_group 的 update 更新，并以 comment 保存共同讨论。",
      "5. 对首次候选或人类已开启的修订，按有依据的建议为本轮待决题及组成员保存完整 definition_draft，核对具体条件、单位、时间、边界及缺失/冲突处理。切换偏好后同步检查受影响规则。读回候选和实际比较内容；未备齐项列明编号、缺口和影响，不声称已可确认。",
      "6. 人类确认后，项目问题 JSON 的 definition.current_version 所指版本立即成为唯一正式口径；其他文档引用它。AI 不确认、不覆盖有效版本。新修订需人类开启；旧版保持有效。参数偏好、讨论保存和测试通过都不等于内容完整或已获执行授权。"
    );
    return lines.join("\n");
  }

  function renderHandoff(exclude = false) {
    const items = pending();
    const waiting = items.length > 0 && !exclude;
    root.querySelector("#sw2-handoff-pending").hidden = !waiting;
    root.querySelector("#sw2-handoff-pending").innerHTML = waiting ? "<strong>" + items.length + " 项尚未保存</strong><ul>" + items.map(q => "<li>" + q.id + " · " + escape(q.title) + "（" + [Object.hasOwn(drafts, q.id) ? "候选口径" : "", messageDrafts[q.id]?.trim() ? "留言" : ""].filter(Boolean).join("、") + "）</li>").join("") + "</ul>" : "";
    const area = root.querySelector("#sw2-handoff-text");
    area.hidden = waiting; area.value = waiting ? "" : handoffText(exclude ? items.map(q => q.id) : []);
    root.querySelector("[data-action=handoff-save]").hidden = !waiting;
    root.querySelector("[data-action=handoff-saved]").hidden = !waiting;
    root.querySelector("[data-action=copy]").hidden = waiting;
    root.querySelector("#sw2-copy-status").textContent = waiting ? "" : exclude && items.length ? "已排除 " + items.length + " 题未保存草稿" : "项目已保存内容";
    root.querySelector("#sw2-handoff-status").hidden = true;
  }

  function openHandoff(button) {
    returnFocus = button; renderHandoff(); overlay().hidden = false;
    root.querySelector("#sw2-notice").hidden = true;
    for (const element of root.querySelectorAll(".sw2-app > header, .sw2-app > nav, .sw2-workspace, .sw2-footer")) element.inert = true;
    root.querySelector("[data-action=close]").focus();
  }

  function closeHandoff() {
    if (state.busy) return;

    overlay().hidden = true;
    for (const element of root.querySelectorAll("[inert]")) element.inert = false;
    root.querySelector("#sw2-navigation").inert = drawerMedia.matches ? root.dataset.navOpen !== "true" : root.dataset.navHidden === "true";
    if (returnFocus?.isConnected) returnFocus.focus();
  }

  groupUI = window.CouncilGroups?.({ root, state, api, refresh, render, notice: showNotice, friendlyError, escape, workflowHTML, discussionResizerHTML, discussionShortcut, discussionShortcutAttribute, choiceContext, onOpen: () => showMobileView("detail"), onDraftChange: updateDraftUI, saveCandidate: saveAnswer,
    discardEdits, setDraft: answerDraft, getDraft: id => drafts[id] ?? candidateText(byId(id)), pendingQuestions });
  root.addEventListener("click", async event => {
    const summary = event.target.closest('summary');
    if (summary && root.contains(summary) && summary.parentElement?.tagName === 'DETAILS' && !event.target.closest('a,button,input,select,textarea')) {
      const details = summary.parentElement;
      if (details.animate) { event.preventDefault(); setDisclosure(details, !(disclosureMotions.get(details)?.expanded ?? details.open)); }
      return;
    }
    const directoryLink = event.target.closest(".sw2-directory-link");
    if (directoryLink) {
      event.preventDefault();
      if (state.busy) return;
      persistDrafts();
      if (!storageOK && pending().length) {
        showNotice("浏览器暂存失败，请先保存本轮再切换项目。", "error"); return;
      }
      leavingForDirectory = true; location.assign(directoryLink.href); return;
    }
    const button = event.target.closest("[data-action]");
    if (!button || !root.contains(button)) return;
    const action = button.dataset.action;
    // Let the reference link open its new tab without touching this page's state.
    if (action === 'reference-question') return;
    if (state.busy) return;
    if (action === 'logout') {
      if (pending().length) { showNotice('还有未保存内容，请先保存本轮再退出。', 'info'); return; }
      state.busy = true; applyBusy(); button.textContent = '退出中…';
      try { await api('/api/logout', {}, true); location.reload(); }
      catch (error) { showNotice(friendlyError(error), 'error'); }
      finally { state.busy = false; applyBusy(); button.textContent = '退出'; }
      return;
    }
    if (action === 'quote-selection') {
      const quote = quotedSelection;
      if (!quote || quote.scope !== selected()?.id) { hideQuote(); return; }
      if (appendToDiscussion(quote.text, quote.source)) {
        hideQuote(); window.getSelection()?.removeAllRanges();
        showNotice('引用已加入讨论，请补充意见后保存。', 'info');
      }
      return;
    }
    if (action === 'open-choice' || action === 'open-status') { openSelect(button); return; }
    if (action === 'select-value') { commitSelect(Number(button.dataset.index)); return; }
    if (action === 'close-select') { closeSelect(true); return; }
    if (action === 'clear-choice' && selectMenu?.kind === 'parameter') {
      selectMenu.trigger.value = ''; selectParameter(selectMenu.trigger); updateSelectMenu(); selectList.focus({preventScroll:true}); return;
    }
    if (action === 'choice-discuss') {
      const trigger = selectMenu?.trigger; closeSelect();
      if (trigger?.value) addParameterToDiscussion(trigger); return;
    }
    if (action === 'toggle-nav' || action === 'close-nav') {
      const open = drawerMedia.matches ? root.dataset.navOpen === 'true' : root.dataset.navHidden !== 'true';
      setNavigation(action === 'toggle-nav' && !open);
      if (action === 'close-nav') root.querySelector('#sw2-nav-toggle').focus();
      return;
    }
    if (action === "review-pane") {
      const panel = root.querySelector("#sw2-detail"); panel.dataset.reading = button.dataset.pane;
      for (const tab of root.querySelectorAll('[data-action="review-pane"]')) tab.setAttribute("aria-pressed", String(tab.dataset.pane === button.dataset.pane));
      return;
    }
    if (action === "dismiss-notice") { clearTimeout(noticeTimer); root.querySelector("#sw2-notice").hidden = true; return; }
    if (action === "compose" || action === "close-compose") {
      const joint = state.snapshot.decision_groups?.find(g => g.member_ids.includes(state.selected));
      if (action === "compose" && joint && !messageDrafts[state.selected]?.trim()) { groupUI?.openDiscussion(joint.id); return; }
      composing[state.selected] = action === "compose";
      const editor = root.querySelector(".sw2-message-editor");
      editor.hidden = !composing[state.selected];
      root.querySelector('[data-action="compose"]').hidden = composing[state.selected];
      if (composing[state.selected]) root.querySelector("#sw2-message").focus();
      else root.querySelector('[data-action="compose"]').focus();
      return;
    }
    if (action === 'clear-search') {
      event.preventDefault(); state.search = ''; root.querySelector('#sw2-search').value = '';
      if (!visible().some(q => q.id === state.selected)) state.selected = visible()[0]?.id || null;
      persistDrafts(); render(); root.querySelector('#sw2-search').focus(); return;
    }
    if (action === "group" || action === "clear-filter") {
      groupUI?.clear();
      state.group = action === "group" ? button.dataset.group : "all";
      if (action === "clear-filter") { state.search = ""; state.status = "all"; }
      state.selected = visible()[0]?.id || null; persistDrafts(); render(); return;
    }
    if (action === "status-filter") {
      groupUI?.clear();
      state.status = button.dataset.status;
      state.selected = visible()[0]?.id || null; persistDrafts(); render(); return;
    }
    if (action === "select") {
      if (mobileMedia.matches && state.mobileView === "list") mobileListScroll = window.scrollY;
      state.selected = button.dataset.id; persistDrafts(); renderList(); renderDetail(); updateDraftUI();
      showMobileView("detail"); return;
    }
    if (action === "mobile-back") { showMobileView("list"); return; }
    if (action === "suggest") {
      composing[state.selected] = true; root.querySelector(".sw2-message-editor").hidden = false;
      root.querySelector('[data-action="compose"]').hidden = true;
      const area = root.querySelector("#sw2-message"); area.value = [messageDrafts[state.selected], button.dataset.value].filter(Boolean).join("\n");
      messageDraft(state.selected, area.value); area.focus(); showNotice("选择已填入讨论，尚未保存。", "info", "message"); return;
    }
    if (action === "edit-definition") {
      const q = selected(); editing[q.id] = true; root.querySelector("#sw2-detail").dataset.reading = "wording"; renderDetail(); updateDraftUI();
      root.querySelector("#sw2-answer").focus(); return;
    }
    if (action === "close-editor") {
      if (Object.hasOwn(drafts, state.selected)) { showNotice("请先保存候选修改，再收起编辑。", "info", "answer"); return; }
      editing[state.selected] = false; renderDetail(); updateDraftUI(); return;
    }
    if (action === "use-project" || action === "keep-draft") {
      const q = selected();
      if (action === "use-project") { delete drafts[q.id]; delete draftBases[q.id]; delete draftRequests[q.id + ":definition"]; }
      else draftBases[q.id] = { text: candidateText(q), current: definition(q).current_version };
      persistDrafts(); renderDetail(); updateDraftUI(); showNotice(action === "use-project" ? "已使用项目候选文本。" : "已保留本地候选修改，保存后写入项目。", "info", "answer"); return;
    }
    if (action === "handoff") { openHandoff(button); return; }
    if (action === "close") { closeHandoff(); return; }
    if (action === "handoff-saved") { renderHandoff(true); root.querySelector("#sw2-handoff-text").focus(); return; }
    if (action === "copy") {
      const area = root.querySelector("#sw2-handoff-text");
      try { await navigator.clipboard.writeText(area.value); root.querySelector("#sw2-copy-status").textContent = "已复制"; showNotice("交接说明已复制。"); }
      catch (_) { area.focus(); area.select(); root.querySelector("#sw2-copy-status").textContent = "已选中，请手动复制"; showNotice("自动复制未成功，交接说明已选中。", "info"); }
      return;
    }
    state.busy = true; applyBusy();
    const originalLabel = button.textContent;
    if (action !== "save-all") button.textContent = ({ refresh: "刷新中…", "approve-definition": "确认中…", "begin-definition": "开启中…", "discard-definition": "取消中…" })[action] || "保存中…";
    try {
      const id = state.selected;
      if (action === "refresh") { await refresh(); showNotice("项目记录已刷新 · 第 " + state.snapshot.round + " 轮 · " + questions().length + " 题"); }
      else if (action === "save-all" || action === "handoff-save") {
        const saved = await saveAll();
        if (action === "handoff-save") { renderHandoff(); root.querySelector("#sw2-handoff-text").focus(); }
        showNotice("已保存 " + saved + " 项，全部修改已写入项目。", "success", action === "handoff-save" ? "handoff" : "");
      } else if (action === "save-answer") {
        await saveAnswer(id); render(); showNotice(id + " 候选已保存，尚未确认生效。", "success", "answer", id);
      } else if (action === "post") {
        await saveMessage(id); render();
        if (state.selected === id) {
          const thread = root.querySelector(".sw2-thread"); thread.scrollTop = thread.scrollHeight;
        }
        showNotice(id + " 讨论已保存 · 讨论中", "success", "message", id);
      } else if (action === "begin-definition") {
        await change(id, "definition_begin", null); editing[id] = true; render();
        showNotice("已开启下一版候选，当前正式版本继续有效。", "success", "answer", id);
      } else if (action === "discard-definition") {
        await change(id, "definition_discard", discardEdits([id])[id] || null);
        reconcileDrafts(); persistDrafts(); editing[id] = false; render();
        showNotice("已取消修订，候选内容已留存；原正式口径和讨论未变。", "success", "answer", id);
      } else if (action === "approve-definition") {
        if (Object.hasOwn(drafts, id) || messageDrafts[id]?.trim()) throw new Error("请先保存候选修改和讨论，再确认完整文本。");
        await change(id, "definition_approve", (definition(byId(id)).draft?.approval_token || definition(byId(id)).draft?.text_sha256)); editing[id] = false; render();
        showNotice("正式口径已生效；网页与项目读取同一版本。", "success", "answer", id);
      }
    } catch (error) {
      if (error.network || error.status >= 500) connection("连接异常 · 请重试刷新", "error");
      if (action === "handoff-save") renderHandoff();
      const target = ["begin-definition", "discard-definition", "approve-definition", "save-answer"].includes(action) ? "answer" : action === "post" ? "message" : action === "handoff-save" ? "handoff" : "";
      showNotice("操作未完成：" + friendlyError(error), "error", target);
    } finally {
      if (action !== "save-all") button.textContent = action === "refresh" ? (button.id === "sw2-mobile-refresh" ? "刷新" : "刷新项目记录") : originalLabel;
      state.busy = false; applyBusy();
      if (overlay().hidden && !button.isConnected) {
        const focusTarget = ({ post: '#sw2-message', "save-answer": '[data-action="edit-definition"]',
          "approve-definition": '[data-action="begin-definition"]', "begin-definition": '#sw2-answer',
          "discard-definition": '.sw2-begin-definition' })[action];
        if (focusTarget) root.querySelector(focusTarget)?.focus({ preventScroll: true });
      }
      if (!overlay().hidden) root.querySelector(action === "handoff-save" && !pending().length ? "#sw2-handoff-text" : "[data-action=close]").focus();
    }
  });


  root.querySelector("#sw2-search").addEventListener("input", event => {
    groupUI?.clear(); state.search = event.target.value;
    if (!visible().some(q => q.id === state.selected)) state.selected = visible()[0]?.id || null;
    persistDrafts(); renderList(); renderDetail(); updateMobileNav(); updateDraftUI();
  });
  root.addEventListener("input", event => {
    if (event.target.matches?.('[data-choice-control]')) return;
    if (event.target.closest?.(".dg-discussion")) updateDraftUI();
    if (event.target.id === "sw2-answer") { root.querySelector("#sw2-answer-preview").innerHTML = renderMarkdown(event.target.value); answerDraft(state.selected, event.target.value); root.querySelector("#sw2-answer-status").hidden = true; }
    if (event.target.id === "sw2-message") { messageDraft(state.selected, event.target.value); root.querySelector("#sw2-message-status").hidden = true; }
  });

  setNavigation(!drawerMedia.matches);
  drawerMedia.addEventListener('change', () => setNavigation(!drawerMedia.matches));
  mobileMedia.addEventListener("change", () => {
    state.mobileView = "list"; updateMobileNav();
    if (mobileMedia.matches) window.scrollTo(0, 0);
  });
  const snapshotVersion = snapshot => JSON.stringify([snapshot.revision, snapshot.round, snapshot.questions.map(q => [q.id, q.revision])]);
  async function checkUpdates() {
    if (state.busy || document.hidden || !state.snapshot.project) return;
    try {
      const data = await api("/api/snapshot");
      if (snapshotVersion(data.snapshot) !== snapshotVersion(state.snapshot)) {
        state.remoteUpdate = true;
        root.querySelector("#sw2-update").textContent = "记录有更新 · 刷新";
        root.querySelector("#sw2-mobile-refresh").textContent = "刷新 ●";
        root.querySelector("#sw2-mobile-refresh").dataset.updated = "true";
        connection("有新记录 · 点击刷新读取", "info");
      } else connection("项目记录已同步");
    } catch (_) { connection("连接异常 · 本地草稿保留", "error"); }
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) checkUpdates(); });
  setInterval(checkUpdates, 10000);
  document.addEventListener("click", event => {
    const filters = root.querySelector("#sw2-filter-disclosure");
    if (filters.open && !event.composedPath().includes(filters) && !event.composedPath().includes(selectPopover)) setDisclosure(filters, false);
  });
  document.addEventListener("keydown", event => {
    if (event.key === 'Escape' && quotedSelection) { hideQuote(); return; }
    if (overlay().hidden && event.key === 'Escape' && root.dataset.navOpen === 'true') {
      event.preventDefault(); setNavigation(false); root.querySelector('#sw2-nav-toggle').focus(); return;
    }
    if (overlay().hidden && event.key === '/' && !event.target.closest?.('input,textarea,select,[contenteditable]')) {
      event.preventDefault(); setNavigation(true); root.querySelector('#sw2-search').focus(); return;
    }
    const filters = root.querySelector("#sw2-filter-disclosure");
    if (event.key === "Escape" && filters.open && overlay().hidden) {
      event.preventDefault(); setDisclosure(filters, false); root.querySelector("#sw2-filter-toggle").focus(); return;
    }
    if (overlay().hidden) return;
    if (event.key === "Escape") { event.preventDefault(); closeHandoff(); return; }
    if (event.key !== "Tab") return;
    const dialog = root.querySelector(".sw2-dialog");
    const focusable = [...dialog.querySelectorAll("button, textarea, [tabindex]")].filter(e => !e.disabled && !e.hidden && e.getClientRects().length && e.tabIndex >= 0);
    const first = focusable[0], last = focusable.at(-1);
    if (!first) { event.preventDefault(); dialog.focus(); return; }
    if (!dialog.contains(document.activeElement) || (event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
      event.preventDefault(); (event.shiftKey ? last : first).focus();
    }
  });
  window.addEventListener('popstate', () => {
    if (!routeInitialized) return;
    readingHistory = true;
    try { persistDrafts(); applyRoute(); render(); persistDrafts(); }
    finally { readingHistory = false; }
  });
  window.addEventListener("beforeunload", event => {
    persistDrafts();
    if (pending().length && !leavingForDirectory) { event.preventDefault(); event.returnValue = ""; }
  });
  refresh().then(() => {
    if (pending().length) showNotice("已恢复 " + pending().length + " 题未保存草稿。", "info");
    else root.querySelector("#sw2-save-label").textContent = "项目记录已同步";
  }).catch(error => {
    connection("读取失败 · 请重试", "error");
    root.querySelector("#sw2-detail").innerHTML = '<div class="sw2-empty"><strong>暂时无法读取项目</strong>' + escape(friendlyError(error)) + '<br><button class="sw2-button sw2-button-outline" data-action="refresh">重试读取</button></div>';
    showNotice("读取失败：" + friendlyError(error), "error");
  });
})();

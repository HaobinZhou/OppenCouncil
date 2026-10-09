(() => {
  const form = document.getElementById('login-form'), message = document.getElementById('message');
  const password = document.getElementById('password'), confirmation = document.getElementById('confirmation');
  const submit = document.getElementById('submit'), reveal = document.getElementById('reveal');
  const target = location.pathname + location.search;
  let setup = false, busy = false;
  // Old key fragments are no longer credentials; keep the intended question/group route.
  if (location.hash) history.replaceState(null, '', target);
  const feedback = (text, error = false) => { message.textContent = text; message.dataset.error = String(error); };
  async function request(path, body) {
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(path, {credentials:'same-origin',cache:'no-store',signal:controller.signal,
        ...(body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {})});
      const data = await response.json();
      if (!response.ok) { const error = new Error(data.error || '暂时无法登录，请重试。'); error.status = response.status; throw error; }
      return data;
    } finally { clearTimeout(timeout); }
  }
  async function load() {
    const data = await request('/api/auth');
    if (data.authenticated) { location.replace(target); return; }
    setup = data.setup_required;
    document.getElementById('mode-tag').textContent = setup ? '首次使用' : '密码访问';
    document.getElementById('heading').textContent = setup ? '设置站点密码' : '欢迎回来';
    document.getElementById('intro').textContent = setup ? '设置一个 8–128 字符的密码，用于访问本站所有项目。' : '输入站点密码，继续审阅与讨论。';
    document.getElementById('confirmation-row').hidden = !setup;
    password.autocomplete = setup ? 'new-password' : 'current-password';
    confirmation.required = setup;
    submit.textContent = setup ? '设置密码并进入' : '进入工作台';
    form.hidden = false;
  }
  reveal.addEventListener('click', () => {
    const visible = password.type === 'password';
    password.type = confirmation.type = visible ? 'text' : 'password';
    reveal.textContent = visible ? '隐藏' : '显示';
    reveal.setAttribute('aria-label', visible ? '隐藏密码' : '显示密码');
    reveal.setAttribute('aria-pressed', String(visible));
  });
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    if (password.value.length < 8 || password.value.length > 128 || !password.value.trim()) {
      feedback('密码需为 8–128 个字符，不能全为空格。', true); password.focus(); return;
    }
    if (setup && password.value !== confirmation.value) {
      feedback('两次输入的密码不一致。', true); confirmation.focus(); return;
    }
    busy = true; submit.disabled = true; submit.textContent = setup ? '正在设置…' : '正在登录…'; feedback('');
    try {
      await request(setup ? '/api/setup' : '/api/login', {password:password.value,...(setup ? {confirmation:confirmation.value} : {})});
      password.value = confirmation.value = ''; feedback('登录成功，正在打开工作台…'); location.replace(target);
    } catch (error) {
      feedback(error instanceof TypeError || error.name === 'AbortError' ? '连接未完成，请重试；密码不会保存在浏览器草稿中。' : error.message, true);
      if (error.status === 409) await load().catch(() => {});
    } finally { busy = false; submit.disabled = false; submit.textContent = setup ? '设置密码并进入' : '进入工作台'; }
  });
  load().catch(() => { feedback('暂时无法连接工作台，请刷新页面重试。', true); });
})();

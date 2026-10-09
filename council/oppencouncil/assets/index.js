(() => {
  const colors = ["#7250e3", "#00a9c3", "#ef5593", "#f29c2e", "#18ab83", "#4285eb"];
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const button = document.querySelector("#refresh"), status = document.querySelector("#status");
  const logout = document.querySelector('#logout');
  let loading = false, lastItems = "", csrf = '';
  async function load(manual = false) {
    if (loading) return;
    loading = true; button.disabled = true; button.textContent = "刷新中…";
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/api/projects", {credentials:"same-origin",cache:"no-store",signal:controller.signal});
      const data = await response.json();
      if (response.status === 401) { location.reload(); return; }
      if (!response.ok) throw new Error("项目目录暂时无法读取。");
      csrf = data.csrf; logout.hidden = !data.auth_required;
      const items = data.projects, key = JSON.stringify(items);
      document.querySelector("#count").textContent = "· " + items.length;
      if (key !== lastItems) {
        lastItems = key;
        document.querySelector("#projects").innerHTML = items.length ? items.map((p, index) => {
          const date = p.updated_at ? new Date(p.updated_at).toLocaleString() : "暂无记录";
          const body = '<div class="meta"><span>' + (p.available ? "第 " + p.round + " 轮 · " + p.total + " 题" : "") + '</span></div><h2>' + escape(p.name) + '</h2>' +
            (p.available ? '<div class="stats"><div class="stat open"><strong>' + p.open + '</strong>待讨论</div><div class="stat talk"><strong>' + p.discussing + '</strong>讨论中</div><div class="stat answered"><strong>' + (p.formal || 0) + '</strong>正式口径' + '</div></div><div class="meta">' + escape(date) + '</div><span class="enter">进入工作台 <span aria-hidden="true">→</span></span>' : '<div class="unavailable">项目暂不可用，请检查所在磁盘或目录后刷新。</div>');
          return p.available ? '<a class="card" style="--accent:' + colors[index % colors.length] + '" href="' + escape(p.url) + '">' + body + '</a>' : '<article class="card" style="--accent:' + colors[index % colors.length] + '">' + body + '</article>';
        }).join("") : '<div class="empty"><strong>还没有协作项目</strong>请让 Codex 为项目打开 Council 工作台，项目会显示在这里。</div>';
      }
      status.textContent = "已同步 · " + new Date().toLocaleTimeString();
      if (manual) status.textContent = "目录已刷新 · " + items.length + " 个项目";
    } catch (error) {
      status.textContent = "读取失败 · 请重试刷新";
      if (!lastItems) document.querySelector("#projects").innerHTML = '<div class="empty"><strong>暂时无法读取目录</strong>检查工作台连接，然后点击“刷新目录”。</div>';
    } finally { clearTimeout(timeout); loading = false; button.disabled = false; button.textContent = "刷新目录"; }
  }
  button.addEventListener("click", () => load(true));
  logout.addEventListener('click', async () => {
    logout.disabled = true; logout.textContent = '退出中…';
    try {
      const response = await fetch('/api/logout', {method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-Freeze-CSRF':csrf},body:'{}'});
      if (response.ok || response.status === 401) location.reload();
      else throw new Error('退出失败，请刷新后重试。');
    } catch (_) { status.textContent = '退出未完成，请检查连接后重试。'; }
    finally { logout.disabled = false; logout.textContent = '退出'; }
  });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
  setInterval(() => { if (!document.hidden) load(); }, 15000);
  load();
})();

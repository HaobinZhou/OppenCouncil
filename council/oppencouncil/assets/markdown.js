/* Presentation only: the exact Markdown source remains the stored authority. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./vendor/markdown-it.min.js'));
  else root.CouncilMarkdown = factory(root.markdownit);
})(typeof globalThis !== 'undefined' ? globalThis : this, function (markdownit) {
  const md = markdownit({ html: false, breaks: true, linkify: false, typographer: false });
  const choiceKey = (scope, id) => scope + ':' + id;
  const appendPreference = (existing, text) => {
    const before = String(existing || '').trimEnd();
    return before + (before && !/[。！？；：.!?;:]$/.test(before) ? '；' : '') + text;
  };
  const quoteLiteral = text => String(text).replace(/([\\`*_{}\[\]()<>#!|~.+-])/g, '\\$1');
  const appendQuote = (existing, source, text) => {
    const before = String(existing || '').trimEnd();
    const block = [quoteLiteral(source), '', ...String(text).trim().split(/\r?\n/).map(quoteLiteral)].map(line => '> ' + line).join('\n');
    return (before ? before + '\n\n' : '') + block + '\n\n';
  };
  // Semicolons keep this extension usable inside ordinary Markdown tables.
  md.inline.ruler.before('text', 'parameter_choice', (state, silent) => {
    if (!state.env.choiceScope || state.linkLevel || !state.src.startsWith('{{choice', state.pos)) return false;
    const match = /^\{\{choice[:：]([^{}\n]+)\}\}/.exec(state.src.slice(state.pos));
    if (!match) return false;
    const [id, label, ...values] = match[1].split(/[;；]/).map(value => value.trim());
    if (!/^[a-zA-Z][a-zA-Z0-9_-]{0,63}$/.test(id) || !label || label.length > 80 || values.length < 2 || values.length > 12 ||
        values.some(value => !value || value.length > 120) || new Set(values).size !== values.length) return false;
    if (!silent) {
      const token = state.push('council_choice', 'span', 0);
      token.meta = {id, label, values}; token.content = match[0];
    }
    state.pos += match[0].length;
    return true;
  });
  md.renderer.rules.council_choice = (tokens, idx, _options, env) => {
    const {id, label, values} = tokens[idx].meta, escape = md.utils.escapeHtml;
    const key = choiceKey(env.choiceScope, id), signature = JSON.stringify([label, ...values]);
    const saved = env.choiceValues?.[key];
    const selected = saved?.signature === signature && values.includes(saved.value) ? saved.value : '';
    return '<span class="sw2-inline-choice"><button type="button" class="sw2-choice-trigger" data-action="open-choice" data-choice-control data-choice-key="'+escape(key)+'" data-choice-signature="'+escape(signature)+'" data-choice-label="'+escape(label)+'" value="'+escape(selected)+'" aria-label="'+escape(label+'：'+(selected || '未选择'))+'" aria-haspopup="listbox" aria-controls="sw2-select-list" aria-expanded="false">'+escape(selected || label)+'</button></span>';
  };
  // Use Markdown's delimiter pairing, relaxing only Chinese punctuation beside **.
  // Token construction follows markdown-it's MIT-licensed emphasis rule.
  const chinesePunctuation = char => /[\u2014\u2018\u2019\u201c\u201d\u2026\u3001-\u303f\uff01-\uff65]/u.test(char) && /\p{P}/u.test(char);
  md.inline.ruler.before('emphasis', 'chinese_strong', (state, silent) => {
    if (silent || state.src[state.pos] !== '*') return false;
    const delimiters = state.scanDelims(state.pos, true);
    if (delimiters.length !== 2) return false;
    const before = state.src[state.pos - 1] || ' ', after = state.src[state.pos + 2] || ' ';
    const open = delimiters.can_open || chinesePunctuation(after);
    const close = delimiters.can_close || chinesePunctuation(before);
    if (open === delimiters.can_open && close === delimiters.can_close) return false;
    for (let i = 0; i < 2; i++) {
      state.push('text', '', 0).content = '*';
      state.delimiters.push({ marker:42, length:2, token:state.tokens.length - 1, end:-1, open, close });
    }
    state.pos += 2;
    return true;
  });
  // Resolve only actual question IDs in prose, never code or existing links.
  md.core.ruler.after('text_join', 'question_references', state => {
    const ids = new Set(state.env.questionIds || []);
    if (!ids.size) return;
    for (const block of state.tokens) {
      if (block.type !== 'inline') continue;
      let linkDepth = 0;
      block.children = block.children.flatMap(token => {
        if (token.type === 'link_open') linkDepth++;
        if (token.type === 'link_close') linkDepth--;
        if (linkDepth || token.type !== 'text') return [token];
        const urls = [...token.content.matchAll(/(?:https?:\/\/|mailto:|www\.)[^\s<>]+/g)];
        const result = []; let start = 0;
        for (const match of token.content.matchAll(/F-\d{6}/g)) {
          const id = match[0], at = match.index, end = at + id.length;
          if (urls.some(url => at >= url.index && at < url.index + url[0].length)) continue;
          if (!ids.has(id) || /[A-Za-z0-9_./-]/.test(token.content[at - 1] || '') || /[A-Za-z0-9_/-]/.test(token.content[end] || '') || /^\.[A-Za-z0-9]/.test(token.content.slice(end))) continue;
          const text = new state.Token('text', '', 0); text.content = token.content.slice(start, at); result.push(text);
          const opening = new state.Token('link_open', 'a', 1);
          opening.attrs = [['href', '?question=' + id], ['data-action', 'reference-question'], ['data-id', id]];
          const label = new state.Token('text', '', 0); label.content = id;
          result.push(opening, label, new state.Token('link_close', 'a', -1)); start = end;
        }
        if (!result.length) return [token];
        const tail = new state.Token('text', '', 0); tail.content = token.content.slice(start); result.push(tail);
        return result;
      });
    }
  });
  const validate = md.validateLink.bind(md);
  md.validateLink = url => validate(url) && !/^data:/i.test(url);
  const link = md.renderer.rules.link_open || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options));
  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    tokens[idx].attrSet('target', '_blank');
    tokens[idx].attrSet('rel', 'noopener noreferrer');
    return link(tokens, idx, options, env, self);
  };
  // Images remain explicit references, without loading remote content on review.
  md.renderer.rules.image = (tokens, idx) => {
    const token = tokens[idx], escape = md.utils.escapeHtml;
    const title = token.content || '图片';
    return '<a href="'+escape(token.attrGet('src') || '')+'" target="_blank" rel="noopener noreferrer">'+escape(title)+'</a>';
  };
  md.renderer.rules.table_open = () => '<div class="sw2-markdown-table" tabindex="0" role="region" aria-label="内容表格"><table>\n';
  md.renderer.rules.table_close = () => '</table></div>\n';
  return { render: (text, context = {}) => '<div class="sw2-markdown">'+md.render(String(text ?? ''), context)+'</div>', appendPreference, appendQuote };
});

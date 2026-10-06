// 8.11 — lista della spesa della settimana applicata e report PDF.

function shoppingBlock(weekStart) {
  const box = element('div', undefined, 'shopping-block');
  const actions = element('div', undefined, 'meal-actions');
  const all = element('label', undefined, 'small inline-check');
  const allBox = element('input');
  allBox.type = 'checkbox';
  all.append(allBox, document.createTextNode(' Includi i pasti già consumati'));
  const show = element('button', '🛒 Lista della spesa', 'secondary small');
  show.type = 'button';
  const pdf = element('a', '⇩ Report PDF', 'ghost small button-link');
  const query = () => '?include_all=' + (allBox.checked ? 'true' : 'false');
  const syncPdf = () => (pdf.href = '/api/week/' + weekStart + '/report.pdf' + query());
  syncPdf();
  pdf.download = 'piano-' + weekStart + '.pdf';
  const out = element('div', undefined, 'shopping-list');
  let open = false;
  const load = async () => {
    out.replaceChildren(element('p', 'Preparo la lista…', 'muted small'));
    try {
      out.replaceChildren(shoppingList(await api('week/' + weekStart + '/shopping-list' + query())));
    } catch (e) {
      out.replaceChildren(element('p', e.code === 'week_not_applied' ? 'Applica prima un piano a questa settimana.' : e.message, 'error'));
    }
  };
  show.onclick = () => {
    open = !open;
    show.textContent = open ? '🛒 Nascondi la spesa' : '🛒 Lista della spesa';
    open ? load() : out.replaceChildren();
  };
  allBox.onchange = () => {
    syncPdf();
    if (open) load();
  };
  actions.append(show, pdf, all);
  box.append(actions, out);
  return box;
}

function shoppingList(r) {
  const box = element('div');
  box.append(element('p', (r.scope === 'remaining_unconsumed_meals' ? 'Pasti ancora da consumare' : 'Tutti i pasti della settimana') + ': ' + r.included_meals, 'muted small'));
  if (!r.items.length && !r.trace_condiments?.length) {
    box.append(element('p', 'Niente da comprare per i pasti inclusi.', 'muted'));
    return box;
  }
  const byDept = new Map();
  r.items.forEach((it) => {
    const d = it.department || 'Altro';
    if (!byDept.has(d)) byDept.set(d, []);
    byDept.get(d).push(it);
  });
  [...byDept.keys()].sort((a, b) => a.localeCompare(b, 'it')).forEach((dept) => {
    box.append(element('h4', dept, 'shopping-dept'));
    const ul = element('ul', undefined, 'shopping-items');
    byDept.get(dept).forEach((it) => {
      const li = element('li');
      const name = it.product_name ? it.product_name + (it.brand ? ' (' + it.brand + ')' : '') : it.name;
      li.append(element('span', name, 'shopping-name'), element('strong', it.grams != null ? fmt0(it.grams) + ' g' : 'Non disponibile'));
      const note = [];
      if (it.packages) note.push(it.packages + ' conf. da ' + fmt0(it.package_g) + ' g');
      if (it.occurrences > 1) note.push('in ' + it.occurrences + ' pasti');
      if (note.length) li.append(element('span', note.join(' · '), 'muted small'));
      ul.append(li);
    });
    box.append(ul);
  });
  if (r.trace_condiments?.length) {
    box.append(element('h4', 'Condimenti in traccia', 'shopping-dept'));
    box.append(element('p', r.trace_condiments.map((t) => t.name).join(', '), 'small'));
  }
  if (r.unresolved?.length) {
    box.append(element('p', 'Da verificare (composizione non nota): ' + r.unresolved.map((u) => (u.food?.name || u.food?.id || '?') + (u.grams ? ' ' + fmt0(u.grams) + ' g' : '')).join(', '), 'notice'));
  }
  (r.warnings || []).forEach((w) => box.append(element('p', w.message || String(w), 'notice')));
  return box;
}

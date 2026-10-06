// 8.7 — piatti già decisi per la settimana e ricette preferite.
const lockedSlots = { lunch: 'Pranzo', dinner: 'Cena' };

async function renderLockedDishes() {
  const box = $('week-locked');
  const week = $('week-start').value;
  if (!box || !week) return;
  box.replaceChildren(element('p', 'Carico i piatti decisi…', 'muted small'));
  let data, prefs, presets;
  try {
    [data, prefs, presets] = await Promise.all([
      api('week/' + week + '/locked-dishes'),
      api('recipes/preferences'),
      rebalanceCatalog ? Promise.resolve(rebalanceCatalog) : api('rebalance/presets'),
    ]);
    rebalanceCatalog = presets;
  } catch (e) {
    return box.replaceChildren(element('p', e.message, 'error'));
  }
  if ($('week-start').value !== week) return;
  box.replaceChildren(element('h3', 'Piatti già decisi'), element('p', 'Una cena in pizzeria, la lasagna della domenica: Optees li tiene fissi e bilancia il resto della settimana. Valgono dalla prossima generazione.', 'muted small'));
  const list = element('ul', undefined, 'locked-list');
  (data.locked_dishes || []).forEach((d) => {
    const li = element('li');
    const src = d.preset || (d.provenance?.source === 'preset' ? { id: d.provenance.preset_id, size: d.provenance.size } : null);
    const preset = src && presets.presets?.[src.id];
    const kcal = d.nutrients?.kcal ? ' (' + fmt0(d.nutrients.kcal.min) + '–' + fmt0(d.nutrients.kcal.max) + ' kcal)' : '';
    const what = (preset ? preset.name + ' · ' + (preset.sizes?.[src.size]?.label || src.size).toLowerCase() : d.title || d.recipe?.id || src?.id) + kcal;
    li.append(element('span', parseDate(d.date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' }) + ' · ' + lockedSlots[d.slot], 'muted'), element('strong', what + (d.recipe?.portions > 1 ? ' × ' + d.recipe.portions : '')));
    const del = element('button', '✕', 'icon-button small');
    del.type = 'button';
    del.setAttribute('aria-label', 'Togli ' + what);
    del.onclick = async () => {
      del.disabled = true;
      try {
        await api('week/' + week + '/locked-dishes/' + d.date + '/' + d.slot, 'DELETE');
        renderLockedDishes();
      } catch (e) {
        message(e.message);
        del.disabled = false;
      }
    };
    li.append(del);
    list.append(li);
  });
  if (list.childElementCount) box.append(list);
  box.append(lockedForm(week, prefs, presets));
  const pending = (prefs.recipes || []).filter((r) => r.solver_status !== 'ready');
  const ready = (prefs.recipes || []).filter((r) => r.solver_status === 'ready');
  if (prefs.recipes?.length)
    box.append(
      element(
        'p',
        '♥ ' + ready.length + (ready.length === 1 ? ' ricetta preferita pronta' : ' ricette preferite pronte') + ': Optees prova a inserirle (al massimo ' + (prefs.limits?.max_occurrences_per_week ?? 2) + ' volte a settimana).' + (pending.length ? ' ' + pending.length + ' in attesa di verifica degli ingredienti.' : ''),
        'muted small',
      ),
    );
}

function lockedForm(week, prefs, presets) {
  const form = element('form', undefined, 'locked-form');
  const today = isoDate(new Date());
  const day = element('select');
  day.setAttribute('aria-label', 'Giorno');
  for (let i = 0; i < 7; i++) {
    const d = addDays(week, i);
    if (d <= today) continue;
    const o = element('option', parseDate(d).toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric' }));
    o.value = d;
    day.append(o);
  }
  if (!day.options.length) {
    form.append(element('p', 'Non restano giorni da decidere in questa settimana.', 'muted small'));
    return form;
  }
  const slot = element('select');
  slot.setAttribute('aria-label', 'Pasto');
  Object.entries(lockedSlots).forEach(([v, t]) => {
    const o = element('option', t);
    o.value = v;
    slot.append(o);
  });
  slot.value = 'dinner';
  const what = element('select');
  what.setAttribute('aria-label', 'Piatto');
  const ready = (prefs.recipes || []).filter((r) => r.solver_status === 'ready');
  if (ready.length) {
    const g = element('optgroup');
    g.label = 'Ricette preferite';
    ready.forEach((r) => {
      const o = element('option', r.title);
      o.value = 'recipe:' + r.recipe_id;
      g.append(o);
    });
    what.append(g);
  }
  const g = element('optgroup');
  g.label = 'Fuori casa';
  Object.values(presets.presets || {}).forEach((p) =>
    Object.entries(p.sizes || {}).forEach(([size, s]) => {
      if (!s.calories_kcal) return;
      const o = element('option', p.name + ' · ' + (s.label || size).toLowerCase() + ' (' + fmt0(s.calories_kcal.min) + '–' + fmt0(s.calories_kcal.max) + ' kcal)');
      o.value = 'preset:' + p.id + ':' + size;
      g.append(o);
    }),
  );
  what.append(g);
  const portions = element('select');
  portions.setAttribute('aria-label', 'Porzioni');
  [1, 2, 3].forEach((n) => {
    const o = element('option', n + (n === 1 ? ' porzione' : ' porzioni'));
    o.value = n;
    portions.append(o);
  });
  const syncPortions = () => (portions.hidden = !what.value.startsWith('recipe:'));
  what.onchange = syncPortions;
  syncPortions();
  const add = element('button', 'Fissa', 'secondary small');
  add.type = 'submit';
  form.append(day, slot, what, portions, add);
  form.onsubmit = async (e) => {
    e.preventDefault();
    // Recipe ids contain ':' themselves (e.g. demo:pasta-pomodoro), presets are preset:id:size.
    const v = what.value;
    const body = { date: day.value, slot: slot.value };
    if (v.startsWith('recipe:')) body.recipe = { id: v.slice(7), portions: Number(portions.value) };
    else {
      const [, id, size] = v.split(':');
      body.preset = { id, size };
    }
    add.disabled = true;
    try {
      await api('week/' + week + '/locked-dishes', 'PUT', body);
      renderLockedDishes();
    } catch (err) {
      message(err.code === 'slot_already_logged' ? 'Quel pasto è già registrato nel diario.' : err.message);
      add.disabled = false;
    }
  };
  return form;
}

function heartButton(r) {
  const b = element('button', r.preferred ? '♥' : '♡', 'icon-button small heart' + (r.preferred ? ' on' : ''));
  b.type = 'button';
  const label = () => (r.preferred ? 'Togli dalle preferite' : 'Aggiungi alle preferite');
  b.setAttribute('aria-label', label());
  b.title = label();
  b.setAttribute('aria-pressed', String(!!r.preferred));
  b.onclick = async () => {
    b.disabled = true;
    try {
      const res = await api('recipes/' + encodeURIComponent(r.id) + '/preferred', 'PUT', { preferred: !r.preferred });
      r.preferred = res.preferred;
      b.textContent = r.preferred ? '♥' : '♡';
      b.classList.toggle('on', r.preferred);
      b.setAttribute('aria-pressed', String(r.preferred));
      b.setAttribute('aria-label', label());
      b.title = label();
      if (r.preferred) {
        const p = (await api('recipes/preferences')).recipes.find((x) => x.recipe_id === r.id);
        message(p && p.solver_status !== 'ready' ? 'Preferita. Gli ingredienti vanno ancora verificati: entrerà nei piani appena pronta.' : 'Preferita: Optees proverà a inserirla nella settimana.');
      }
    } catch (e) {
      message(e.message);
    } finally {
      b.disabled = false;
    }
  };
  return b;
}

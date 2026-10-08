// Rientro: pasto fuori programma (6.3) o scostamenti registrati nella settimana (B13), docs/backend-handoff-rebalance.md.
const presetIcons = { pizzeria: '🍕', ristorante_italiano: '🍝', sushi: '🍣', kebab: '🥙', aperitivo: '🍹', dolce: '🍰', fast_food: '🍔' };
const sizeNames = { piccolo: 'Piccolo', medio: 'Medio', grande: 'Grande' };
const rangeText = (r, unit = 'kcal') => (!r ? '—' : Math.round(r.min) === Math.round(r.max) ? fmt0(r.min) + ' ' + unit : fmt0(r.min) + '–' + fmt0(r.max) + ' ' + unit);
let rebalanceCatalog = null;
// One open panel at a time: {mode: 'meal'|'diary', date, slot, preset, size, custom, preview, loading, error}.
let rebalance = null;
const signedKcal = (v) => {
  const n = Math.round(v);
  return (n > 0 ? '+' : n < 0 ? '−' : '') + fmt0(Math.abs(n)) + ' kcal';
};
const signedRange = (r) => (!r ? '—' : Math.round(r.min) === Math.round(r.max) ? signedKcal(r.min) : signedKcal(r.min).replace(' kcal', '') + ' … ' + signedKcal(r.max));
function rerenderRebalance() {
  if (rebalance?.mode === 'diary' || !rebalance) renderWeekRebalance();
  if (rebalance?.mode !== 'diary') renderDay(currentDay);
}

async function openRebalance(m, day) {
  $('message').hidden=true;
  rebalance = { mode: 'meal', date: day.date, slot: m.slot, preset: null, size: 'medio', custom: null, preview: null, loading: false };
  renderWeekRebalance();
  try {
    rebalanceCatalog = rebalanceCatalog || (await api('rebalance/presets'));
  } catch (e) {
    rebalance = null;
    return message(e.message);
  }
  renderDay(currentDay);
}
function closeRebalance() {
  const mode = rebalance?.mode;
  rebalance = null;
  if (mode === 'diary') renderWeekRebalance();
  else renderDay(currentDay);
}
function canRebalance(m, day) {
  const today = isoDate(new Date());
  return m.state === 'unknown' && day.date <= today && day.date >= mondayOf(today);
}

async function runRebalancePreview() {
  const r = rebalance;
  if(r.mode==='meal'){r.preview=null;rerenderRebalance();return;}
  const body = r.mode === 'diary' ? { date: r.date, from_diary: true } : { date: r.date, slot: r.slot, ...(r.custom ? { custom: r.custom } : { preset: { id: r.preset, size: r.size } }) };
  // 8.6: activity only when asked; walking is the default suggestion.
  if (r.activity && r.activity !== 'none') body.activity = { mode: r.activity, max_minutes_per_day: 45 };
  r.loading = true;
  r.preview = null;
  r.error = null;
  rerenderRebalance();
  try {
    const preview = await api('rebalance/preview', 'POST', body);
    if (rebalance !== r) return;
    r.preview = preview;
  } catch (e) {
    if (rebalance !== r) return;
    r.error = e.status === 409 && e.code === 'solver_busy' ? 'Optees sta già calcolando: riprova fra qualche secondo.' : e.message;
  } finally {
    if (rebalance === r) {
      r.loading = false;
      rerenderRebalance();
    }
  }
}

async function decideRebalance(action) {
  const r = rebalance;
  try {
    const res = await api('rebalance/' + r.preview.preview_id + '/' + action, 'POST', {});
    rebalance = null;
    const days = res.changed_days?.length || 0;
    const balanced = days + (days === 1 ? ' giorno ribilanciato' : ' giorni ribilanciati');
    if (r.mode === 'diary') message(action === 'apply' ? 'Settimana ribilanciata · ' + balanced : 'Piano lasciato com’è');
    else message(action === 'apply' ? 'Pasto registrato · ' + balanced : 'Pasto registrato · piano invariato');
    await loadHome();
  } catch (e) {
    if (e.status === 409 || e.status === 404) {
      r.preview = null;
      r.error = (e.code === 'slot_already_logged' ? 'Questo pasto è già stato registrato.' : 'Qualcosa è cambiato dopo il calcolo: ricalcola l’impatto.') + ' ';
      rerenderRebalance();
    } else message(e.message);
  }
}

function presetPicker(r) {
  const grid = element('div', undefined, 'preset-grid');
  Object.values(rebalanceCatalog.presets).forEach((p) => {
    const available = Object.values(p.sizes).some((s) => s.available);
    const b = element('button', undefined, 'preset-tile' + (r.preset === p.id && !r.custom ? ' on' : ''));
    b.type = 'button';
    b.disabled = !available;
    b.append(element('span', presetIcons[p.id] || '🍽', 'preset-icon'), element('span', p.name.replace(/\s*\(.*\)$/, ''), 'preset-name'));
    if (!available) {
      b.append(element('span', 'senza dati verificati', 'muted small'));
      b.title = p.note || 'Nessuna fonte nutrizionale verificabile';
    }
    b.onclick = () => {
      r.preset = p.id;
      r.custom = null;
      if (!p.sizes[r.size]?.available) r.size = Object.keys(p.sizes).find((k) => p.sizes[k].available);
      runRebalancePreview();
    };
    grid.append(b);
  });
  const other = element('button', undefined, 'preset-tile' + (r.custom || r.preset === 'custom' ? ' on' : ''));
  other.type = 'button';
  other.append(element('span', '✎', 'preset-icon'), element('span', 'Altro: lo stimo io', 'preset-name'));
  other.onclick = () => {
    r.preset = 'custom';
    r.custom = null;
    r.preview = null;
    renderDay(currentDay);
  };
  grid.append(other);
  return grid;
}

function sizePicker(r) {
  const preset = rebalanceCatalog.presets[r.preset];
  const seg = element('div', undefined, 'segmented size-seg');
  Object.entries(preset.sizes).forEach(([key, s]) => {
    const b = element('button', undefined, 'seg' + (r.size === key ? ' active' : ''));
    b.type = 'button';
    b.disabled = !s.available || r.loading;
    b.append(element('strong', sizeNames[key] || s.label || key), element('span', s.available ? rangeText(s.calories_kcal) : 'n.d.', 'seg-sub'));
    if (s.portion_description) b.title = s.portion_description;
    b.onclick = () => {
      r.size = key;
      runRebalancePreview();
    };
    seg.append(b);
  });
  const box = element('div');
  box.append(seg);
  const desc = preset.sizes[r.size]?.portion_description;
  if (desc) box.append(element('p', desc, 'muted small'));
  return box;
}

// Numbers or ranges like "450-550"; all four nutrients are required by the API.
function customForm(r) {
  const form = element('form', undefined, 'custom-meal');
  const fields = [
    ['kcal', 'Calorie (kcal)', 'es. 900-1100'],
    ['protein_g', 'Proteine (g)', 'es. 30-40'],
    ['carbs_available_g', 'Carboidrati (g)', 'es. 100-130'],
    ['fat_g', 'Grassi (g)', 'es. 35-45'],
  ];
  fields.forEach(([key, label, hint]) => {
    const l = element('label', label);
    const input = element('input');
    input.name = key;
    input.placeholder = hint;
    input.inputMode = 'decimal';
    input.required = true;
    if(r.custom?.[key])input.value=r.custom[key].min+'-'+r.custom[key].max;
    input.oninput=()=>{r.custom=null;};
    l.append(input);
    form.append(l);
  });
  const go = element('button', 'Prepara questa stima', 'primary');
  form.append(go);
  form.onsubmit = (e) => {
    e.preventDefault();
    const custom = {};
    for (const [key, label] of fields) {
      const raw = form.elements[key].value.trim().replace(/,/g, '.');
      const parts = raw.split(/\s*[-–]\s*/).map(Number);
      if (!parts.length || parts.length > 2 || parts.some((v) => !Number.isFinite(v) || v < 0)) return message(label + ': inserisci un numero o un intervallo, es. 450-550');
      custom[key] = { min: Math.min(...parts), max: Math.max(...parts) };
    }
    r.custom = custom;
    runRebalancePreview();
  };
  return form;
}

function itemName(x) {
  return String(x.name || (typeof x.food === 'string' ? x.food : x.food?.name || x.food?.id || '')).split(',')[0];
}
function slotChanges(change) {
  const before = {},
    after = {};
  (change.before || []).forEach((x) => (before[itemName(x)] = (before[itemName(x)] || 0) + (x.grams || 0)));
  (change.after || []).forEach((x) => (after[itemName(x)] = (after[itemName(x)] || 0) + (x.grams || 0)));
  const chips = [];
  Object.keys({ ...before, ...after }).forEach((name) => {
    if (!(name in after)) chips.push(['− ' + name, 'diff-remove']);
    else if (!(name in before)) chips.push(['+ ' + name + ' ' + fmt0(after[name]) + ' g', 'diff-add']);
    else if (Math.round(before[name]) !== Math.round(after[name])) chips.push([name + ' ' + fmt0(before[name]) + '→' + fmt0(after[name]) + ' g', 'diff-change']);
  });
  return chips;
}

function previewView(r) {
  const p = r.preview;
  const box = element('div', undefined, 'rebalance-preview');
  const b = p.budget || {};
  const diary = r.mode === 'diary' || p.source === 'diary';
  if (!diary) {
    const est = p.estimate || {};
    const prov = est.provenance || {};
    const what = prov.source === 'preset' ? (rebalanceCatalog.presets[prov.preset_id]?.name || prov.preset_id) + ' · ' + (sizeNames[prov.size] || prov.size) : 'Stima tua';
    const head = element('div', undefined, 'rb-estimate');
    head.append(element('strong', rangeText(est.nutrients?.kcal)), element('span', what, 'muted'));
    box.append(head);
    if (prov.source === 'preset' && (prov.calculation || prov.sources?.length)) {
      const src = element('details', undefined, 'rb-source');
      src.append(element('summary', 'Da dove vengono i numeri'));
      if (prov.calculation) src.append(element('p', prov.calculation, 'small'));
      const names = [...new Set((prov.sources || []).map((s) => s.source + (s.name ? ' · ' + s.name : '')))];
      if (names.length) src.append(element('p', 'Fonti: ' + names.join('; '), 'muted small'));
      box.append(src);
    }
  }
  // Recorded deviations of the week (B13): exact where known, intervals for estimates.
  const devs = (p.deviations || []).filter((d) => d.difference_kcal && (Math.abs(d.difference_kcal.min) > 0.5 || Math.abs(d.difference_kcal.max) > 0.5));
  if (b.excess_kcal) {
    const head = element('div', undefined, 'rb-estimate');
    head.append(element('strong', signedRange(b.excess_kcal)), element('span', 'scostamento della settimana' + (diary ? '' : ', questo pasto compreso'), 'muted'));
    box.append(head);
  }
  if (devs.length) {
    const list = element('details', undefined, 'rb-source');
    list.append(element('summary', devs.length + (devs.length === 1 ? ' pasto diverso dal previsto' : ' pasti diversi dal previsto')));
    devs.forEach((d) =>
      list.append(
        element(
          'p',
          parseDate(d.date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' }) + ' · ' + (mealMeta[d.slot]?.[0] || d.slot) + ': previsto ' + fmt0(d.planned_kcal) + ', mangiato ' + rangeText(d.consumed_kcal) + ' (' + signedRange(d.difference_kcal) + ')',
          'small',
        ),
      ),
    );
    box.append(list);
  }
  const correction = b.correction_kcal || 0;
  const giving = correction < 0 || (b.excess_kcal && b.excess_kcal.max < 0);
  const status = element('div', undefined, 'rb-status rb-' + p.status);
  const titles = giving
    ? { full: 'Calorie da restituire', partial: 'Restituzione parziale', unchanged: 'Nessuna modifica necessaria', unavailable: 'Rientro non calcolabile' }
    : { full: 'Rientro possibile', partial: 'Rientro parziale', unchanged: 'Nessun rientro necessario', unavailable: 'Rientro non calcolabile' };
  status.append(element('strong', titles[p.status] || p.status));
  if (b.previous_correction_kcal) status.append(element('p', 'Già ' + (b.previous_correction_kcal > 0 ? 'recuperate ' : 'restituite ') + fmt0(Math.abs(b.previous_correction_kcal)) + ' kcal con rientri precedenti di questa settimana.', 'small'));
  if (p.status === 'full' || p.status === 'partial') {
    const n = p.days.filter((d) => Math.abs(d.reduction_kcal) > 0.5).length;
    status.append(element('p', 'I prossimi ' + n + (n === 1 ? ' giorno ' : ' giorni ') + (giving ? (n === 1 ? 'sale' : 'salgono') : n === 1 ? 'scende' : 'scendono') + ' in tutto di ' + fmt0(Math.abs(correction)) + ' kcal, distribuite' + (n > 1 ? ' in modo uniforme' : '') + '.', 'small'));
    const rest = b.remaining_excess_kcal || {};
    const restAbs = { min: Math.min(Math.abs(rest.min || 0), Math.abs(rest.max || 0)), max: Math.max(Math.abs(rest.min || 0), Math.abs(rest.max || 0)) };
    const restText = restAbs.min > 0.5 ? rangeText(restAbs) : 'fino a ' + fmt0(restAbs.max) + ' kcal';
    if (p.status === 'partial') status.append(element('p', 'Resta uno scarto di ' + restText + ' sulla settimana: va bene così, una settimana non si giudica da un pasto.', 'small'));
  } else status.append(element('p', p.reason || p.explanation || '', 'small'));
  if (b.correction_activity_kcal > 0.5)
    status.append(element('p', 'Di cui ' + fmt0(b.correction_diet_kcal) + ' kcal in meno nei pasti e circa ' + fmt0(b.correction_activity_kcal) + ' kcal di movimento in più (stima prudente).', 'small'));
  box.append(status);
  if (!giving && (r.activity || (p.status !== 'unchanged' && p.status !== 'unavailable'))) box.append(activityChoice(r));
  const days = (p.days || []).filter((d) => Math.abs(d.reduction_kcal) > 0.5 || d.changes?.some((c) => slotChanges(c).length));
  if (days.length) {
    const list = element('div', undefined, 'rb-days');
    days.forEach((d) => {
      const row = element('div', undefined, 'rb-day');
      const top = element('div', undefined, 'rb-day-head');
      const delta = -d.reduction_kcal;
      top.append(element('strong', parseDate(d.date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' })), element('span', fmt0(d.before_kcal) + ' → ' + fmt0(d.after_kcal) + ' kcal', 'muted'), element('span', (delta > 0 ? '+' : '−') + fmt0(Math.abs(delta)), delta > 0 ? 'rb-add' : 'rb-cut'));
      row.append(top);
      (d.activities || []).forEach((a) =>
        row.append(element('p', '🚶 ' + activityLabel(a.activity_id) + ' ' + a.minutes + ' min · circa ' + fmt0(a.energy_kcal?.low) + ' kcal (stima prudente)', 'small rb-activity')),
      );
      const chips = element('div', undefined, 'diff-chips');
      (d.changes || []).forEach((c) => slotChanges(c).forEach(([text, cls]) => chips.append(element('span', (mealMeta[c.slot]?.[0] || c.slot) + ': ' + text, 'chip ' + cls))));
      if (chips.childElementCount) {
        const more = element('details', undefined, 'diff-more');
        more.append(element('summary', chips.childElementCount + (chips.childElementCount === 1 ? ' modifica ai pasti' : ' modifiche ai pasti')), chips);
        row.append(more);
      }
      list.append(row);
    });
    box.append(list);
  }
  const lim = p.limits || {};
  const limits = ['Al massimo ' + fmt0(lim.maximum_daily_reduction_kcal ?? 200) + ' kcal di differenza al giorno, mai sotto ' + fmt0(lim.minimum_kcal ?? 1400) + ' kcal e ' + fmt0(lim.minimum_protein_g ?? 45) + ' g di proteine.'];
  if (lim.minimum_weekly_deviation_kcal) limits.push('Scostamenti fino a ' + fmt0(lim.minimum_weekly_deviation_kcal) + ' kcal nella settimana non si compensano.');
  limits.push(p.workout?.explanation || 'Nessun allenamento obbligatorio.');
  box.append(element('p', limits.join(' '), 'muted small'));
  const actions = element('div', undefined, 'actions');
  const can = p.status === 'full' || p.status === 'partial';
  if (can) {
    const ok = element('button', giving ? 'Aggiungi le calorie' : 'Accetta il rientro', 'primary');
    ok.type = 'button';
    ok.onclick = () => ((ok.disabled = true), decideRebalance('apply'));
    actions.append(ok);
  }
  // On the diary path 'keep' only closes the preview: nothing new is recorded.
  const keep = element('button', diary && !can ? 'Chiudi' : 'Lascia il piano com’è', can ? 'secondary' : 'primary');
  keep.type = 'button';
  keep.onclick = () => ((keep.disabled = true), decideRebalance('keep'));
  actions.append(keep);
  box.append(actions);
  return box;
}

const rebalanceActivityModes = [
  ['none', 'Solo i pasti'],
  ['walk', '+ una passeggiata'],
  ['liked', '+ attività che mi piacciono'],
];
function activityLabel(id) {
  return activityNames[id] || String(id).replace(/_/g, ' ');
}
function activityChoice(r) {
  const box = element('div', undefined, 'rb-activity-choice');
  box.append(element('span', 'Vuoi muoverti un po’ invece di togliere tutto dai pasti?', 'muted small'));
  const chips = element('div', undefined, 'chips');
  rebalanceActivityModes.forEach(([mode, text]) => {
    const b = element('button', text, 'chip-toggle' + ((r.activity || 'none') === mode ? ' on' : ''));
    b.type = 'button';
    b.setAttribute('aria-pressed', String((r.activity || 'none') === mode));
    b.onclick = () => {
      if ((r.activity || 'none') === mode) return;
      r.activity = mode;
      runRebalancePreview();
    };
    chips.append(b);
  });
  box.append(chips);
  if (r.activity && r.activity !== 'none') box.append(element('p', 'Al massimo 45 minuti al giorno e metà della correzione: le attività sono facoltative, confermale quando le fai.', 'muted small'));
  return box;
}

// Week-level entry point in Oggi: rebalance from everything recorded so far (B13).
let rebalanceWeek = null;
function renderWeekRebalance(week) {
  if (week) rebalanceWeek = week;
  const box = $('week-rebalance');
  const w = rebalanceWeek;
  const today = isoDate(new Date());
  box.replaceChildren();
  if (!w || w.plan_status !== 'active' || w.week_start !== mondayOf(today) || addDays(w.week_start, 6) === today) return;
  const r = rebalance?.mode === 'diary' ? rebalance : null;
  const panel = element('div', undefined, 'panel compact week-rebalance' + (r ? ' open' : ''));
  const head = element('div', undefined, 'rb-head');
  const text = element('div');
  text.append(element('strong', 'Rientro della settimana'), element('p', 'Grammi diversi, alimenti aggiunti, tolti o sostituiti, pasti saltati: Optees somma le differenze registrate e propone come rientrare nei prossimi giorni, in più o in meno.', 'muted small'));
  head.append(text);
  if (r) {
    const close = element('button', '✕', 'icon-button small');
    close.type = 'button';
    close.setAttribute('aria-label', 'Chiudi');
    close.onclick = closeRebalance;
    head.append(close);
  }
  panel.append(head);
  if (!r) {
    const go = element('button', 'Ribilancia i prossimi giorni', 'secondary small');
    go.type = 'button';
    go.onclick = () => {
      rebalance = { mode: 'diary', date: today, preview: null, loading: false };
      renderDay(currentDay);
      runRebalancePreview();
    };
    panel.append(go);
  } else {
    if (r.loading) {
      const job = element('div', undefined, 'job');
      job.append(element('div', undefined, 'progress-indeterminate'), element('p', 'Optees confronta previsto e mangiato e ricalcola i prossimi giorni…', 'job-text'));
      panel.append(job);
    }
    if (r.error) panel.append(element('p', r.error, 'error'));
    if (r.preview) panel.append(previewView(r));
  }
  box.append(panel);
}

function rebalancePanel(m, day) {
  const r = rebalance;
  const panel = element('div', undefined, 'rebalance-panel');
  const head = element('div', undefined, 'rb-head');
  head.append(element('strong', 'Pasto fuori programma'));
  const close = element('button', '✕', 'icon-button small');
  close.type = 'button';
  close.setAttribute('aria-label', 'Chiudi');
  close.onclick = closeRebalance;
  head.append(close);
  panel.append(head, element('p', 'Capita. Scegli cosa hai mangiato: la registrazione conserva un intervallo. Dopo potrai scegliere se valutare un rientro nei giorni futuri.', 'muted small'));
  panel.append(presetPicker(r));
  if (r.preset && r.preset !== 'custom') panel.append(sizePicker(r));
  if (r.preset === 'custom' && !r.preview && !r.loading) panel.append(customForm(r));
  if (r.loading) {
    const job = element('div', undefined, 'job');
    job.append(element('div', undefined, 'progress-indeterminate'), element('p', 'Optees ricalcola i prossimi giorni…', 'job-text'));
    panel.append(job);
  }
  if (r.error) panel.append(element('p', r.error, 'error'));
  if(r.preset&&r.preset!=='custom'||r.custom){const record=element('button','Registra pasto stimato','primary');record.type='button';record.onclick=async()=>{record.disabled=true;try{const result=await api('rebalance/register','POST',{date:r.date,slot:r.slot,...(r.custom?{custom:r.custom}:{preset:{id:r.preset,size:r.size}})});rebalance=null;renderDay(result);refreshWeek();message('Pasto stimato registrato · piano futuro invariato');}catch(e){r.error=e.message;rerenderRebalance();}};panel.append(record,element('p','La registrazione non modifica i giorni futuri. Potrai valutare il rientro separatamente.','muted small'));}
  if (r.preview) panel.append(previewView(r));
  return panel;
}

function evaluateRecordedRebalance(date){
  if(!currentDay.week_plan_id)return message('Nessun piano attivo da ribilanciare. Il pasto resta registrato.');
  rebalance={mode:'diary',date,preview:null,loading:false};renderDay(currentDay);runRebalancePreview();
}

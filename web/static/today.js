// Oggi, Settimana, Statistiche, Piano settimanale e Progressi (api-contract.md §1).
const isoDate = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const parseDate = (s) => new Date(s + 'T12:00:00');
const addDays = (s, n) => {
  const d = parseDate(s);
  d.setDate(d.getDate() + n);
  return isoDate(d);
};
const mondayOf = (s) => addDays(s, -((parseDate(s).getDay() + 6) % 7));
const longDate = (s) => parseDate(s).toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' });
const shortDate = (s) => parseDate(s).toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
const kcalText = (v) => (v == null ? '—' : fmt0(v) + ' kcal');
const stateMeta = {
  unknown: ['Da registrare', 'state-unknown'],
  as_planned: ['Come previsto', 'state-ok'],
  modified: ['Modificato', 'state-mod'],
  skipped: ['Saltato', 'state-skip'],
  unplanned: ['Fuori piano', 'state-extra'],
};
const modeNames = { sedentary: 'Dieta sedentaria', training: 'Dieta palestra', free: 'Algoritmo libero' };
let homeDate = isoDate(new Date());
let currentDay = null;
let editSlot = null;
const mealAlternatives = {};

async function waitJob(jobId, onTick) {
  const started = Date.now();
  while (Date.now() - started < 240000) {
    const job = await api('jobs/' + jobId);
    if (job.state === 'done') return job;
    if (job.state === 'failed') throw Error(job.error?.detail || 'Calcolo non riuscito');
    if (onTick) onTick(Math.round((Date.now() - started) / 1000));
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw Error('Il calcolo sta impiegando troppo: riprova fra poco');
}

// ---------- Oggi ----------
async function loadHome() {
  const [day, week, stats] = await Promise.all([
    api('day?date=' + homeDate),
    api('week?start=' + mondayOf(homeDate)),
    api('stats/summary'),
  ]);
  renderDay(day);
  renderWeek(week);
  renderStats($('stats-tiles'), stats, week);
}
async function refreshWeek() {
  try {
    renderWeek(await api('week?start=' + mondayOf(homeDate)));
  } catch (e) {
    message(e.message);
  }
}
async function mutate(path, method, body) {
  try {
    renderDay(await api(path, method, body));
    refreshWeek();
  } catch (e) {
    message(e.message);
  }
}

function renderDay(day) {
  currentDay = day;
  const today = isoDate(new Date());
  $('day-title').textContent = longDate(day.date).replace(/^./, (c) => c.toUpperCase());
  const cov = day.totals.coverage;
  const sub = [modeNames[day.mode] || day.mode];
  if (day.day_type === 'training') sub.push('giornata di allenamento');
  if (day.day_type === 'rest') sub.push('giornata di riposo');
  if (cov.planned_slots) sub.push(cov.logged_slots + '/' + cov.planned_slots + ' pasti registrati');
  $('day-sub').textContent = sub.join(' · ');
  $('day-today').hidden = day.date === today;
  const hasPlan = day.meals.some((m) => m.planned);
  $('day-empty').hidden = hasPlan || day.meals.some((m) => m.state !== 'unknown');
  $('day-meals').replaceChildren(...day.meals.map((m) => mealCard(m, day)));
  renderDayProgress(day);
  renderWorkout(day);
}

function itemRow(item, editable) {
  const row = element('div', undefined, 'meal-item');
  const name = element('span', item.name || item.food?.id, 'item-name');
  if (item.source_label && item.food?.source !== 'CREA') name.append(element('span', item.source_label, 'src' + (item.food?.source === 'user_label' ? ' src-user' : ' src-brand')));
  row.append(name);
  if (editable) {
    const input = element('input', undefined, 'qty-input');
    const usesUnits = item.units != null;
    input.type = 'number';
    input.min = usesUnits ? 1 : 1;
    input.step = usesUnits ? 1 : 5;
    input.value = usesUnits ? item.units : item.grams;
    input.setAttribute('aria-label', 'Quantità di ' + (item.name || 'alimento'));
    input.onchange = () => {
      const value = Math.round(Number(input.value));
      if (!value) return;
      mutate('diary/entries/' + item.id, 'PATCH', usesUnits ? { units: value } : { grams: value });
    };
    const unit = element('span', usesUnits ? 'conf.' : 'g', 'muted');
    const remove = element('button', '✕', 'icon-button small remove');
    remove.type = 'button';
    remove.title = 'Togli';
    remove.setAttribute('aria-label', 'Togli ' + (item.name || 'alimento'));
    remove.onclick = () => mutate('diary/entries/' + item.id, 'DELETE');
    const qty = element('span', undefined, 'item-edit');
    qty.append(input, unit, remove);
    row.append(qty);
  } else {
    row.append(element('span', fmt0(item.grams) + ' g' + (item.units ? ' · ' + item.units + ' conf.' : ''), 'item-qty'));
  }
  return row;
}

function foodSearch(day, slot) {
  const box = element('div', undefined, 'food-search');
  const input = element('input');
  input.type = 'search';
  input.placeholder = 'Aggiungi un alimento: es. yogurt, mela, ricotta…';
  input.setAttribute('aria-label', 'Cerca un alimento da aggiungere');
  const results = element('div', undefined, 'food-results');
  let timer = null;
  input.oninput = () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) return results.replaceChildren();
    timer = setTimeout(async () => {
      try {
        // Foods with complete values first: unknown values would leave the day total incomplete.
        const foods = (await api('foods/search?q=' + encodeURIComponent(q) + '&limit=12')).sort((a, b) => (a.per_100g.kcal == null) - (b.per_100g.kcal == null)).slice(0, 8);
        results.replaceChildren(
          ...foods.map((f) => {
            const b = element('button', undefined, 'food-result');
            b.type = 'button';
            b.append(element('strong', f.name), element('span', [f.brand, f.source_label, f.per_100g.kcal != null ? fmt0(f.per_100g.kcal) + ' kcal/100 g' : 'senza valori nutrizionali: il totale resterà incompleto'].filter(Boolean).join(' · '), 'muted'));
            if (f.per_100g.kcal == null) b.classList.add('incomplete');
            b.onclick = () => mutate('diary/entries', 'POST', { date: day.date, slot, food: f.food, ...(f.unit_g ? { units: 1 } : { grams: 100 }) });
            return b;
          }),
        );
        if (!foods.length) results.append(element('p', 'Nessun alimento trovato', 'muted'));
      } catch (e) {
        message(e.message);
      }
    }, 250);
  };
  box.append(input, results);
  return box;
}

function mealCard(m, day) {
  const meta = mealMeta[m.slot] || [m.slot, '•'];
  const state = stateMeta[m.state] || [m.state, ''];
  const card = element('article', undefined, 'meal-card ' + state[1]);
  const head = element('div', undefined, 'meal-head');
  head.append(element('span', meta[1], 'meal-icon'), element('h3', meta[0]), element('span', state[0], 'chip state-chip'));
  const kcal = m.eaten ? m.eaten.kcal : m.planned?.kcal;
  head.append(element('span', kcalText(kcal), 'meal-kcal'));
  card.append(head);

  const editing = editSlot === m.slot && m.state !== 'skipped' && (m.state !== 'unknown' || !m.planned);
  const list = element('div', undefined, 'meal-items');
  const items = m.eaten ? m.eaten.items : m.planned ? m.planned.items : [];
  if (m.state === 'skipped') list.append(element('p', 'Pasto saltato: conta come zero calorie.', 'muted'));
  else if (!items.length) list.append(element('p', m.planned ? 'Nessun alimento' : 'Niente di previsto per questo pasto.', 'muted'));
  else items.forEach((i) => list.append(itemRow(i, editing)));
  card.append(list);
  if (editing) card.append(foodSearch(day, m.slot));
  if (m.state === 'modified' && m.planned) {
    const planned = element('details', undefined, 'planned-ref');
    planned.append(element('summary', 'Previsto: ' + kcalText(m.planned.kcal)));
    m.planned.items.forEach((i) => planned.append(itemRow(i, false)));
    card.append(planned);
  }

  const actions = element('div', undefined, 'meal-actions');
  const add = (label, cls, fn, title) => {
    const b = element('button', label, cls);
    b.type = 'button';
    if (title) b.title = title;
    b.onclick = fn;
    actions.append(b);
  };
  const has = (a) => m.actions.includes(a);
  if (editing) add('Fine', 'primary small', () => ((editSlot = null), renderDay(currentDay)));
  else {
    if (has('confirm')) add('✓ Come previsto', 'primary small', () => mutate('diary/confirm', 'POST', { date: day.date, slot: m.slot }));
    if (has('edit'))
      add(m.state === 'unknown' && !m.planned ? '+ Aggiungi' : '✎ Modifica', 'secondary small', async () => {
        editSlot = m.slot;
        if (m.state === 'unknown' && m.planned) await mutate('diary/confirm', 'POST', { date: day.date, slot: m.slot });
        else renderDay(currentDay);
      }, m.state === 'unknown' && m.planned ? 'Registra il previsto e poi modificalo' : undefined);
    if (has('alternatives')) add('⇄ Alternative', 'ghost small', () => startAlternatives(m.slot), 'Altre soluzioni ottime per questo pasto, a parità del resto della giornata');
    if (has('skip')) add('Salta', 'ghost small', () => mutate('diary/skip', 'POST', { date: day.date, slot: m.slot }));
    if (has('reset')) add('Annulla registrazione', 'ghost small', () => mutate('diary/reset', 'POST', { date: day.date, slot: m.slot }));
  }
  card.append(actions);
  const alt = mealAlternatives[day.date + '|' + m.slot];
  if (alt) card.append(alternativesPanel(alt, day, m.slot));
  return card;
}

async function startAlternatives(slot) {
  const key = homeDate + '|' + slot;
  mealAlternatives[key] = { state: 'running', seconds: 0 };
  renderDay(currentDay);
  try {
    const { job_id } = await api('plans/meal-alternatives', 'POST', { date: homeDate, slot });
    const job = await waitJob(job_id, (s) => {
      mealAlternatives[key].seconds = s;
      const label = document.querySelector('[data-alt-progress="' + key + '"]');
      if (label) label.textContent = 'Optees cerca alternative per questo pasto… ' + s + ' s';
    });
    mealAlternatives[key] = { state: 'done', set: await api('plan-sets/' + job.result.plan_set_id) };
  } catch (e) {
    mealAlternatives[key] = { state: 'error', message: e.message };
  }
  if (currentDay?.date === key.split('|')[0]) renderDay(currentDay);
}

function alternativesPanel(alt, day, slot) {
  const key = day.date + '|' + slot;
  const panel = element('div', undefined, 'alt-panel');
  const close = element('button', 'Chiudi', 'ghost small');
  close.type = 'button';
  close.onclick = () => {
    delete mealAlternatives[key];
    renderDay(currentDay);
  };
  if (alt.state === 'running') {
    const p = element('p', 'Optees cerca alternative per questo pasto… ' + (alt.seconds || 0) + ' s', 'job-text');
    p.dataset.altProgress = key;
    panel.append(element('div', undefined, 'progress-indeterminate'), p);
    return panel;
  }
  if (alt.state === 'error') {
    panel.append(element('p', alt.message, 'error'));
    const retry = element('button', 'Riprova', 'secondary small');
    retry.type = 'button';
    retry.onclick = () => startAlternatives(slot);
    const bar = element('div', undefined, 'meal-actions');
    bar.append(retry, close);
    panel.append(bar);
    return panel;
  }
  const set = alt.set;
  const warn = element('div');
  renderWarnings(warn, set.warnings);
  panel.append(warn);
  const cards = element('div', undefined, 'alt-cards');
  set.plans.forEach((p) => {
    const c = element('div', undefined, 'alt-card');
    const h = element('div', undefined, 'card-header');
    h.append(roleBadge(p.role), element('span', kcalText(p.nutrients?.kcal), 'meal-kcal'));
    c.append(h, explanationBlock(p));
    const names = (p.selections || []).filter((s) => !s.meal || s.meal === slot);
    names.forEach((s) => c.append(itemRow({ name: s.food, grams: s.grams, units: s.units }, false)));
    const choose = element('button', 'Scegli questo', 'primary small');
    choose.type = 'button';
    choose.onclick = async () => {
      try {
        const result = await api('plan-sets/' + set.run_id + '/apply', 'POST', { plan_id: p.id, scope: 'meal', date: day.date, slot });
        delete mealAlternatives[key];
        renderDay(result);
        refreshWeek();
        message('Pasto aggiornato');
      } catch (e) {
        message(e.message);
      }
    };
    c.append(choose);
    cards.append(c);
  });
  if (!set.plans.length) cards.append(element('p', 'Nessuna alternativa ammessa per questo pasto.', 'muted'));
  panel.append(cards);
  const bar = element('div', undefined, 'meal-actions');
  bar.append(close);
  panel.append(bar);
  return panel;
}

function dualMeter(label, unit, eaten, planned, spec) {
  const wrap = element('div', undefined, 'meter');
  const head = element('div', undefined, 'meter-head');
  const value = element('span', eaten == null ? '— ' : fmt0(eaten) + ' ', 'meter-value');
  value.append(element('em', '/ ' + (spec?.target != null ? fmt0(spec.target) : '—') + ' ' + unit));
  head.append(element('span', label, 'meter-label'), value);
  wrap.append(head);
  const max = Math.max(spec?.max || 0, planned || 0, eaten || 0) * 1.05 || 1;
  const track = element('div', undefined, 'meter-track');
  if (planned != null) {
    const p = element('span', undefined, 'meter-fill planned');
    p.style.width = percent(planned / max);
    track.append(p);
  }
  if (eaten != null) {
    const e = element('span', undefined, 'meter-fill');
    e.style.width = percent(eaten / max);
    track.append(e);
  }
  if (spec?.target != null) {
    const t = element('span', undefined, 'meter-target');
    t.style.left = percent(spec.target / max);
    track.append(t);
  }
  track.title = 'Consumato ' + (eaten == null ? '—' : fmt0(eaten)) + ' · previsto ' + (planned == null ? '—' : fmt0(planned)) + (spec ? ' · limiti ' + fmt0(spec.min) + '–' + fmt0(spec.max) : '') + ' ' + unit;
  wrap.append(track);
  return wrap;
}

function renderDayProgress(day) {
  const box = $('day-progress');
  const eaten = day.totals.eaten || {};
  const planned = day.totals.planned || {};
  box.replaceChildren(element('h3', 'Bilancio della giornata'));
  const legend = element('p', undefined, 'meter-legend muted');
  legend.append(element('span', 'consumato', 'lg-eaten'), element('span', 'previsto', 'lg-planned'), element('span', 'bersaglio', 'lg-target'));
  box.append(legend);
  [
    ['kcal', 'Energia', 'kcal'],
    ['protein_g', 'Proteine', 'g'],
    ['carbs_available_g', 'Carboidrati', 'g'],
    ['fat_g', 'Grassi', 'g'],
  ].forEach(([k, label, unit]) => box.append(dualMeter(label, unit, day.totals.eaten ? eaten[k] : null, day.totals.planned ? planned[k] : null, day.targets?.[k])));
  if (!day.totals.eaten) box.append(element('p', 'Ancora nessun pasto registrato oggi.', 'muted small'));
}

function renderWorkout(day) {
  const box = $('day-workout');
  box.replaceChildren(element('h3', 'Attività'));
  if (!day.workout) {
    box.append(element('p', 'Nessun allenamento pianificato.', 'muted'), element('p', 'La pianificazione della palestra arriva nel prossimo aggiornamento.', 'muted small'));
    return;
  }
  const w = day.workout;
  const row = element('div', undefined, 'workout-row');
  if (w.media?.thumbnail) {
    const img = element('img', undefined, 'workout-thumb');
    img.src = w.media.thumbnail;
    img.alt = '';
    row.append(img);
  }
  const st = workoutStatus[w.status] || [w.status, ''];
  const text = element('div');
  text.append(element('strong', w.title || w.session_id), element('p', [w.minutes && Math.round(w.minutes) + ' min', w.start_time, st[0]].filter(Boolean).join(' · '), 'muted'));
  row.append(text);
  box.append(row);
  if (w.demo) box.append(element('p', 'Bozza dimostrativa' + (w.pending_configuration?.length ? ' · ' + w.pending_configuration.length + ' informazioni da configurare' : ''), 'muted small'));
  const actions = element('div', undefined, 'actions');
  const add = (label, cls, fn) => {
    const b = element('button', label, cls);
    b.type = 'button';
    b.onclick = fn;
    actions.append(b);
  };
  if (w.status === 'chosen' || w.status === 'proposed') {
    add('Inizia', 'primary small', () => startWorkout({ planned_session_id: w.planned_session_id, session_id: w.session_id, date: day.date }));
    add('Apri', 'secondary small', () => openDayWorkout(w));
    add('Salta', 'ghost small', async () => {
      try {
        renderDay(await api('workouts/skip', 'POST', { planned_session_id: w.planned_session_id }));
        refreshWeek();
      } catch (e) {
        message(e.message);
      }
    });
  } else add(w.status === 'in_progress' ? 'Continua' : 'Vedi', w.status === 'in_progress' ? 'primary small' : 'secondary small', () => openDayWorkout(w));
  box.append(actions);
}

// ---------- Settimana ----------
function renderWeek(week) {
  const start = week.week_start;
  $('week-range').textContent = shortDate(start) + ' – ' + shortDate(addDays(start, 6));
  const today = isoDate(new Date());
  $('week-strip').replaceChildren(
    ...week.days.map((d) => {
      const b = element('button', undefined, 'week-day' + (d.date === homeDate ? ' selected' : '') + (d.date === today ? ' today' : ''));
      b.type = 'button';
      b.setAttribute('aria-label', longDate(d.date));
      b.append(element('span', parseDate(d.date).toLocaleDateString('it-IT', { weekday: 'short' }), 'wd-name'), element('span', String(parseDate(d.date).getDate()), 'wd-num'));
      const dots = element('span', undefined, 'wd-dots');
      d.meals.forEach((m) => {
        const dot = element('i', undefined, 'dot ' + (stateMeta[m.state]?.[1] || ''));
        dot.title = (mealMeta[m.slot]?.[0] || m.slot) + ': ' + (stateMeta[m.state]?.[0] || m.state);
        dots.append(dot);
      });
      if (d.workout) b.append(element('span', '🏋', 'wd-workout ' + (workoutStatus[d.workout]?.[1] || '')));
      b.append(dots, element('span', d.kcal_eaten != null ? fmt0(d.kcal_eaten) + ' kcal' : d.kcal_planned != null ? fmt0(d.kcal_planned) + ' prev.' : '—', 'wd-kcal'));
      b.onclick = () => {
        homeDate = d.date;
        editSlot = null;
        loadHome().catch((e) => message(e.message));
      };
      return b;
    }),
  );
  const box = $('week-budget');
  const bud = week.budget || {};
  box.replaceChildren();
  if (week.plan_status !== 'active') {
    box.append(element('p', 'Nessun piano attivo per questa settimana.', 'muted'));
    const cta = element('button', 'Pianifica la settimana', 'primary small');
    cta.type = 'button';
    cta.dataset.goto = 'planning';
    box.append(cta);
    return;
  }
  box.append(dualMeter('Budget calorico della settimana', 'kcal', bud.kcal_eaten, bud.kcal_planned, bud.kcal_target ? { min: 0, max: bud.kcal_target, target: bud.kcal_target } : null));
  box.append(
    element(
      'p',
      'Consumato ' + kcalText(bud.kcal_eaten) + ' · previsto ' + kcalText(bud.kcal_planned) + ' · obiettivo ' + kcalText(bud.kcal_target) + ' · giorni completi ' + (bud.complete_days ?? 0) + '/7',
      'muted small',
    ),
  );
}

// ---------- Statistiche ----------
function sparkline(points) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', '0 0 100 28');
  svg.setAttribute('class', 'sparkline');
  svg.setAttribute('aria-hidden', 'true');
  const values = points.slice(0, 30).reverse().map((p) => p[1]);
  const min = Math.min(...values),
    max = Math.max(...values),
    span = max - min || 1;
  const line = document.createElementNS(ns, 'polyline');
  line.setAttribute('points', values.map((v, i) => (i * 100) / Math.max(values.length - 1, 1) + ',' + (26 - ((v - min) / span) * 24)).join(' '));
  svg.append(line);
  return svg;
}
function statTile(label, stat, format) {
  const tile = element('div', undefined, 'stat-tile');
  tile.append(element('span', label, 'stat-label'));
  if (!stat || stat.status !== 'available') {
    tile.append(element('strong', '—', 'stat-value muted'), element('span', 'Dati insufficienti', 'stat-note'));
    if (stat?.reason) tile.title = stat.reason;
    return tile;
  }
  const [value, note] = format(stat);
  tile.append(element('strong', value, 'stat-value'), element('span', note, 'stat-note'));
  if (stat.points?.length > 1) tile.append(sparkline(stat.points));
  return tile;
}
function renderStats(target, stats) {
  target.replaceChildren(
    statTile('Peso', stats.weight, (s) => [s.value.toLocaleString('it-IT', { maximumFractionDigits: 1 }) + ' ' + (s.unit || 'kg'), s.trend_7d != null ? (s.trend_7d > 0 ? '+' : '') + s.trend_7d.toLocaleString('it-IT', { maximumFractionDigits: 1 }) + ' kg in 7 giorni' : 'ultima misura ' + shortDate(s.date)]),
    statTile('Aderenza della settimana', stats.adherence_week, (s) => [Math.round(s.diet * 100) + '%', 'dieta · palestra ' + Math.round((s.training || 0) * 100) + '%']),
    statTile('Kcal medie', stats.kcal_average, (s) => [fmt0(s.eaten_avg), 'su ' + fmt0(s.target) + ' · ' + s.days + ' giorni']),
    statTile('Allenamenti', stats.workouts, (s) => [s.done + '/' + s.planned, 'questa settimana']),
  );
}

// ---------- Piano: settimana ----------
let planningReady = false;
function showPlanTab(tab) {
  document.querySelectorAll('[data-plan-tab]').forEach((b) => {
    const on = b.dataset.planTab === tab;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', String(on));
  });
  document.querySelectorAll('[data-plan-panel]').forEach((p) => (p.hidden = p.dataset.planPanel !== tab));
}
document.querySelectorAll('[data-plan-tab]').forEach((b) => (b.onclick = () => showPlanTab(b.dataset.planTab)));
function preparePlanning() {
  if (!profile) return;
  fillModes('week-mode');
  const thisMonday = mondayOf(isoDate(new Date()));
  const select = $('week-start');
  if (!planningReady) {
    select.replaceChildren(
      ...[
        [thisMonday, 'Questa settimana · dal ' + shortDate(thisMonday)],
        [addDays(thisMonday, 7), 'Prossima settimana · dal ' + shortDate(addDays(thisMonday, 7))],
      ].map(([value, label]) => {
        const o = element('option', label);
        o.value = value;
        return o;
      }),
    );
    planningReady = true;
  }
}

function weekPlanCard(p, set) {
  const card = element('article', undefined, 'card week-plan');
  const header = element('div', undefined, 'card-header');
  header.append(roleBadge(p.role), element('span', p.status === 'optimal' ? 'Ottimo certificato' : 'Verificata', 'tag'));
  card.append(header, explanationBlock(p));
  const days = p.days || [];
  const avg = days.length ? days.reduce((a, d) => a + (d.nutrients?.kcal || 0), 0) / days.length : null;
  const hero = element('div', undefined, 'plan-hero');
  const k = element('div', fmt0(avg), 'hero-kcal');
  k.append(element('small', 'kcal/giorno'));
  const left = element('div');
  left.append(k, element('div', 'Media dei 7 giorni', 'hero-caption'));
  hero.append(left);
  card.append(hero);
  const list = element('div', undefined, 'week-plan-days');
  days.forEach((d) => {
    const row = element('div', undefined, 'wp-day');
    const main = ['lunch', 'dinner']
      .map((meal) => {
        const foods = (d.selections || []).filter((s) => s.meal === meal).map((s) => String(s.food).split(',')[0]);
        return foods.length ? mealMeta[meal][0] + ': ' + foods.slice(0, 3).join(', ') : null;
      })
      .filter(Boolean)
      .join(' · ');
    row.append(element('strong', parseDate(d.date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' })), element('span', main || '—', 'wp-foods'), element('span', kcalText(d.nutrients?.kcal), 'wp-kcal'));
    list.append(row);
  });
  card.append(list);
  const apply = element('button', 'Usa questa settimana', 'primary card-cta');
  apply.type = 'button';
  apply.onclick = async () => {
    apply.disabled = true;
    try {
      const r = await api('plan-sets/' + set.run_id + '/apply', 'POST', { plan_id: p.id, scope: 'week' });
      const applied = r.applied_slots?.length || 0,
        skipped = r.skipped_slots?.length || 0;
      message('Settimana pianificata: ' + applied + ' pasti' + (skipped ? ', ' + skipped + ' già registrati lasciati invariati' : ''));
      const today = isoDate(new Date());
      homeDate = mondayOf(today) === set.week_start ? today : set.week_start;
      document.querySelector('.nav[data-page="home"]').click();
    } catch (e) {
      message(e.message);
      apply.disabled = false;
    }
  };
  card.append(apply);
  return card;
}

$('week-generate').onclick = async () => {
  const button = $('week-generate');
  const box = $('week-job');
  button.disabled = true;
  $('week-plans').replaceChildren();
  $('week-warnings').replaceChildren();
  box.hidden = false;
  const text = element('p', 'Optees sta componendo la settimana…', 'job-text');
  box.replaceChildren(element('div', undefined, 'progress-indeterminate'), text);
  try {
    const { job_id } = await api('plans/week', 'POST', { week_start: $('week-start').value, mode: $('week-mode').value });
    const job = await waitJob(job_id, (s) => (text.textContent = 'Optees sta componendo la settimana… ' + s + ' s'));
    const set = await api('plan-sets/' + job.result.plan_set_id);
    set.week_start = set.week_start || $('week-start').value;
    renderWarnings($('week-warnings'), set.warnings);
    $('week-plans').replaceChildren(...set.plans.map((p) => weekPlanCard(p, set)));
    if (set.plans.length === 1) $('week-warnings').append(element('p', 'Con questi vincoli Optees ha trovato una sola proposta valida per la settimana.', 'notice'));
  } catch (e) {
    $('week-warnings').replaceChildren(element('p', e.message, 'error'));
  } finally {
    box.hidden = true;
    button.disabled = false;
  }
};

// ---------- Progressi ----------
const measureUnits = { weight: 'kg', waist: 'cm', body_fat: '%', height: 'cm' };
const measureNames = { weight: 'Peso', waist: 'Vita', body_fat: 'Grasso corporeo', height: 'Altezza' };
async function loadProgress() {
  if (!$('measure-date').value) $('measure-date').value = isoDate(new Date());
  const [stats, measures] = await Promise.all([api('stats/summary'), api('measurements')]);
  renderStats($('progress-tiles'), stats);
  const list = $('measure-list');
  list.replaceChildren();
  if (!measures.length) return list.append(element('p', 'Nessuna misura registrata.', 'muted'));
  list.append(
    healthTable(
      ['Data', 'Misura', 'Valore', 'Fonte'],
      measures.slice(0, 12).map((m) => [shortDate(m.date), measureNames[m.kind] || m.kind, Number(m.value).toLocaleString('it-IT', { maximumFractionDigits: 1 }) + ' ' + (m.unit || ''), m.source === 'manual' ? 'inserita da te' : m.source === 'apple_health' ? 'Apple Salute' : m.source]),
    ),
  );
}
$('measure-form').onsubmit = async (e) => {
  e.preventDefault();
  const kind = $('measure-kind').value;
  try {
    await api('measurements', 'POST', { date: $('measure-date').value, kind, value: Number($('measure-value').value), unit: measureUnits[kind] });
    $('measure-value').value = '';
    message('Misura salvata');
    await loadProgress();
  } catch (err) {
    message(err.message);
  }
};

// ---------- Navigazione ----------
$('day-prev').onclick = () => ((homeDate = addDays(homeDate, -1)), (editSlot = null), loadHome().catch((e) => message(e.message)));
$('day-next').onclick = () => ((homeDate = addDays(homeDate, 1)), (editSlot = null), loadHome().catch((e) => message(e.message)));
$('day-today').onclick = () => ((homeDate = isoDate(new Date())), (editSlot = null), loadHome().catch((e) => message(e.message)));
document.addEventListener('click', (e) => {
  const target = e.target.closest('[data-goto]');
  if (!target) return;
  document.querySelector('.nav[data-page="' + target.dataset.goto + '"]').click();
  if (target.dataset.goto === 'planning') showPlanTab('week');
});

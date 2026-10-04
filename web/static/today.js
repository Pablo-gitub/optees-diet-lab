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
  const workouts = day.workouts || (day.workout ? [day.workout] : []);
  if (!workouts.length) {
    box.append(element('p', day.day_type === 'rest' ? 'Giornata di riposo.' : 'Nessun allenamento pianificato.', 'muted'));
    const cta = element('button', 'Vai all’allenamento', 'secondary small');
    cta.type = 'button';
    cta.dataset.goto = 'workout';
    box.append(cta);
    return;
  }
  workouts.forEach((w) => box.append(dayWorkoutItem(w, day)));
}
function dayWorkoutItem(w, day) {
  const item = element('div', undefined, 'day-workout-item');
  const row = element('div', undefined, 'workout-row');
  if (w.media?.thumbnail) {
    const img = element('img', undefined, 'workout-thumb');
    img.src = w.media.thumbnail;
    img.alt = '';
    row.append(img);
  }
  const st = workoutStatus[w.status] || [w.status, ''];
  const text = element('div');
  text.append(element('strong', w.title || w.session_id), element('p', [w.minutes && Math.round(w.minutes) + ' min', w.start_time, st[0], w.planned_session_id ? null : 'fuori piano'].filter(Boolean).join(' · '), 'muted'));
  row.append(text);
  item.append(row);
  if (w.demo) item.append(element('p', 'Bozza dimostrativa' + (w.pending_configuration?.length ? ' · ' + w.pending_configuration.length + ' informazioni da configurare' : ''), 'muted small'));
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
  item.append(actions);
  return item;
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
  if (stat && stat.status !== 'available' && stat.value != null && stat.unit) {
    tile.append(element('strong', stat.value.toLocaleString('it-IT', { maximumFractionDigits: 1 }) + ' ' + stat.unit, 'stat-value'), element('span', stat.reason || 'Dato non recente', 'stat-note'));
    return tile;
  }
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
    statTile('Aderenza della settimana', stats.adherence_week, (s) => [s.diet != null ? Math.round(s.diet * 100) + '%' : '—', 'dieta · palestra ' + (s.training != null ? Math.round(s.training * 100) + '%' : '—')]),
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
    select.addEventListener('change', () => availabilityInputs($('joint-availability'), select.value));
    $('week-joint').checked = !!jointSaved().enabled;
    planningReady = true;
  }
  // Balance and day-type targets live in the profile (used by the Monday recalibration too).
  setBalance(profile.energy_balance_target_kcal !== undefined ? profile.energy_balance_target_kcal : jointSaved().balance);
  renderJointTargets();
  availabilityInputs($('joint-availability'), select.value);
  syncJointMode();
}

// ---------- Piano: settimana congiunta dieta + palestra (passo 4.3) ----------
const nutrientRows = [
  ['kcal_100g', 'Calorie', 'kcal', 50],
  ['protein_g_100g', 'Proteine', 'g', 5],
  ['carbs_available_g_100g', 'Carboidrati', 'g', 5],
  ['fat_g_100g', 'Grassi', 'g', 5],
];
const dayTypeNames = { rest: 'Riposo', training: 'Allenamento' };
const scenarioNames = { low: 'Se consumi meno del solito', central: 'Se consumi come al solito', high: 'Se consumi più del solito' };
const sessionTitles = {};
function jointSaved() {
  try {
    return JSON.parse(localStorage.getItem('diet-joint-settings') || '{}') || {};
  } catch {
    return {};
  }
}
function jointSave(patch) {
  try {
    localStorage.setItem('diet-joint-settings', JSON.stringify({ ...jointSaved(), ...patch }));
  } catch {}
}
function setBalance(value) {
  const select = $('joint-balance');
  const known = [...select.options].some((o) => o.value !== 'custom' && o.value === (value == null ? '' : String(value)));
  select.value = value == null ? '' : known ? String(value) : 'custom';
  if (select.value === 'custom') $('joint-balance-custom').value = value;
  $('joint-balance-custom-wrap').hidden = select.value !== 'custom';
}
function readBalance() {
  const v = $('joint-balance').value;
  if (v === '') return null;
  const n = Number(v === 'custom' ? $('joint-balance-custom').value : v);
  if ($('joint-balance-custom').value === '' && v === 'custom') throw Error('Indica il bilancio calorico in kcal al giorno');
  if (!Number.isFinite(n) || n < -1000 || n > 1000) throw Error('Bilancio calorico fra −1000 e +1000 kcal al giorno');
  return n;
}
$('joint-balance').onchange = () => {
  $('joint-balance-custom-wrap').hidden = $('joint-balance').value !== 'custom';
  if ($('joint-balance').value === 'custom') $('joint-balance-custom').focus();
};
$('week-joint').onchange = () => {
  jointSave({ enabled: $('week-joint').checked });
  syncJointMode();
};
$('joint-ranges').onchange = () => $('joint-targets').classList.toggle('show-ranges', $('joint-ranges').checked);
function syncJointMode() {
  const on = $('week-joint').checked;
  $('joint-options').hidden = !on;
  $('week-mode-label').hidden = on;
  $('week-hint').textContent = on
    ? 'Optees combina più schede di allenamento con la dieta di 7 giorni e verifica ogni combinazione. Pasti e allenamenti già registrati restano bloccati. Obiettivi e bilancio scelti vengono salvati nel profilo. Il calcolo può richiedere un paio di minuti.'
    : 'Optees propone 7 giorni completi rispettando la dieta, le porzioni e le ripetizioni. I pasti già registrati restano bloccati.';
  $('joint-modes-note').textContent = profile?.personal_diets
    ? 'Nei giorni di riposo vale la dieta sedentaria, in quelli di allenamento la dieta palestra. Qui scegli gli obiettivi dell’intera giornata, colazione e spuntini compresi.'
    : 'Obiettivi dell’intera giornata, colazione e spuntini compresi. Nei giorni di allenamento puoi alzare calorie e carboidrati.';
}
function renderJointTargets() {
  const base = profile.daily_meals?.targets || {};
  // Older browsers kept targets locally: use them only until the profile has its own.
  const saved = profile.day_type_targets || jointSaved().targets || {};
  const grid = $('joint-targets');
  grid.classList.toggle('show-ranges', $('joint-ranges').checked);
  const cells = [element('span'), element('strong', 'Riposo', 'tg-head'), element('strong', '🏋 Allenamento', 'tg-head')];
  nutrientRows.forEach(([key, label, unit, step]) => {
    cells.push(element('span', label + ' (' + unit + ')', 'tg-label'));
    ['rest', 'training'].forEach((type) => {
      const spec = saved[type]?.[key] || base[key] || {};
      const cell = element('div', undefined, 'tg-cell');
      ['min', 'target', 'max'].forEach((part) => {
        const input = element('input');
        input.type = 'number';
        input.min = 0;
        input.max = 10000;
        input.step = step;
        input.value = spec[part] ?? '';
        input.dataset.type = type;
        input.dataset.key = key;
        input.dataset.part = part;
        input.className = 'tg-' + part;
        input.setAttribute('aria-label', label + ' ' + dayTypeNames[type].toLowerCase() + ' ' + (part === 'target' ? 'obiettivo' : part === 'min' ? 'minimo' : 'massimo'));
        cell.append(input);
      });
      cells.push(cell);
    });
  });
  grid.replaceChildren(...cells);
}
function readJointTargets() {
  const out = { rest: {}, training: {} };
  $('joint-targets')
    .querySelectorAll('input')
    .forEach((i) => {
      out[i.dataset.type][i.dataset.key] = out[i.dataset.type][i.dataset.key] || {};
      out[i.dataset.type][i.dataset.key][i.dataset.part] = Number(i.value);
    });
  for (const type of ['rest', 'training'])
    for (const [key, label] of nutrientRows) {
      const t = out[type][key];
      if (![t.min, t.target, t.max].every(Number.isFinite) || !(t.min <= t.target && t.target <= t.max) || t.target <= 0)
        throw Error(label + ' (' + dayTypeNames[type].toLowerCase() + '): l’obiettivo deve stare fra minimo e massimo. Attiva «Mostra intervalli» per modificarli.');
    }
  return out;
}

function sessionName(id) {
  return sessionTitles[id] || id;
}
function weekdayShort(date) {
  return parseDate(date).toLocaleDateString('it-IT', { weekday: 'short' });
}
// Differenze rispetto al piano migliore: allenamenti prima, alimenti raggruppati.
function sessionDiffChips(diff) {
  const box = element('div', undefined, 'diff-chips');
  if (!diff) return box;
  (diff.sessions_added || []).forEach((x) => box.append(element('span', '+ ' + sessionName(x.session_id) + ' ' + weekdayShort(x.date), 'chip diff-add')));
  (diff.sessions_removed || []).forEach((x) => box.append(element('span', '− ' + sessionName(x.session_id) + ' ' + weekdayShort(x.date), 'chip diff-remove')));
  (diff.sessions_moved || []).forEach((x) => box.append(element('span', sessionName(x.session_id) + ' ' + weekdayShort(x.from_date) + ' → ' + weekdayShort(x.to_date), 'chip diff-change')));
  return box;
}
function robustReason(reason, set) {
  if (/Bilancio/i.test(reason || '') && set.energy_balance_target_kcal == null)
    return 'Indica il bilancio calorico che vuoi (anche «Mantenimento») per sapere quanto ogni settimana regge se consumi più o meno del solito.';
  return (
    'Per valutarla servono dati Apple Salute recenti (almeno 7 giornate complete nelle ultime 4 settimane) e, per ogni attività pianificata, almeno 3 allenamenti dello stesso tipo registrati negli ultimi 90 giorni. Puoi importare l’export in Progressi.'
  );
}
function robustnessSummary(set) {
  const box = $('week-robustness');
  box.replaceChildren();
  const r = set.robust_selection;
  if (!r) return;
  if (r.status === 'unavailable' || !r.comparable_candidates) {
    const n = element('div', undefined, 'notice robust-off');
    const t = element('span');
    t.append(element('strong', 'Robustezza non valutata. '), document.createTextNode(robustReason(r.reason, set)));
    n.append(t);
    box.append(n);
    return;
  }
  const n = element('div', undefined, 'notice robust-on');
  const t = element('span');
  n.append(t);
  t.append(
    element('strong', 'Robustezza valutata. '),
    document.createTextNode(
      'Ogni settimana è stata messa alla prova con tre scenari di consumo ricavati da Apple Salute. ' +
        'Il confronto riguarda le ' + r.comparable_candidates + ' combinazioni calcolate, non tutte quelle possibili.' +
        (r.status === 'local_finite_pool' ? ' Classifica calcolata localmente: il selettore di Optees non era disponibile.' : ''),
    ),
  );
  box.append(n);
}
function robustnessBlock(p, set, scale) {
  const r = p.robustness || {};
  const box = element('div', undefined, 'robust-box');
  if (r.status !== 'available') {
    if (set.robust_selection?.comparable_candidates) box.append(element('p', 'Robustezza non valutabile per questa combinazione: mancano gli scenari di consumo per alcuni giorni.', 'muted small'));
    return box.childElementCount ? box : null;
  }
  const balance = r.energy_balance_target_kcal;
  box.append(element('h4', 'Se il tuo consumo cambia'));
  const rows = element('div', undefined, 'scenario-rows');
  ['low', 'central', 'high'].forEach((s) => {
    const loss = r.scenarios[s];
    const row = element('div', undefined, 'scenario-row' + (loss === r.max_loss_kcal ? ' worst' : ''));
    const bar = element('span', undefined, 'scenario-bar');
    const fill = element('i');
    fill.style.width = Math.max(3, Math.min(100, (loss / scale) * 100)) + '%';
    bar.append(fill);
    row.append(element('span', scenarioNames[s], 'scenario-name'), bar, element('span', '± ' + fmt0(loss) + ' kcal', 'scenario-value'));
    rows.append(row);
  });
  box.append(rows);
  const goal = balance === 0 ? 'dal pareggio fra calorie mangiate e consumate' : 'dal ' + (balance < 0 ? 'deficit' : 'surplus') + ' di ' + fmt0(Math.abs(balance)) + ' kcal che hai scelto';
  box.append(element('p', 'Nel caso peggiore ti allontani in media di ' + fmt0(r.max_loss_kcal) + ' kcal al giorno ' + goal + '.', 'small'));
  if (r.max_regret_kcal != null)
    box.append(
      element(
        'p',
        p.role === 'robust'
          ? 'È la combinazione più prudente: in qualunque scenario resta al massimo ' + fmt0(r.max_regret_kcal) + ' kcal al giorno dalla scelta migliore per quello scenario.'
          : 'Rispetto alla scelta migliore per ciascuno scenario perde al massimo ' + fmt0(r.max_regret_kcal) + ' kcal al giorno.',
        'muted small',
      ),
    );
  const days = p.days || [];
  const low = days.reduce((a, d) => a + (d.energy_scenarios?.consumption_kcal?.low || 0), 0) / (days.length || 1);
  const high = days.reduce((a, d) => a + (d.energy_scenarios?.consumption_kcal?.high || 0), 0) / (days.length || 1);
  if (low && high) box.append(element('p', 'Consumo stimato da Apple Salute: ' + fmt0(low) + '–' + fmt0(high) + ' kcal al giorno, allenamenti contati una sola volta.', 'muted small'));
  return box;
}
function jointDayRow(d) {
  const row = element('div', undefined, 'wp-day joint-day' + (d.day_type === 'training' ? ' training' : ''));
  const sessions = (d.workout_sessions || []).map((s) => (s.session?.title || sessionName(s.session_id)) + ' · ' + fmt0(s.minutes) + ' min');
  const meals = ['lunch', 'dinner']
    .map((meal) => {
      const foods = (d.selections || []).filter((s) => s.meal === meal).map((s) => String(s.food).split(',')[0]);
      return foods.length ? mealMeta[meal][0] + ': ' + foods.slice(0, 3).join(', ') : null;
    })
    .filter(Boolean)
    .join(' · ');
  const what = element('div', undefined, 'wp-foods');
  if (sessions.length) what.append(element('span', '🏋 ' + sessions.join(' + '), 'wp-session'));
  what.append(element('span', meals || '—'));
  const target = d.targets?.kcal_100g?.target;
  row.append(
    element('strong', parseDate(d.date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' })),
    element('span', dayTypeNames[d.day_type] || '—', 'day-type-pill ' + (d.day_type || '')),
    what,
    element('span', fmt0(d.nutrients?.kcal) + (target ? ' / ' + fmt0(target) : '') + ' kcal', 'wp-kcal'),
  );
  return row;
}
function weekPlanCard(p, set, scale) {
  const joint = set.kind === 'joint';
  const card = element('article', undefined, 'card week-plan' + (joint ? ' joint-plan' : ''));
  const header = element('div', undefined, 'card-header');
  const tags = element('span', undefined, 'card-tags');
  tags.append(element('span', p.status === 'optimal' ? 'Ottimo certificato' : 'Verificata', 'tag'));
  if (joint && p.demo) tags.append(element('span', 'Allenamento dimostrativo', 'tag tag-warn'));
  header.append(roleBadge(p.role), tags);
  card.append(header);
  if (joint) {
    const e = p.explanation || {};
    const ex = element('div', undefined, 'explanation');
    if (e.headline) ex.append(element('p', e.headline, 'headline'));
    const chips = sessionDiffChips(p.diff);
    if (chips.childElementCount) ex.append(chips);
    const foodChanges = (p.diff?.days || []).reduce((a, d) => a + (d.added?.length || 0) + (d.removed?.length || 0) + (d.changed?.length || 0), 0);
    if (foodChanges) {
      const more = element('details', undefined, 'diff-more');
      more.append(element('summary', foodChanges + (foodChanges === 1 ? ' differenza' : ' differenze') + ' negli alimenti rispetto a «Il migliore»'), diffChips(p.diff));
      ex.append(more);
    }
    if (p.status === 'partial') ex.append(element('p', 'Soluzione verificata; ottimo non certificato entro il tempo di calcolo.', 'muted small'));
    card.append(ex);
  } else card.append(explanationBlock(p));
  const days = p.days || [];
  const avg = days.length ? days.reduce((a, d) => a + (d.nutrients?.kcal || 0), 0) / days.length : null;
  const hero = element('div', undefined, 'plan-hero');
  const k = element('div', fmt0(avg), 'hero-kcal');
  k.append(element('small', 'kcal/giorno'));
  const left = element('div');
  left.append(k, element('div', 'Media dei 7 giorni', 'hero-caption'));
  hero.append(left);
  if (joint) {
    const sessions = p.workout_sessions || [];
    const stats = element('div', undefined, 'hero-stats');
    const stat = (value, label, title) => {
      const s = element('div', undefined, 'hero-stat');
      s.append(element('strong', value), element('span', label));
      if (title) s.title = title;
      stats.append(s);
    };
    stat(fmt0(p.objectives?.training_minutes) + ' min', sessions.length + (sessions.length === 1 ? ' allenamento' : ' allenamenti'));
    if (p.objectives?.training_fit != null) stat(Math.round(p.objectives.training_fit * 100) + '%', 'obiettivi di allenamento', 'Stima della copertura dei gruppi muscolari e dei minuti di cardio impostati: non misura l’efficacia.');
    hero.append(stats);
  }
  card.append(hero);
  if (joint) {
    const robust = robustnessBlock(p, set, scale);
    if (robust) card.append(robust);
  }
  const list = element('div', undefined, 'week-plan-days');
  days.forEach((d) => {
    if (joint) return list.append(jointDayRow(d));
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
  const apply = element('button', joint ? 'Usa dieta e allenamenti' : 'Usa questa settimana', 'primary card-cta');
  apply.type = 'button';
  apply.onclick = async () => {
    apply.disabled = true;
    try {
      const r = await api('plan-sets/' + set.run_id + '/apply', 'POST', { plan_id: p.id, scope: 'week' });
      const applied = r.applied_slots?.length || 0,
        skipped = r.skipped_slots?.length || 0;
      const sessions = (r.applied_slots || []).filter((x) => x.session_id).length;
      message(
        joint
          ? 'Settimana pianificata: ' + (applied - sessions) + ' pasti e ' + sessions + (sessions === 1 ? ' allenamento' : ' allenamenti') + (skipped ? ' · ' + skipped + ' già registrati lasciati invariati' : '')
          : 'Settimana pianificata: ' + applied + ' pasti' + (skipped ? ', ' + skipped + ' già registrati lasciati invariati' : ''),
      );
      const today = isoDate(new Date());
      homeDate = mondayOf(today) === set.week_start ? today : set.week_start;
      document.querySelector('.nav[data-page="home"]').click();
    } catch (e) {
      message(e.status === 409 ? 'Qualcosa è cambiato dopo il calcolo (pasti registrati o configurazione): genera di nuovo la settimana.' : e.message);
      apply.disabled = false;
    }
  };
  card.append(apply);
  return card;
}

// PUT /api/profile replaces the whole profile: resend every field with the patch.
async function saveProfilePatch(patch) {
  const p = profile;
  await api('profile', 'PUT', {
    display_name: p.display_name,
    mode: p.mode,
    preference_note: p.preference_note,
    targets: p.targets,
    meal_targets: p.meal_targets,
    excluded_crea_ids: p.excluded_crea_ids,
    targets_demo: p.targets_demo,
    daily_meals: p.daily_meals,
    preferred_cuisines: p.preferred_cuisines,
    ...patch,
  });
  Object.assign(profile, patch);
}
async function jointRequest() {
  const day_targets = readJointTargets();
  const energy_balance_target_kcal = readBalance();
  if (JSON.stringify(day_targets) !== JSON.stringify(profile.day_type_targets) || energy_balance_target_kcal !== profile.energy_balance_target_kcal)
    await saveProfilePatch({ day_type_targets: day_targets, energy_balance_target_kcal });
  jointSave({ targets: undefined, balance: undefined });
  return {
    week_start: $('week-start').value,
    day_targets,
    energy_balance_target_kcal,
    workout: { ...readAvailability($('joint-availability')), demo: true },
  };
}
$('week-generate').onclick = async () => {
  const button = $('week-generate');
  const box = $('week-job');
  const joint = $('week-joint').checked;
  let body;
  try {
    body = joint ? await jointRequest() : { week_start: $('week-start').value, mode: $('week-mode').value };
  } catch (e) {
    return message(e.message);
  }
  button.disabled = true;
  $('week-plans').replaceChildren();
  $('week-warnings').replaceChildren();
  $('week-robustness').replaceChildren();
  box.hidden = false;
  const label = joint ? 'Optees sta combinando dieta e allenamento…' : 'Optees sta componendo la settimana…';
  const text = element('p', label, 'job-text');
  box.replaceChildren(element('div', undefined, 'progress-indeterminate'), text);
  try {
    const { job_id } = await api(joint ? 'plans/joint-week' : 'plans/week', 'POST', body);
    const job = await waitJob(job_id, (s) => (text.textContent = label + ' ' + s + ' s'));
    const set = await api('plan-sets/' + job.result.plan_set_id);
    set.week_start = set.week_start || $('week-start').value;
    if (joint) {
      set.energy_balance_target_kcal = body.energy_balance_target_kcal;
      set.plans.forEach((p) => (p.workout_sessions || []).forEach((s) => (sessionTitles[s.session_id] = s.session?.title || s.session?.name || s.session_id)));
    }
    // Robustness gets its own plain-language summary instead of the raw backend warnings.
    const robustAvailable = set.robust_selection && set.robust_selection.status !== 'unavailable';
    renderWarnings(
      $('week-warnings'),
      (set.warnings || [])
        .filter((w) => w.code !== 'robustness_unavailable' && (w.code !== 'robust_role_omitted' || robustAvailable))
        .map((w) => (w.code === 'robust_role_omitted' ? { message: 'Nessuna combinazione abbastanza diversa da proporre come «Più robusto»: la più stabile coincide con una di quelle mostrate.' } : w)),
    );
    if (joint) robustnessSummary(set);
    const scale = Math.max(1, ...set.plans.map((p) => p.robustness?.max_loss_kcal || 0));
    $('week-plans').replaceChildren(...set.plans.map((p) => weekPlanCard(p, set, scale)));
    if (set.plans.length === 1) $('week-warnings').append(element('p', 'Con questi vincoli Optees ha trovato una sola proposta valida per la settimana.', 'notice'));
    if (!set.plans.length) $('week-warnings').append(element('p', joint ? 'Nessuna combinazione rispetta tempi, obiettivi e vincoli: aumenta i minuti disponibili o allarga gli intervalli.' : 'Nessuna settimana rispetta i vincoli.', 'error'));
  } catch (e) {
    const box = $('week-warnings');
    box.replaceChildren(element('p', e.message, 'error'));
    if (/colazione e spuntini/i.test(e.message)) {
      const go = element('button', 'Apri il profilo', 'secondary small');
      go.type = 'button';
      go.dataset.goto = 'profile';
      box.append(go);
    }
  } finally {
    box.hidden = true;
    button.disabled = false;
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

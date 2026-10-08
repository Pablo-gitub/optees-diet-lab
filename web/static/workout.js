// Allenamento: settimana, sessione con registro delle serie, configurazione personale (passi 3.2/3.3).
const exerciseNames = {
  'push-up': 'Piegamenti (push-up)',
  'bodyweight-squat': 'Squat a corpo libero',
  'dumbbell-deadlift': 'Stacco con manubri',
  'dumbbell-floor-press': 'Distensioni a terra con manubri',
  plank: 'Plank',
  'inverted-row': 'Trazioni australiane',
  'stationary-bike': 'Cyclette',
  'rowing-machine': 'Vogatore',
  'incline-treadmill-walk': 'Camminata in salita sul tapis roulant',
  'elliptical-trainer': 'Ellittica',
};
const variantNames = { standard: 'Standard', chair_assisted: 'Assistito con sedia', knees: 'Sulle ginocchia', hands_elevated: 'Mani rialzate', feet_on_floor: 'Piedi a terra' };
const levelNames = { beginner: 'Principiante', intermediate: 'Intermedio', advanced: 'Avanzato' };
const equipmentNames = {
  manubri: 'Manubri',
  bilanciere: 'Bilanciere',
  bilanciere_curvo: 'Bilanciere curvo',
  panca: 'Panca piana',
  panca_inclinata: 'Panca inclinata',
  vogatore_acqua: 'Vogatore ad acqua',
  cyclette: 'Cyclette',
  tapis_roulant_inclinabile: 'Tapis roulant inclinabile',
  ellittica: 'Ellittica',
  aqua_bag: 'Aqua bag',
  aqua_tank: 'Aqua tank',
  crunch_machine: 'Crunch machine',
  ab_wheel: 'Ab wheel',
  parallele: 'Parallele',
  barra_trazioni: 'Barra per trazioni',
  sedia: 'Sedia stabile',
};
const workoutStatus = {
  proposed: ['Proposta', ''],
  chosen: ['Da fare', ''],
  in_progress: ['In corso', 'state-mod'],
  done: ['Fatto', 'state-ok'],
  skipped: ['Saltato', 'state-skip'],
};
const timelineNames = { warmup: 'Riscaldamento', setup: 'Preparazione', work: 'Lavoro', rest: 'Recupero', transition: 'Cambio', round_rest: 'Pausa fra giri', recovery: 'Recupero attivo', cooldown: 'Defaticamento' };
const exName = (e) => exerciseNames[e.exercise_id || e.source_id] || e.name;
const minutesText = (m) => (m == null ? '—' : Math.round(m) + ' min');
const clock = (s) => Math.floor(s / 60) + ':' + String(Math.round(s % 60)).padStart(2, '0');
let wkConfig = null;
let wkCurrent = null;
let wkPrepared = false;

function showWorkoutTab(tab) {
  document.querySelectorAll('[data-wk-tab]').forEach((b) => {
    const on = b.dataset.wkTab === tab;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', String(on));
  });
  document.querySelectorAll('[data-wk-panel]').forEach((p) => (p.hidden = p.dataset.wkPanel !== tab));
  if (tab === 'config') renderWorkoutConfig();
  if (tab === 'week' && wkPrepared) loadWorkoutWeek().catch((e) => message(e.message));
}
document.querySelectorAll('[data-wk-tab]').forEach((b) => (b.onclick = () => showWorkoutTab(b.dataset.wkTab)));

async function loadWorkout() {
  prepareWorkout();
  await Promise.all([loadWorkoutConfig(), loadWorkoutWeek(), loadWorkoutCatalog()]);
}

function prepareWorkout() {
  if (wkPrepared) return;
  wkPrepared = true;
  const thisMonday = mondayOf(isoDate(new Date()));
  $('wk-week-start').replaceChildren(
    ...[
      [thisMonday, 'Questa settimana · dal ' + shortDate(thisMonday)],
      [addDays(thisMonday, 7), 'Prossima settimana · dal ' + shortDate(addDays(thisMonday, 7))],
    ].map(([value, label]) => {
      const o = element('option', label);
      o.value = value;
      return o;
    }),
  );
  $('wk-week-start').onchange = renderAvailability;
  renderAvailability();
}

function renderAvailability() {
  availabilityInputs($('wk-availability'), $('wk-week-start').value);
}
// Minuti disponibili per giorno, condivisi fra Allenamento e Piano (preferenza del browser).
function availabilityInputs(box, start) {
  const defaults = [40, 0, 40, 0, 40, 30, 0];
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem('diet-workout-availability:'+window.planningOwner) || 'null');
  } catch {}
  box.replaceChildren(
    ...defaults.map((d, i) => {
      const date = addDays(start, i);
      const label = element('label', parseDate(date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' }));
      const input = element('input');
      input.type = 'number';
      input.min = 0;
      input.max = 240;
      input.step = 5;
      input.value = saved?.[i] ?? d;
      input.dataset.date = date;
      label.append(input);
      return label;
    }),
  );
}
function readAvailability(box) {
  const inputs = [...box.querySelectorAll('input')];
  for(const input of inputs)if(input.value===''||!input.checkValidity())throw Error('Minuti disponibili: indica un valore da 0 a 240, a passi di 5, per ogni giorno.');
  try {
    localStorage.setItem('diet-workout-availability:'+window.planningOwner, JSON.stringify(inputs.map((i) => Number(i.value) || 0)));
  } catch {}
  const days = Object.fromEntries(inputs.map((i) => [i.dataset.date, Math.max(0, Math.round(Number(i.value) || 0))]));
  return { days, excluded_days: Object.keys(days).filter((d) => !days[d]) };
}

async function loadWorkoutConfig() {
  wkConfig = await api('workouts/config');
  const missing = wkConfig.missing_fields.filter((m) => !m.optional).length;
  $('wk-config-count').hidden = !missing;
  $('wk-config-count').textContent = missing;
  const banner = $('wk-config-banner');
  banner.replaceChildren();
  if (missing) {
    const n = element('div', undefined, 'notice warn');
    const text = element('span', 'Nella configurazione salvata mancano ' + missing + ' informazioni (livello, attrezzi, carichi, varianti). Compila e salva per aggiornare il conteggio; finché mancano le sessioni restano bozze dimostrative. ');
    const go = element('button', 'Completa la configurazione', 'secondary small');
    go.type = 'button';
    go.onclick = () => showWorkoutTab('config');
    text.append(go);
    n.append(text);
    banner.append(n);
  }
}

async function loadWorkoutWeek() {
  const start = mondayOf(isoDate(new Date()));
  $('wk-range').textContent = shortDate(start) + ' – ' + shortDate(addDays(start, 6));
  const days = await Promise.all([0, 1, 2, 3, 4, 5, 6].map((i) => api('day?date=' + addDays(start, i))));
  const rows = days.flatMap((d) => (d.workouts || (d.workout ? [d.workout] : [])).map((w) => [d, w]));
  const list = $('wk-sessions');
  list.replaceChildren();
  if (!rows.length) {
    list.append(element('p', 'Nessuna sessione pianificata questa settimana: generala qui sotto o scegli una sessione dal catalogo.', 'empty-inline muted'));
    return;
  }
  rows.forEach(([d, w]) => list.append(sessionRow(d, w)));
}

function sessionRow(day, w) {
  const st = workoutStatus[w.status] || [w.status, ''];
  const row = element('article', undefined, 'session-row ' + st[1]);
  if (w.media?.thumbnail) {
    const img = element('img', undefined, 'workout-thumb');
    img.src = w.media.thumbnail;
    img.alt = '';
    row.append(img);
  }
  const text = element('div', undefined, 'session-text');
  const title = element('strong', w.title || w.session_id);
  text.append(title, element('span', parseDate(day.date).toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric' }).replace(/^./, (c) => c.toUpperCase()) + ' · ' + minutesText(w.minutes) + (w.start_time ? ' · ' + w.start_time : '') + (w.planned_session_id ? '' : ' · fuori piano'), 'muted'));
  row.append(text, element('span', st[0], 'chip state-chip'));
  const actions = element('div', undefined, 'session-actions');
  const open = element('button', w.status === 'in_progress' ? 'Continua' : w.status === 'done' ? 'Vedi' : 'Apri', w.status === 'in_progress' ? 'primary small' : 'secondary small');
  open.type = 'button';
  open.onclick = () => openDayWorkout(w);
  actions.append(open);
  if ((w.status === 'chosen' || w.status === 'proposed') && w.planned_session_id) {
    const skip = element('button', 'Salta', 'ghost small');
    skip.type = 'button';
    skip.onclick = async () => {
      try {
        await api('workouts/skip', 'POST', { planned_session_id: w.planned_session_id });
        message('Sessione saltata');
        loadWorkoutWeek();
      } catch (e) {
        message(e.message);
      }
    };
    actions.append(skip);
  }
  row.append(actions);
  return row;
}

async function loadWorkoutCatalog() {
  const cat = await api('workouts/catalog');
  const box = $('wk-catalog');
  box.replaceChildren(
    ...cat.templates.map((t) => {
      const card = element('article', undefined, 'card catalog-card');
      const head = element('div', undefined, 'card-header');
      head.append(element('h3', t.title || t.name), element('span', minutesText(t.duration_minutes_assumed), 'tag'));
      card.append(head, element('p', t.exercises.map(exName).join(' · '), 'muted'));
      if (!t.equipment_feasible) card.append(element('p', 'Attrezzatura mancante', 'error'));
      const actions = element('div', undefined, 'actions');
      const preview = element('button', 'Guarda', 'ghost small');
      preview.type = 'button';
      preview.onclick = () => previewWorkout(t);
      const start = element('button', 'Inizia oggi', 'secondary small');
      start.type = 'button';
      start.disabled = !t.equipment_feasible;
      start.onclick = () => startWorkout({ session_id: t.id, date: isoDate(new Date()) });
      actions.append(preview, start);
      card.append(actions);
      return card;
    }),
  );
  (cat.unavailable_sessions || []).forEach((u) => box.append(element('p', (u.name || u.id) + ': ' + (u.reason || 'non disponibile'), 'muted small')));
}

// ---------- Settimana: generazione ----------
function workoutPlanCard(p, set) {
  const card = element('article', undefined, 'card');card.dataset.planId=p.id;
  if(set.applied_plan_ids?.includes(p.id))card.append(element('span','Applicata in precedenza','tag is-selected'));
  const head = element('div', undefined, 'card-header');
  head.append(roleBadge(p.role), element('span', minutesText(p.weekly_minutes) + ' a settimana', 'tag'));
  card.append(head, explanationBlock(p));
  const list = element('div', undefined, 'week-plan-days');
  (p.workout_sessions || []).forEach((s) => {
    const row = element('div', undefined, 'wp-day');
    row.append(element('strong', parseDate(s.date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' })), element('span', s.session?.title || s.session?.name || s.session_id, 'wp-foods'), element('span', minutesText(s.minutes), 'wp-kcal'));
    list.append(row);
  });
  const details=element('details');details.append(element('summary','Dettaglio delle sessioni'),list);card.append(details);
  card.append(weekButton('Confronta',e=>toggleWeekCompare(p,set,e?.currentTarget||card.querySelector('button'))));
  const apply = element('button', 'Usa questa settimana', 'primary card-cta');
  apply.type = 'button';
  apply.textContent='Rivedi e applica';
  apply.onclick=()=>openPlanReview(p,set);
  card.append(apply);
  return card;
}

$('wk-generate').onclick = async () => {
  await document.querySelector('[data-page="planning"]').onclick();
  selectPlanningDate($('wk-week-start').value);$('week-kind').value='workout';
  availabilityInputs($('joint-availability'),$('week-start').value);syncJointMode();
  $('week-config').open=true;await loadPlanningWeek();$('week-config').scrollIntoView({block:'start'});
};

// ---------- Sessione ----------
// A day's workout may be planned or started freely from the catalog (no planned id).
function openDayWorkout(w) {
  if (w.planned_session_id) return openPlannedWorkout(w.planned_session_id);
  if (w.workout_log_id) return openWorkoutLog(w.workout_log_id);
}
async function openWorkoutLog(logId) {
  if(!document.querySelector('.nav[data-page="workout"]').classList.contains('active'))await document.querySelector('.nav[data-page="workout"]').onclick();
  try {
    const log = await api('workouts/logs/' + logId);
    wkCurrent = { planned: log.planned_session_id ? { id: log.planned_session_id } : null, session: log.session, date: log.date, status: log.ended ? 'done' : 'in_progress', log };
    if(!mealRouteRestoring)history.pushState(null,'','#sessione?log='+log.id+'&data='+log.date);
    renderSession();
    showWorkoutTab('session');
    window.scrollTo({ top: 0 });
  } catch (e) {
    message(e.message);
  }
}
async function openPlannedWorkout(plannedId) {
  if(!document.querySelector('.nav[data-page="workout"]').classList.contains('active'))await document.querySelector('.nav[data-page="workout"]').onclick();
  try {
    const planned = await api('workouts/planned/' + plannedId);
    const day = await api('day?date=' + planned.date);
    const logId = (day.workouts || [day.workout]).find((x) => x?.planned_session_id === plannedId)?.workout_log_id || null;
    wkCurrent = { planned, session: planned.session, date: planned.date, status: planned.status, log: logId ? await api('workouts/logs/' + logId) : null };
    if(!mealRouteRestoring)history.pushState(null,'','#sessione?'+(logId?'log='+logId:'piano='+plannedId)+'&data='+planned.date);
    renderSession();
    showWorkoutTab('session');
    window.scrollTo({ top: 0 });
  } catch (e) {
    message(e.message);
  }
}

function previewWorkout(session) {
  wkCurrent = { planned: null, session, date: isoDate(new Date()), status: 'preview', log: null };
  renderSession();
  showWorkoutTab('session');
  window.scrollTo({ top: 0 });
}

async function startWorkout(body) {
  try {
    const r = await api('workouts/start', 'POST', body);
    const log = await api('workouts/logs/' + r.workout_log_id);
    wkCurrent = { planned: body.planned_session_id ? { id: body.planned_session_id } : null, session: log.session, date: log.date, status: 'in_progress', log };
    if(!document.querySelector('.nav[data-page="workout"]').classList.contains('active'))await document.querySelector('.nav[data-page="workout"]').onclick();
    if(!mealRouteRestoring)history.pushState(null,'','#sessione?log='+log.id+'&data='+log.date);
    renderSession();
    showWorkoutTab('session');
    window.scrollTo({ top: 0 });
  } catch (e) {
    message(e.message);
  }
}

function intensityText(i) {
  if (!i) return null;
  if (i.kind === 'rir') return 'Lascia ' + i.min + '–' + i.max + ' ripetizioni in riserva (RIR)';
  if (i.kind === 'rpe_0_10') return 'Sforzo percepito ' + i.min + '–' + i.max + ' su 10';
  return null;
}

function timelineBar(session) {
  const total = session.duration_seconds || session.timeline.reduce((a, t) => a + t.duration_seconds, 0);
  const bar = element('div', undefined, 'timeline-bar');
  session.timeline.forEach((t) => {
    const seg = element('span', undefined, 'tl-' + t.kind);
    seg.style.width = percent(t.duration_seconds / total);
    seg.title = (timelineNames[t.kind] || t.kind) + ' · ' + clock(t.duration_seconds) + (t.source_id ? ' · ' + (exerciseNames[t.source_id] || t.source_id) : '');
    bar.append(seg);
  });
  const legend = element('div', undefined, 'timeline-legend muted');
  const totals = session.time_breakdown_seconds || {};
  Object.entries(totals)
    .filter(([, v]) => v > 0)
    .forEach(([k, v]) => legend.append(element('span', (timelineNames[k] || k) + ' ' + clock(v), 'tl-key tl-' + k)));
  const box = element('div', undefined, 'timeline');
  box.append(bar, legend);
  return box;
}

function prescription(e, session) {
  if (e.work_seconds && !e.repetitions && !e.sets) return Math.round(e.work_seconds / 60) + ' min continui';
  const parts = [];
  if (e.sets) parts.push(e.sets + ' serie');
  if (e.rounds) parts.push(e.rounds + ' giri');
  if (e.repetitions) parts.push(e.repetitions + ' ripetizioni');
  if (e.hold_seconds) parts.push(e.hold_seconds + ' s di tenuta');
  if (e.work_seconds && (e.rounds || e.sets)) parts.push(e.work_seconds + ' s di lavoro');
  if (e.rest_seconds_between_sets) parts.push('recupero ' + clock(e.rest_seconds_between_sets));
  if (e.load_kg != null) parts.push(e.load_kg + ' kg per manubrio');
  if (e.variant && e.variant !== 'standard') parts.push(variantNames[e.variant] || e.variant);
  return parts.join(' · ');
}

function setCount(e, session) {
  return e.sets || e.rounds || session.parameters?.rounds || 1;
}

function setRow(e, n, session) {
  const log = wkCurrent.log;
  const saved = (log?.sets || []).find((s) => s.exercise_id === (e.exercise_id || e.source_id) && s.set_no === n);
  const open = log && !log.ended;
  const row = element('div', undefined, 'set-row' + (saved ? ' saved' : ''));
  row.append(element('span', (e.rounds ? 'Giro ' : 'Serie ') + n, 'set-label'));
  const fields = [];
  const field = (key, label, value, step) => {
    const wrap = element('label', undefined, 'set-field');
    const input = element('input');
    input.type = 'number';
    input.min = 0;
    input.step = step;
    input.value = value ?? '';
    input.disabled = !open;
    input.dataset.key = key;
    input.setAttribute('aria-label', label + ' ' + (e.rounds ? 'giro ' : 'serie ') + n);
    wrap.append(input, element('span', label, 'muted'));
    fields.push(input);
    row.append(wrap);
  };
  const timed = !e.repetitions;
  if (!timed) field('reps', 'rip.', saved?.reps ?? e.repetitions, 1);
  const weighted = e.load_basis === 'kg_per_dumbbell' || e.load_kg != null || (e.requirements || []).some((r) => /manubri|bilanciere/.test(r));
  if (weighted && !timed) field('kg', e.load_basis === 'kg_per_dumbbell' ? 'kg/manubrio' : 'kg', saved?.kg ?? e.load_kg, 0.5);
  if (timed) {
    const seconds = e.hold_seconds || e.work_seconds;
    if (seconds >= 120) field('minutes', 'min', saved?.seconds != null ? Math.round(saved.seconds / 60) : Math.round(seconds / 60), 1);
    else field('seconds', 's', saved?.seconds ?? seconds, 5);
  }
  if (open) {
    const ok = element('button', saved ? '✓' : 'Fatto', saved ? 'secondary small' : 'primary small');
    ok.type = 'button';
    ok.onclick = async () => {
      const body = { exercise_id: e.exercise_id || e.source_id, set_no: n };
      fields.forEach((i) => {
        if (i.value === '') return;
        const v = Number(i.value);
        if (i.dataset.key === 'minutes') body.seconds = v * 60;
        else body[i.dataset.key] = v;
      });
      try {
        await api('workouts/' + log.id + '/sets', 'POST', body);
        wkCurrent.log = await api('workouts/logs/' + log.id);
        renderSession();
        // The server stores the deadline; renderSession restores it after reload.
      } catch (err) {
        message(err.message);
      }
    };
    row.append(ok);
  } else if (saved) row.append(element('span', '✓', 'set-done'));
  return row;
}

function exerciseCard(e, session) {
  const card = element('article', undefined, 'exercise-card');
  const media = e.media || {};
  const images = media.images?.length ? media.images : media.illustrative_image ? [media.illustrative_image.thumbnail_url] : [];
  if (images.length) {
    const gallery = element('div', undefined, 'exercise-images');
    images.slice(0, 2).forEach((src, i) => {
      const img = element('img');
      img.src = src;
      img.alt = exName(e) + (images.length > 1 ? (e.repetitions ? (i ? ' · fine movimento' : ' · inizio movimento') : ' · foto ' + (i + 1) + ' di ' + images.length) : '');
      img.loading = 'lazy';
      gallery.append(img);
    });
    card.append(gallery);
  }
  const body = element('div', undefined, 'exercise-body');
  body.append(element('h3', exName(e)), element('p', prescription(e, session), 'exercise-dose'));
  const videos = media.youtube_videos || [];
  if (videos.length) {
    const v = element('div', undefined, 'exercise-videos');
    videos.forEach((x) => {
      const a = element('a', '▶ ' + x.title);
      a.href = x.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      v.append(a, element('span', x.channel + (x.duration ? ' · ' + x.duration : ''), 'muted small'));
    });
    body.append(v);
  }
  if (wkCurrent.log) {
    const sets = element('div', undefined, 'set-list');
    for (let n = 1; n <= setCount(e, session); n++) sets.append(setRow(e, n, session));
    body.append(sets);
  }
  if (media.disclaimer) body.append(element('p', media.disclaimer, 'muted small'));
  card.append(body);
  return card;
}

function renderSession() {
  const box = $('wk-session');
  box.replaceChildren();
  if (!wkCurrent) {
    box.append(element('p', 'Apri una sessione dalla settimana o dal catalogo.', 'empty-inline muted'));
    return;
  }
  const { session, log } = wkCurrent;
  if(log&&!log.ended&&log.rest_until>Date.now()/1000)startRestTimer(0,log.rest_until*1000);else stopRestTimer();
  const back=element('button','Torna alla giornata','secondary small');back.type='button';back.onclick=async()=>{homeDate=wkCurrent.date;await document.querySelector('[data-page="home"]').onclick();};box.append(back);
  const status = log ? (log.ended ? 'done' : 'in_progress') : wkCurrent.status;
  const st = status === 'preview' ? ['Anteprima', ''] : workoutStatus[status] || [status, ''];
  const head = element('div', undefined, 'panel session-head');
  const titleRow = element('div', undefined, 'card-header');
  titleRow.append(element('h2', session.title || session.name), element('span', st[0], 'chip state-chip ' + st[1]));
  head.append(titleRow);
  if(log)head.append(element('p','Serie registrate: '+log.sets.length+' / '+session.exercises.reduce((n,e)=>n+setCount(e,session),0),'muted'));
  head.append(element('p', [longDate(wkCurrent.date), minutesText(session.duration_minutes_assumed), intensityText(session.intensity)].filter(Boolean).join(' · '), 'muted'));
  if (session.demo) head.append(element('p', 'Bozza dimostrativa: tempi, serie e intensità sono ipotesi da adattare a te, non una prescrizione.', 'notice warn'));
  const atStart = log?.configuration_at_start;
  if (atStart && atStart.pending_configuration?.length && wkConfig && !wkConfig.missing_fields.some((m) => !m.optional)) {
    head.append(element('p', 'Sessione avviata il ' + shortDate(isoDate(new Date(atStart.recorded_at))) + ' con la configurazione di allora: le modifiche successive valgono dalle prossime sessioni.', 'notice'));
  } else if (session.pending_configuration?.length) {
    const p = element('p', undefined, 'notice');
    const t = element('span', 'Da configurare per questa sessione: ' + session.pending_configuration.length + ' informazioni. ');
    const go = element('button', 'Configura', 'secondary small');
    go.type = 'button';
    go.onclick = () => showWorkoutTab('config');
    t.append(go);
    p.append(t);
    head.append(p);
  }
  if (session.timeline?.length) head.append(timelineBar(session));
  box.append(head);
  const list = element('div', undefined, 'exercise-list');
  session.exercises.forEach((e) => list.append(exerciseCard(e, session)));
  box.append(list);

  const foot = element('div', undefined, 'panel session-foot');
  if (!log && (status === 'chosen' || status === 'proposed')) {
    const start = element('button', 'Inizia l’allenamento', 'primary');
    start.type = 'button';
    start.onclick = () => startWorkout({ planned_session_id: wkCurrent.planned.id, session_id: session.id, date: wkCurrent.date });
    const skip = element('button', 'Salta questa sessione', 'ghost');
    skip.type = 'button';
    skip.onclick = async () => {
      try {
        await api('workouts/skip', 'POST', { planned_session_id: wkCurrent.planned.id });
        wkCurrent.status = 'skipped';
        renderSession();
        message('Sessione saltata');
      } catch (e) {
        message(e.message);
      }
    };
    const bar = element('div', undefined, 'actions');
    bar.append(start, skip);
    foot.append(bar);
  } else if (log && !log.ended) {
    foot.append(element('h3', 'Com’è andata?'));
    foot.append(element('p', 'Sforzo percepito complessivo, da 1 (facilissimo) a 10 (massimo).', 'muted'));
    const rpe = element('div', undefined, 'rpe-scale');
    let chosen = null;
    for (let i = 1; i <= 10; i++) {
      const b = element('button', String(i), 'rpe');
      b.type = 'button';
      b.onclick = () => {
        chosen = i;
        rpe.querySelectorAll('.rpe').forEach((x) => x.classList.toggle('on', Number(x.textContent) === i));
      };
      rpe.append(b);
    }
    const notes = element('textarea');
    notes.rows = 2;
    notes.placeholder = 'Note facoltative: sensazioni, dolori, carichi da cambiare…';
    const expectedSets=session.exercises.reduce((n,e)=>n+setCount(e,session),0);
    const finish = element('button', log.sets.length<expectedSets?'Concludi sessione parziale ('+log.sets.length+'/'+expectedSets+' serie)':'Concludi l’allenamento', 'primary');
    finish.type = 'button';
    finish.onclick = async () => {
      try {
        await api('workouts/' + log.id + '/finish', 'POST', { ...(chosen ? { rpe: chosen } : {}), ...(notes.value.trim() ? { notes: notes.value.trim() } : {}) });
        wkCurrent.log = await api('workouts/logs/' + log.id);
        stopRestTimer();
        renderSession();
        message('Allenamento registrato');
        loadWorkoutWeek();
      } catch (e) {
        message(e.message);
      }
    };
    foot.append(rpe, notes, finish);
  } else if (log?.ended) {
    const minutes = (new Date(log.ended) - new Date(log.started)) / 60000;
    foot.append(element('h3', 'Allenamento concluso'), element('p', [log.sets.length + (log.sets.length === 1 ? ' serie registrata' : ' serie registrate'), isFinite(minutes) ? (minutes < 1 ? 'meno di 1 min' : Math.round(minutes) + ' min') : null, log.rpe ? 'sforzo ' + log.rpe + '/10' : null].filter(Boolean).join(' · '), 'muted'));
    if (log.notes) foot.append(element('p', log.notes));
  } else if (status === 'preview') {
    foot.append(element('p', 'Anteprima dal catalogo: nulla viene registrato finché non inizi.', 'muted'));
    const start = element('button', 'Inizia oggi', 'primary');
    start.type = 'button';
    start.disabled = !session.equipment_feasible;
    start.onclick = () => startWorkout({ session_id: session.id, date: isoDate(new Date()) });
    foot.append(start);
  } else if (status === 'skipped') foot.append(element('p', 'Sessione saltata.', 'muted'));
  box.append(foot);
}

// ---------- Timer di recupero ----------
let restInterval = null;
function startRestTimer(seconds,deadline=Date.now()+seconds*1000) {
  stopRestTimer();
  const box = $('rest-timer');

  const label = element('span');
  const skip = element('button', 'Salta', 'ghost small');
  skip.type = 'button';
  skip.onclick = async()=>{try{if(wkCurrent?.log)wkCurrent.log=await api('workouts/'+wkCurrent.log.id+'/rest/skip','POST',{});stopRestTimer();}catch(e){message(e.message);}};
  box.replaceChildren(element('span', 'Recupero', 'muted'), label, skip);
  box.hidden = false;
  const tick = () => {
    const left=Math.max(0,Math.ceil((deadline-Date.now())/1000));
    label.textContent = clock(left);
    if (left <= 0) {
      stopRestTimer();
      try {
        navigator.vibrate?.(300);
      } catch {}
      message('Recupero finito: prossima serie');
    }

  };
  tick();
  restInterval = setInterval(tick, 1000);
}
function stopRestTimer() {
  clearInterval(restInterval);
  restInterval = null;
  $('rest-timer').hidden = true;
}

// ---------- Configurazione ----------
function renderWorkoutConfig() {
  const form = $('wk-config-form');
  form.replaceChildren();
  if (!wkConfig) return;
  const s = wkConfig.settings;
  const missing = new Set(wkConfig.missing_fields.map((m) => m.field));
  const prompt = Object.fromEntries(wkConfig.missing_fields.map((m) => [m.field, m.prompt]));
  const todo = (field) => (missing.has(field) ? element('span', 'da completare', 'chip todo') : null);
  const panel = (title, text) => {
    const p = element('div', undefined, 'panel');
    p.append(element('h2', title));
    if (text) p.append(element('p', text, 'muted'));
    form.append(p);
    return p;
  };

  const p1 = panel('Livello e intensità', 'Servono a capire se le sessioni dimostrative sono adatte a te. Il livello non genera carichi o progressioni automatiche.');
  const level = element('select');
  level.id = 'cfg-level';
  [['', 'Non dichiarato'], ...Object.entries(levelNames)].forEach(([v, l]) => {
    const o = element('option', l);
    o.value = v;
    level.append(o);
  });
  level.value = s.level || '';
  const levelLabel = element('label', 'Livello di allenamento ');
  if (todo('level')) levelLabel.append(todo('level'));
  levelLabel.append(level);
  p1.append(levelLabel);
  const check = (id, text, checked, field) => {
    const l = element('label', undefined, 'check');
    const i = element('input');
    i.type = 'checkbox';
    i.id = id;
    i.checked = !!checked;
    l.append(i, element('span', text));
    if (field && todo(field)) l.append(todo(field));
    return l;
  };
  p1.append(check('cfg-intensity', prompt.intensity_confirmed || 'Ho verificato che intensità e volume siano adatti a me', s.intensity_confirmed, 'intensity_confirmed'));
  p1.append(check('cfg-hiit', 'Posso eseguire intervalli ad alta intensità (facoltativo)', s.high_intensity_ready));

  const p2 = panel('Attrezzatura disponibile', 'Le sessioni che richiedono attrezzi non selezionati vengono escluse.');
  const chips = element('div', undefined, 'chips');
  const equipment = new Set(s.equipment || []);
  wkConfig.equipment_options.forEach((k) => {
    const l = element('label');
    const i = element('input');
    i.type = 'checkbox';
    i.value = k;
    i.checked = equipment.has(k);
    i.dataset.equipment = '1';
    l.append(i, element('span', equipmentNames[k] || k.replaceAll('_', ' ')));
    chips.append(l);
  });
  p2.append(chips);
  p2.append(check('cfg-australian', 'Ho verificato la postazione per le trazioni australiane (barra stabile all’altezza giusta)', s.australian_pullups_setup_verified));

  const p3 = panel('Carichi', 'Peso di un singolo manubrio. Il carico di partenza deve essere fra quelli disponibili; nessun carico viene dedotto.');
  const loadsLabel = element('label', 'Pesi disponibili per manubrio (kg, separati da virgola) ');
  if (todo('available_loads_kg')) loadsLabel.append(todo('available_loads_kg'));
  const loads = element('input');
  loads.id = 'cfg-loads';
  loads.placeholder = 'es. 4, 6, 8, 10';
  loads.value = (s.available_loads_kg || []).join(', ');
  loadsLabel.append(loads);
  p3.append(loadsLabel);
  const loadExercises = [...new Set([...Object.keys(s.starting_loads_kg || {}), ...wkConfig.missing_fields.filter((m) => m.field.startsWith('starting_loads_kg.')).map((m) => m.field.split('.')[1])])];
  const grid = element('div', undefined, 'grid');
  loadExercises.forEach((ex) => {
    const l = element('label', 'Partenza · ' + (exerciseNames[ex] || ex) + ' (kg per manubrio) ');
    if (todo('starting_loads_kg.' + ex)) l.append(todo('starting_loads_kg.' + ex));
    const i = element('input');
    i.type = 'number';
    i.min = 0;
    i.step = 0.5;
    i.value = s.starting_loads_kg?.[ex] ?? '';
    i.dataset.startLoad = ex;
    l.append(i);
    grid.append(l);
  });
  p3.append(grid);

  const p4 = panel('Varianti eseguibili', 'Scegli la variante che riesci a fare con buona tecnica. Togli la spunta se un esercizio non è eseguibile: le sessioni che lo usano verranno escluse.');
  Object.entries(wkConfig.variant_options).forEach(([ex, choices]) => {
    const row = element('div', undefined, 'variant-row');
    const current = s.variants?.[ex] || {};
    const name = element('span', exerciseNames[ex] || ex, 'variant-name');
    if (todo('variants.' + ex)) name.append(todo('variants.' + ex));
    const select = element('select');
    select.dataset.variant = ex;
    choices.forEach((c) => {
      const o = element('option', variantNames[c] || c);
      o.value = c;
      select.append(o);
    });
    select.value = current.variant || choices[0];
    const exec = element('label', undefined, 'check');
    const i = element('input');
    i.type = 'checkbox';
    i.checked = current.executable !== false;
    i.dataset.executable = ex;
    exec.append(i, element('span', 'eseguibile'));
    row.append(name, select, exec);
    p4.append(row);
  });

  const bar = element('div', undefined, 'save-bar');
  const required = wkConfig.missing_fields.filter((m) => !m.optional).length;
  const status = element('p', required ? 'Configurazione salvata: ' + required + ' informazioni ancora da completare. Compila e salva per aggiornare il conteggio.' : 'Configurazione salvata completa.', 'muted');
  status.id = 'wk-config-status';
  status.setAttribute('role', 'status');
  bar.append(status);
  const feedback = element('p', '', 'notice warn');
  feedback.id = 'wk-config-feedback';
  feedback.setAttribute('role', 'alert');
  feedback.hidden = true;
  bar.append(feedback);
  form.oninput = () => {
    status.textContent = 'Modifiche non salvate. Il conteggio riguarda la configurazione salvata.';
    feedback.hidden = true;
    form.querySelectorAll('[aria-invalid]').forEach(i => { i.removeAttribute('aria-invalid'); i.removeAttribute('aria-describedby'); });
  };
  const save = element('button', 'Salva configurazione', 'primary');
  bar.append(save);
  form.append(bar);
}

$('wk-config-form').onsubmit = async (e) => {
  e.preventDefault();
  const form = $('wk-config-form');
  const feedback = $('wk-config-feedback');
  const fail = (text, input) => {
    feedback.textContent = text;
    feedback.hidden = false;
    if (input) {
      input.setAttribute('aria-invalid', 'true');
      input.setAttribute('aria-describedby', feedback.id);
      input.parentElement.append(feedback);
      input.focus();
    }
  };
  const s = wkConfig.settings;
  const loadText = $('cfg-loads').value.trim();
  // Commas separate weights; decimal values use a point, as in the example.
  if (loadText && loadText.split(/[,;\s]+/).some(x => x && (!Number.isFinite(Number(x)) || Number(x) <= 0 || Number(x) > 1000))) {
    fail('Inserisci pesi positivi separati da virgola; per i decimali usa il punto (es. 2.5, 4, 6).', $('cfg-loads'));
    return;
  }
  const loads = $('cfg-loads')
    .value.split(/[,;\s]+/)
    .map((x) => Number(x.replace(',', '.')))
    .filter((x) => x > 0);
  const starting = { ...(s.starting_loads_kg || {}) };
  document.querySelectorAll('[data-start-load]').forEach((i) => {
    if (i.value === '') delete starting[i.dataset.startLoad];
    else starting[i.dataset.startLoad] = Number(i.value);
  });
  const invalidLoad = [...form.querySelectorAll('[data-start-load]')].find(i => i.value !== '' && !loads.includes(Number(i.value)));
  if (invalidLoad) {
    fail('Il carico di partenza di ' + (exerciseNames[invalidLoad.dataset.startLoad] || invalidLoad.dataset.startLoad) + ' è per singolo manubrio e deve essere fra i pesi disponibili (' + loads.join(', ') + ' kg). Correggi il carico oppure aggiungi il peso disponibile.', invalidLoad);
    return;
  }
  const variants = { ...(s.variants || {}) };
  document.querySelectorAll('[data-variant]').forEach((sel) => {
    const ex = sel.dataset.variant;
    const exec = document.querySelector('[data-executable="' + ex + '"]').checked;
    variants[ex] = { variant: sel.value, executable: exec };
  });
  const body = {
    level: $('cfg-level').value || null,
    intensity_confirmed: $('cfg-intensity').checked,
    high_intensity_ready: $('cfg-hiit').checked,
    australian_pullups_setup_verified: $('cfg-australian').checked,
    equipment: [...document.querySelectorAll('[data-equipment]:checked')].map((i) => i.value),
    available_loads_kg: [...new Set(loads)].sort((a, b) => a - b),
    starting_loads_kg: starting,
    variants,
  };
  const save = form.querySelector('button');
  save.disabled = true;
  feedback.hidden = true;
  $('wk-config-status').textContent = 'Salvataggio in corso…';
  try {
    const r = await api('workouts/config', 'PATCH', body);
    wkConfig = r.workout_configuration;
    const missing = wkConfig.missing_fields.filter(m => !m.optional).length;
    $('wk-config-count').hidden = !missing;
    $('wk-config-count').textContent = missing;
    renderWorkoutConfig();
    // Refresh the banner without discarding a successful response if a read fails.
    loadWorkoutConfig().catch(() => {});
    message('Configurazione salvata');
    loadWorkoutCatalog();
  } catch (err) {
    fail(err.message === 'Failed to fetch' ? 'Connessione interrotta. I valori sono ancora qui: riprova a salvare.' : err.message);
    $('wk-config-status').textContent = 'Salvataggio non riuscito. Le modifiche sono ancora nel modulo.';
  } finally {
    save.disabled = false;
  }
};

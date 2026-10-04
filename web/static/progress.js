// Progressi: check-in del lunedì, peso reale e atteso, settimane, ricalibrazione (passo 5.3, docs/backend-handoff-progress.md).
const measureUnits = { weight: 'kg', waist: 'cm', body_fat: '%', height: 'cm' };
const measureNames = { weight: 'Peso', waist: 'Vita', body_fat: 'Grasso corporeo', height: 'Altezza' };
const kgText = (v, digits = 1) => (v == null ? '—' : v.toLocaleString('it-IT', { minimumFractionDigits: digits, maximumFractionDigits: digits }));
const signed = (v, format) => {
  const text = format(Math.abs(v));
  return (/[1-9]/.test(text) ? (v > 0 ? '+' : '−') : '') + text;
};
const comparisonMeta = {
  plan_not_followed: ['Piano non seguito del tutto', 'cmp-warn'],
  within_expected_uncertainty: ['Peso in linea con l’atteso', 'cmp-ok'],
  response_differs_from_expected: ['Peso diverso dall’atteso', 'cmp-diff'],
};
const groupNames = { daily: 'Giornata standard', rest: 'Giorni di riposo', training: 'Giorni di allenamento' };
const limitNames = {
  weekly_change_cap: 'massimo 100 kcal e 5% a settimana',
  existing_profile_intervals: 'intervalli del profilo',
  fixed_nutrient_floors: 'minimi nutrizionali fissi',
  macro_targets_and_bounds_preserved: 'macronutrienti invariati',
  energy_macro_consistency: 'coerenza fra calorie e macronutrienti',
};
const recalStatus = { pending: 'In attesa', approved: 'Approvata', rejected: 'Rifiutata', superseded: 'Sostituita', expired: 'Scaduta' };
let progressWeeks = 8;

async function loadProgress() {
  if (!$('measure-date').value) $('measure-date').value = isoDate(new Date());
  const checkin = mondayOf(isoDate(new Date()));
  $('checkin-date').textContent = longDate(checkin);
  const [stats, measures, progress, history] = await Promise.all([api('stats/summary'), api('measurements'), api('stats/progress?weeks=' + progressWeeks), api('progress/recalibrations')]);
  renderStats($('progress-tiles'), stats);
  renderMeasures(measures);
  renderWeightChart(progress);
  renderProgressWeeks(progress);
  renderRecalHistory(history);
  const done = measures.some((m) => m.kind === 'weight' && m.date === checkin && m.source === 'manual');
  $('checkin-form').querySelector('button').textContent = done ? 'Rifai il check-in' : 'Fai il check-in';
  // A pending proposal survives reloads: show it until it is decided or expires.
  const pending = history.find((h) => h.status === 'pending' && h.checkin_date === checkin);
  if (pending && !$('checkin-result').childElementCount) $('checkin-result').replaceChildren(proposalCard(pending));
}

function renderMeasures(measures) {
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

// ---------- Grafico del peso ----------
function svg(tag, attrs, cls) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs || {}).forEach(([k, v]) => node.setAttribute(k, v));
  if (cls) node.setAttribute('class', cls);
  return node;
}
function niceStep(span) {
  const raw = span / 4;
  return [0.2, 0.5, 1, 2, 5, 10].find((s) => s >= raw) || 10;
}
function renderWeightChart(data) {
  const box = $('weight-chart');
  const note = $('weight-chart-note');
  box.replaceChildren();
  let start = addDays(mondayOf(data.as_of), -(progressWeeks - 1) * 7);
  const end = addDays(mondayOf(data.as_of), 7);
  const inRange = (d) => d >= start && d <= end;
  const weight = data.weight || {};
  const daily = (weight.daily_points || []).filter((p) => inRange(p.date));
  const segments = (data.expected_weight?.segments || []).filter((s) => inRange(s.week_start));
  // Start at the first week with data (at least 4 weeks shown), not at an empty range.
  const first = [daily[0]?.date, segments[0]?.week_start].filter(Boolean).sort()[0];
  if (first) {
    const latestStart = addDays(end, -28);
    const firstWeek = mondayOf(first);
    if (firstWeek > start) start = firstWeek < latestStart ? firstWeek : latestStart;
  }
  const weeksShown = Math.round((parseDate(end) - parseDate(start)) / 86400000 / 7);
  const notes = [];
  if (weight.status === 'available' && weight.trend_7d != null) notes.push('Andamento filtrato: ' + signed(weight.trend_7d, (v) => kgText(v, 1)) + ' kg negli ultimi 7 giorni.');
  else if (weight.reason) notes.push(weight.reason);
  if (!segments.length)
    notes.push('Nessun peso atteso da confrontare: serve una settimana dieta + palestra applicata, con dati Apple Salute completi e la pesata del lunedì di inizio settimana.');
  notes.push('Il peso atteso è una stima di breve periodo (7700 kcal ≈ 1 kg), non una previsione fisiologica.');
  note.textContent = notes.join(' ');
  if (!daily.length && !segments.length) {
    box.append(element('p', 'Nessuna pesata nelle ultime ' + progressWeeks + ' settimane: inizia con il check-in del lunedì.', 'empty-inline muted'));
    return;
  }
  const values = daily.flatMap((p) => [p.value, p.filtered_kg]).concat(segments.flatMap((s) => s.points.flatMap((p) => [p.low_kg, p.high_kg])));
  let lo = Math.min(...values),
    hi = Math.max(...values);
  const pad = Math.max(0.4, (hi - lo) * 0.12);
  lo -= pad;
  hi += pad;
  if (hi - lo < 2) {
    const mid = (hi + lo) / 2;
    lo = mid - 1;
    hi = mid + 1;
  }
  // Draw at the real width so labels keep their size on phones.
  const W = Math.round(Math.max(300, Math.min(760, box.clientWidth || 640))),
    H = W < 500 ? 210 : 240,
    L = 44,
    R = 12,
    T = 12,
    B = 28;
  const total = weeksShown * 7;
  const x = (date) => L + ((parseDate(date) - parseDate(start)) / 86400000 / total) * (W - L - R);
  const y = (kg) => T + ((hi - kg) / (hi - lo)) * (H - T - B);
  const chart = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img' }, 'chart-svg');
  const last = daily[daily.length - 1];
  chart.setAttribute('aria-label', last ? 'Peso: ultima pesata ' + kgText(last.value) + ' kg il ' + shortDate(last.date) : 'Peso atteso dal piano');
  const step = niceStep(hi - lo);
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    chart.append(svg('line', { x1: L, x2: W - R, y1: y(v), y2: y(v) }, 'grid-line'));
    const label = svg('text', { x: L - 6, y: y(v) + 4, 'text-anchor': 'end' }, 'axis-label');
    label.textContent = kgText(v, step < 1 ? 1 : 0);
    chart.append(label);
  }
  const every = weeksShown > 8 || W < 500 ? 2 : 1;
  for (let i = 0; i <= weeksShown; i += every) {
    const d = addDays(start, i * 7);
    chart.append(svg('line', { x1: x(d), x2: x(d), y1: T, y2: H - B }, 'grid-line vertical'));
    if (i < weeksShown) {
      const label = svg('text', { x: x(d) + 2, y: H - 8 }, 'axis-label');
      label.textContent = shortDate(d);
      chart.append(label);
    }
  }
  // Expected weight: one band per week, never joined across weeks without a forecast.
  segments.forEach((s) => {
    const upper = s.points.map((p) => x(p.date) + ',' + y(p.high_kg));
    const lower = s.points.map((p) => x(p.date) + ',' + y(p.low_kg)).reverse();
    chart.append(svg('polygon', { points: upper.concat(lower).join(' ') }, 'exp-band'));
    chart.append(svg('polyline', { points: s.points.map((p) => x(p.date) + ',' + y(p.central_kg)).join(' ') }, 'exp-line'));
  });
  // Filtered trend, restarted after long gaps (reset).
  let run = [];
  const flush = () => {
    if (run.length > 1) chart.append(svg('polyline', { points: run.join(' ') }, 'trend-line'));
    run = [];
  };
  daily.forEach((p) => {
    if (p.reset) flush();
    run.push(x(p.date) + ',' + y(p.filtered_kg));
  });
  flush();
  daily.forEach((p) => {
    const dot = svg('circle', { cx: x(p.date), cy: y(p.value), r: 3.5 }, 'weight-dot' + (p.source === 'manual' ? ' manual' : ''));
    const title = svg('title');
    title.textContent = shortDate(p.date) + ': ' + kgText(p.value) + ' kg' + (p.raw_count > 1 ? ' (mediana di ' + p.raw_count + ' pesate)' : '') + ' · ' + (p.source === 'manual' ? 'inserita da te' : 'Apple Salute');
    dot.append(title);
    chart.append(dot);
  });
  box.append(chart);
}
document.querySelectorAll('[data-progress-weeks]').forEach(
  (b) =>
    (b.onclick = () => {
      progressWeeks = Number(b.dataset.progressWeeks);
      document.querySelectorAll('[data-progress-weeks]').forEach((x) => x.classList.toggle('active', x === b));
      api('stats/progress?weeks=' + progressWeeks)
        .then((p) => {
          renderWeightChart(p);
          renderProgressWeeks(p);
        })
        .catch((e) => message(e.message));
    }),
);

// ---------- Settimane ----------
function weekLine(label, value, note) {
  const row = element('div', undefined, 'pw-item');
  row.append(element('span', label, 'pw-label'), element('strong', value), note ? element('span', note, 'muted small') : document.createTextNode(''));
  return row;
}
function weekCard(w, asOf) {
  const missing = w.diet?.coverage?.missing_days || [];
  const t0 = w.training || {};
  if (!w.diet?.coverage?.complete_days && missing.length && missing.every((m) => m.reason === 'no_plan') && !t0.planned && !t0.free_done) {
    const quiet = element('article', undefined, 'progress-week quiet');
    quiet.append(element('strong', shortDate(w.week_start) + ' – ' + shortDate(w.week_end)), element('span', 'Nessun piano né allenamento registrato', 'muted small'));
    return quiet;
  }
  const card = element('article', undefined, 'progress-week');
  const head = element('div', undefined, 'pw-head');
  head.append(element('strong', shortDate(w.week_start) + ' – ' + shortDate(w.week_end)));
  if (w.week_end >= asOf) head.append(element('span', 'in corso', 'chip'));
  const c = w.comparison || {};
  if (c.status === 'available') {
    const meta = comparisonMeta[c.classification] || [c.classification, ''];
    head.append(element('span', meta[0], 'chip ' + meta[1]));
  }
  card.append(head);
  const body = element('div', undefined, 'pw-body');
  const d = w.diet || {};
  const cov = d.coverage || {};
  body.append(
    d.status === 'available'
      ? weekLine('Dieta', Math.round(d.value * 100) + '%', d.adherent_meals + '/' + d.assessed_meals + ' pasti come previsto · ' + cov.complete_days + '/7 giorni completi')
      : weekLine('Dieta', '—', 'diario incompleto: ' + (cov.complete_days ?? 0) + '/' + (cov.required_days ?? 5) + ' giorni completi richiesti'),
  );
  const t = w.training || {};
  const free = t.free_done ? ' · ' + t.free_done + ' fuori piano' : '';
  body.append(
    t.status === 'available'
      ? weekLine('Allenamento', t.done + '/' + t.due, (t.skipped ? t.skipped + ' saltati' : 'nessuno saltato') + free)
      : weekLine('Allenamento', t.planned ? '—' : 'nessuno', (t.planned ? t.reason : 'nessuna sessione pianificata') + free),
  );
  if (w.kcal_average?.status === 'available') body.append(weekLine('Kcal medie', fmt0(w.kcal_average.eaten_avg), 'obiettivo ' + fmt0(w.kcal_average.target) + ' · ' + w.kcal_average.days + ' giorni'));
  card.append(body);
  if (c.status === 'available') {
    const text = [c.reason];
    if (c.observed_delta_kg != null) text.push('Peso ' + signed(c.observed_delta_kg, (v) => kgText(v)) + ' kg, atteso ' + signed(c.expected_delta_kg, (v) => kgText(v)) + ' kg.');
    card.append(element('p', text.join(' '), 'small pw-note'));
  } else if (c.reason && w.week_end < asOf) card.append(element('p', 'Confronto non disponibile: ' + c.reason.charAt(0).toLowerCase() + c.reason.slice(1), 'muted small pw-note'));
  return card;
}
function renderProgressWeeks(data) {
  const weeks = [...(data.weeks || [])].reverse();
  $('progress-weeks').replaceChildren(...weeks.map((w) => weekCard(w, data.as_of)));
}

// ---------- Check-in e ricalibrazione ----------
$('checkin-form').onsubmit = async (e) => {
  e.preventDefault();
  const button = e.target.querySelector('button');
  button.disabled = true;
  const box = $('checkin-result');
  try {
    const r = await api('progress/check-in', 'POST', { date: mondayOf(isoDate(new Date())), weight_kg: Number($('checkin-weight').value) });
    $('checkin-weight').value = '';
    box.replaceChildren(checkinSummary(r), recalibrationBlock(r.recalibration));
    message('Check-in registrato');
    await loadProgress();
  } catch (err) {
    message(err.message);
  } finally {
    button.disabled = false;
  }
};
function checkinSummary(r) {
  const w = r.previous_week;
  const box = element('div', undefined, 'checkin-summary');
  if (!w) return box;
  box.append(element('h3', 'La settimana appena conclusa'));
  box.append(weekCard(w, r.date));
  return box;
}
function recalibrationBlock(rec) {
  if (!rec) return element('div');
  if (rec.status === 'available' && rec.proposal) return proposalCard(rec.proposal);
  const n = element('div', undefined, 'notice' + (rec.status === 'no_adjustment' ? ' robust-on' : ''));
  const t = element('span');
  t.append(element('strong', rec.status === 'no_adjustment' ? 'Nessuna modifica necessaria. ' : 'Nessuna proposta di ricalibrazione. '), document.createTextNode(rec.reason || ''));
  n.append(t);
  return n;
}
function proposalCard(p) {
  const card = element('article', undefined, 'card proposal-card');
  const head = element('div', undefined, 'card-header');
  head.append(element('h3', 'Proposta di ricalibrazione'), element('span', signed(p.applied_delta_kcal, fmt0) + ' kcal al giorno', 'chip proposal-delta'));
  card.append(head, element('p', p.rationale, 'headline'));
  const changes = element('div', undefined, 'proposal-changes');
  Object.entries(p.changes || {}).forEach(([group, c]) => {
    const before = c.before?.kcal_100g?.target,
      after = c.after?.kcal_100g?.target;
    if (before == null || after == null) return;
    const row = element('div', undefined, 'pc-row');
    row.append(element('span', groupNames[group] || group), element('span', fmt0(before) + ' kcal', 'muted'), element('span', '→'), element('strong', fmt0(after) + ' kcal'));
    changes.append(row);
  });
  card.append(changes);
  const u = p.data_used || {};
  const e = p.expenditure || {};
  const why = element('ul', undefined, 'reasons');
  why.append(element('li', 'Periodo ' + shortDate(u.start) + ' – ' + shortDate(addDays(u.end, -1)) + ': ' + u.complete_intake_days + ' giornate complete, ' + u.weight_days + ' pesate.'));
  if (u.eaten_average_kcal != null) why.append(element('li', 'Hai mangiato in media ' + fmt0(u.eaten_average_kcal) + ' kcal al giorno; Apple Salute stima un consumo di ' + fmt0(u.health_average_kcal) + ' kcal.'));
  if (u.weight_slope_kg_per_day != null) why.append(element('li', 'Il peso è cambiato di ' + signed(u.weight_slope_kg_per_day * 7, (v) => kgText(v, 2)) + ' kg a settimana.'));
  if (e.value_kcal != null) why.append(element('li', 'Consumo stimato per te: ' + fmt0(e.value_kcal) + ' kcal al giorno (fra ' + fmt0(e.low_kcal) + ' e ' + fmt0(e.high_kcal) + '). È una stima provvisoria, non una misura del metabolismo.'));
  const b = p.energy_balance_target_kcal;
  if (b != null) why.append(element('li', b === 0 ? 'Bilancio scelto: mantenimento.' : 'Bilancio scelto: ' + (b < 0 ? 'deficit' : 'surplus') + ' di ' + fmt0(Math.abs(b)) + ' kcal al giorno.'));
  if (p.requested_delta_kcal != null && Math.round(p.requested_delta_kcal) !== Math.round(p.applied_delta_kcal))
    why.append(element('li', 'La stima indicava ' + signed(p.requested_delta_kcal, fmt0) + ' kcal; per prudenza la variazione è limitata a ' + signed(p.applied_delta_kcal, fmt0) + ' kcal.', 'tradeoff'));
  card.append(why);
  const limits = (p.limits_applied || []).map((l) => limitNames[l] || l);
  if (limits.length) card.append(element('p', 'Limiti di sicurezza rispettati: ' + limits.join(', ') + '.', 'muted small'));
  (p.uncertainty?.limitations || []).forEach((l) => card.append(element('p', l, 'muted small')));
  card.append(element('p', 'Cambiano solo gli obiettivi delle prossime settimane generate: piani già applicati, diario e misure restano come sono.', 'muted small'));
  if (p.status === 'pending') {
    const reason = element('input');
    reason.type = 'text';
    reason.maxLength = 300;
    reason.placeholder = 'Motivo, se non la vuoi (facoltativo)';
    reason.className = 'proposal-reason';
    const actions = element('div', undefined, 'actions');
    const approve = element('button', 'Approva la proposta', 'primary');
    approve.type = 'button';
    const reject = element('button', 'Non ora', 'ghost');
    reject.type = 'button';
    const decide = async (kind) => {
      approve.disabled = reject.disabled = true;
      try {
        const r = await api('progress/recalibrations/' + p.id + '/' + kind, 'POST', { state_token: p.state_token, ...(kind === 'reject' && reason.value.trim() ? { reason: reason.value.trim() } : {}) });
        if (r.profile) profile = r.profile;
        // New targets come from the profile: drop anything the browser remembered.
        jointSave({ targets: undefined, balance: undefined });
        planningReady = false;
        $('checkin-result').replaceChildren(element('p', kind === 'approve' ? 'Proposta approvata: i nuovi obiettivi valgono per le prossime settimane che generi.' : 'Proposta rifiutata: gli obiettivi restano invariati.', 'notice robust-on'));
        await loadProgress();
      } catch (err) {
        approve.disabled = reject.disabled = false;
        message(err.status === 409 ? err.message + ' Rifai il check-in per una proposta aggiornata.' : err.message);
      }
    };
    approve.onclick = () => decide('approve');
    reject.onclick = () => decide('reject');
    actions.append(approve, reject);
    card.append(reason, actions);
  }
  return card;
}
function renderRecalHistory(history) {
  const decided = history.filter((h) => h.status !== 'pending');
  $('recal-history-panel').hidden = !decided.length;
  $('recal-history').replaceChildren(
    ...decided.slice(0, 10).map((h) => {
      const row = element('div', undefined, 'recal-row');
      row.append(
        element('span', shortDate(h.checkin_date)),
        element('span', recalStatus[h.status] || h.status, 'chip' + (h.status === 'approved' ? ' cmp-ok' : '')),
        element('span', signed(h.applied_delta_kcal || 0, fmt0) + ' kcal'),
        element('span', h.decision_reason || '', 'muted small'),
      );
      return row;
    }),
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

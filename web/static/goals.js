// 8.1 — intervista iniziale: quattro blocchi indipendenti, ogni domanda si può saltare.

// Mirrors config/activity-catalog.json (Compendium 2024 ids); the backend validates every id.
const activityNames = {
  walking_slow: 'Camminata lenta',
  walking_moderate: 'Camminata normale',
  walking_brisk: 'Camminata veloce',
  walking_uphill: 'Camminata in salita',
  hiking: 'Escursione',
  cycling_leisure: 'Bici tranquilla',
  cycling_moderate: 'Bici moderata',
  running_light: 'Corsa leggera',
  swimming_leisure: 'Nuoto tranquillo',
  dancing: 'Ballo',
  yoga: 'Yoga',
  pilates: 'Pilates',
  stretching: 'Stretching',
  gardening: 'Giardinaggio',
};
const trainingGoals = [
  ['strength', 'Forza', 'carichi alti, poche ripetizioni'],
  ['hypertrophy', 'Massa muscolare', 'volume settimanale vicino al cedimento'],
  ['muscular_endurance', 'Resistenza muscolare', 'molte ripetizioni, recuperi brevi'],
  ['power', 'Potenza', 'movimenti veloci, pliometria'],
  ['cardio_fitness', 'Fiato', 'minuti di cardio e intervalli'],
  ['fat_loss', 'Perdere grasso', 'soprattutto dalla dieta; i pesi conservano i muscoli'],
  ['health', 'Salute e mantenimento', 'i minimi raccomandati di attività'],
  ['mobility', 'Flessibilità e mobilità', 'stretching, yoga, pilates'],
  ['agility', 'Agilità', 'cambi di direzione'],
];
const priorityNames = ['No', 'Poco', 'Abbastanza', 'Molto'];
const circumferenceNames = { waist: 'Vita', hip: 'Fianchi', chest: 'Petto', arm: 'Braccio', thigh: 'Coscia' };
const anchorExercises = {
  'dumbbell-floor-press': 'Distensioni a terra con manubri',
  'dumbbell-deadlift': 'Stacco con manubri',
  'bodyweight-squat': 'Squat',
  'push-up': 'Piegamenti',
  'inverted-row': 'Rematore inverso',
};
const storeNames = ['Coop', 'Conad', 'Esselunga', 'Carrefour', 'Eurospin', 'Lidl', 'Despar', 'Pam', 'Penny', 'MD', 'Unes', 'Bennet', 'Crai'];
let goals = null;
const fmt1 = (v) => (Math.round(v * 10) / 10).toLocaleString('it-IT');

async function loadGoals() {
  goals = await api('goals');
  renderGoals();
}

function goalsField(label, input, hint) {
  const wrap = element('label', undefined, 'goal-field');
  wrap.append(element('span', label), input);
  if (hint) wrap.append(element('small', hint, 'muted'));
  return wrap;
}
function numberInput(value, min, max, step) {
  const input = element('input');
  input.type = 'number';
  input.min = min;
  input.max = max;
  input.step = step || 'any';
  input.inputMode = 'decimal';
  if (value != null) input.value = value;
  return input;
}
function chipToggles(options, selected, single) {
  const box = element('div', undefined, 'chips');
  const chosen = new Set(selected || []);
  Object.entries(options).forEach(([id, name]) => {
    const b = element('button', name, 'chip-toggle' + (chosen.has(id) ? ' on' : ''));
    b.type = 'button';
    b.setAttribute('aria-pressed', chosen.has(id));
    b.onclick = () => {
      if (single) chosen.clear();
      chosen.has(id) && !single ? chosen.delete(id) : chosen.add(id);
      box.querySelectorAll('.chip-toggle').forEach((x) => {
        const on = chosen.has(x.dataset.id);
        x.classList.toggle('on', on);
        x.setAttribute('aria-pressed', on);
      });
    };
    b.dataset.id = id;
    box.append(b);
  });
  box.value = () => [...chosen];
  return box;
}
function goalsBlock(title, intro, build, save) {
  const block = element('details', undefined, 'goal-block');
  const summary = element('summary');
  summary.append(element('strong', title));
  block.append(summary, element('p', intro, 'muted small'));
  const body = element('div', undefined, 'goal-body');
  const read = build(body);
  const bar = element('div', undefined, 'meal-actions');
  const button = element('button', 'Salva', 'primary small');
  button.type = 'button';
  button.onclick = async () => {
    button.disabled = true;
    try {
      goals = await save(read());
      message(title + ': salvato');
      renderGoals(title);
    } catch (e) {
      message(e.message);
    } finally {
      button.disabled = false;
    }
  };
  bar.append(button);
  block.append(body, bar);
  return block;
}

function renderGoals(open) {
  const panel = $('goals-panel');
  if (!panel || !goals) return;
  panel.replaceChildren(element('h2', 'Obiettivi e intervista'), element('p', 'Ogni domanda si può saltare: un dato che manca resta mancante e il sistema lo dice, senza inventarlo.', 'muted'));
  const b = goals.body,
    a = goals.activity,
    d = goals.activity_defaults || {};

  panel.append(
    goalsBlock('Corpo', 'Dove vuoi arrivare. Peso e misure attuali si registrano in Progressi, con la loro data.', (body) => {
      const weight = numberInput(b.target_weight_kg, 30, 300, 0.1);
      const fat = numberInput(b.target_body_fat_pct, 3, 60, 0.5);
      const date = element('input');
      date.type = 'date';
      date.value = b.target_date || '';
      const pace = element('select');
      [
        ['', 'Non indicato'],
        ['gentle', 'Tranquillo'],
        ['moderate', 'Moderato'],
        ['custom', 'Personalizzato'],
      ].forEach(([v, t]) => pace.append(new Option(t, v, false, (b.pace || '') === v)));
      const pct = numberInput(b.pace_pct_per_week, 0.05, 1, 0.05);
      const pctField = goalsField('% del peso a settimana', pct, 'In perdita al massimo 1%, in aumento al massimo 0,5%.');
      const syncPace = () => (pctField.hidden = pace.value !== 'custom');
      pace.onchange = syncPace;
      syncPace();
      const circ = chipToggles(circumferenceNames, b.circumferences);
      const grid = element('div', undefined, 'goal-grid');
      grid.append(
        goalsField('Peso obiettivo (kg)', weight),
        goalsField('oppure massa grassa obiettivo (%)', fat, 'Dalla bilancia a bioimpedenza: si usa l’andamento, non il singolo valore.'),
        goalsField('Entro (facoltativo)', date, 'Almeno fra quattro settimane.'),
        goalsField('Ritmo', pace, 'Tranquillo: 0,25% del peso a settimana in perdita · Moderato: 0,5%.'),
        pctField,
      );
      body.append(grid, element('p', 'Circonferenze da seguire', 'goal-label'), circ);
      return () => {
        const out = {};
        const num = (x) => (x.value === '' ? null : Number(x.value));
        if (num(weight) != null) out.target_weight_kg = num(weight);
        if (num(fat) != null) out.target_body_fat_pct = num(fat);
        if (date.value) out.target_date = date.value;
        if (pace.value) out.pace = pace.value;
        if (pace.value === 'custom' && num(pct) != null) out.pace_pct_per_week = num(pct);
        out.circumferences = circ.value();
        return out;
      };
    }, (data) => api('goals/body', 'PUT', data)),
  );

  panel.append(
    goalsBlock('Attività e tempo', 'La palestra non è obbligatoria: camminare, andare in bici o nuotare valgono quanto lei.', (body) => {
      const gym = chipToggles({ yes: 'Sì', maybe: 'Forse', no: 'No' }, a.gym ? [a.gym] : [], true);
      const liked = chipToggles(activityNames, a.liked_activities);
      const disliked = chipToggles(activityNames, a.disliked_activities);
      const minutes = numberInput(a.max_session_minutes ?? d.max_session_minutes, 20, 240, 5);
      const perDay = element('select');
      [
        [1, 'Una'],
        [2, 'Fino a due'],
      ].forEach(([v, t]) => perDay.append(new Option(t, v, false, (a.max_sessions_per_day ?? d.max_sessions_per_day) === v)));
      const gap = numberInput(a.min_gap_hours ?? d.min_gap_hours, 1, 24, 1);
      const stores = chipToggles(Object.fromEntries(storeNames.map((s) => [s, s])), a.preferred_stores);
      const grid = element('div', undefined, 'goal-grid');
      grid.append(
        goalsField('Durata massima di una seduta (min)', minutes, 'Una scelta tua, non un limite fisiologico.'),
        goalsField('Sedute nello stesso giorno', perDay),
        goalsField('Ore minime fra due sedute', gap),
      );
      body.append(
        element('p', 'Vuoi includere la palestra?', 'goal-label'),
        gym,
        element('p', 'Attività che ti piacciono', 'goal-label'),
        liked,
        element('p', 'Attività da non proporre', 'goal-label'),
        disliked,
        grid,
        element('p', 'Supermercati dove fai la spesa', 'goal-label'),
        stores,
        element('small', 'Servono a proporre i prodotti da comprare; non indicano l’assortimento reale del negozio.', 'muted'),
      );
      return () => {
        const out = {
          liked_activities: liked.value(),
          disliked_activities: disliked.value(),
          max_session_minutes: Number(minutes.value) || d.max_session_minutes,
          max_sessions_per_day: Number(perDay.value),
          min_gap_hours: Number(gap.value) || d.min_gap_hours,
          preferred_stores: stores.value(),
        };
        if (gym.value()[0]) out.gym = gym.value()[0];
        return out;
      };
    }, (data) => api('goals/activity', 'PUT', data)),
  );

  panel.append(
    goalsBlock('Obiettivi di allenamento', 'Quanto conta ciascun obiettivo. Al massimo tre su «Molto».', (body) => {
      const selects = {};
      const list = element('div', undefined, 'goal-priorities');
      trainingGoals.forEach(([id, name, hint]) => {
        const row = element('div', undefined, 'goal-priority');
        const label = element('div');
        label.append(element('strong', name), element('small', hint, 'muted'));
        const seg = element('div', undefined, 'segmented goal-seg');
        const current = goals.training_priorities[id] ?? 0;
        priorityNames.forEach((t, v) => {
          const b = element('button', t, 'seg' + (v === current ? ' active' : ''));
          b.type = 'button';
          b.onclick = () => {
            seg.querySelectorAll('button').forEach((x) => x.classList.remove('active'));
            b.classList.add('active');
            selects[id] = v;
          };
          seg.append(b);
        });
        selects[id] = current;
        row.append(label, seg);
        list.append(row);
      });
      body.append(list);
      (goals.warnings || []).forEach((w) => body.append(element('p', w.message, 'notice warn')));
      body.append(element('p', '«Aumentare il metabolismo» e «postura» non sono obiettivi a sé: l’effetto reale è piccolo o le prove sono deboli. Rientrano in perdere grasso, massa muscolare, salute e mobilità.', 'muted small'));
      return () => Object.fromEntries(Object.entries(selects).filter(([, v]) => v > 0));
    }, (data) => api('goals/training', 'PUT', { priorities: data })),
  );

  if (a.gym !== 'no')
    panel.append(
      goalsBlock('Carichi di riferimento', 'Una serie pesante (2–6 ripetizioni pulite) e una leggera (10–15) recenti. Ne basta una; il massimale su una ripetizione non serve.', (body) => {
        const rows = {};
        const today = isoDate(new Date());
        Object.entries(anchorExercises).forEach(([key, name]) => {
          const known = goals.strength_anchors.find((x) => x.exercise_key === key) || {};
          const row = element('div', undefined, 'anchor-row');
          row.append(element('strong', name));
          const sets = {};
          [
            ['heavy', 'Pesante', 2, 6],
            ['light', 'Leggera', 10, 15],
          ].forEach(([kind, label, lo, hi]) => {
            const kg = numberInput(known[kind]?.kg, 0, 1000, 0.5);
            kg.placeholder = 'kg';
            const reps = numberInput(known[kind]?.reps, lo, hi, 1);
            reps.placeholder = lo + '–' + hi;
            const box = element('div', undefined, 'anchor-set');
            box.append(element('span', label, 'muted small'), kg, element('span', 'kg ×', 'muted'), reps, element('span', 'rip.', 'muted'));
            row.append(box);
            sets[kind] = () => (kg.value && reps.value ? { kg: Number(kg.value), reps: Number(reps.value), date: known[kind]?.date || today } : null);
          });
          rows[key] = sets;
          body.append(row);
        });
        return () =>
          Object.entries(rows)
            .map(([exercise_key, s]) => {
              const out = { exercise_key };
              const heavy = s.heavy(),
                light = s.light();
              if (heavy) out.heavy = heavy;
              if (light) out.light = light;
              return heavy || light ? out : null;
            })
            .filter(Boolean);
      }, (data) => api('goals/strength-anchors', 'PUT', { anchors: data })),
    );

  panel.append(energyProposalBlock(), dayTargetsBlock());
  const missing = goals.missing || [];
  if (missing.length) {
    const box = element('details', undefined, 'goal-missing');
    box.append(element('summary', missing.length === 1 ? 'Una risposta mancante limita i calcoli' : missing.length + ' risposte mancanti limitano i calcoli'));
    const ul = element('ul');
    missing.forEach((m) => ul.append(element('li', m.prompt)));
    box.append(ul);
    panel.append(box);
  }
  if (open) panel.querySelectorAll('.goal-block').forEach((x) => x.querySelector('strong').textContent === open && (x.open = true));
}

function energyProposalBlock() {
  const box = element('div', undefined, 'goal-energy');
  box.append(element('h3', 'Bilancio calorico dall’obiettivo'), element('p', 'Dal tuo peso filtrato, dall’obiettivo e dal ritmo: una proposta, da approvare. I target nutrizionali non cambiano.', 'muted small'));
  const out = element('div');
  const ask = element('button', 'Calcola la proposta', 'secondary small');
  ask.type = 'button';
  ask.onclick = async () => {
    ask.disabled = true;
    try {
      const r = await api('goals/energy-proposal', 'POST', {});
      out.replaceChildren(r.status === 'available' ? energyProposalCard(r.proposal, out) : element('p', r.reason, 'notice'));
    } catch (e) {
      out.replaceChildren(element('p', e.message, 'error'));
    } finally {
      ask.disabled = false;
    }
  };
  box.append(ask, out);
  return box;
}

function energyProposalCard(p, out) {
  const card = element('article', undefined, 'card proposal-card');
  const fmtBal = (v) => (v == null ? 'nessuno' : (v > 0 ? '+' : v < 0 ? '−' : '') + fmt0(Math.abs(v)) + ' kcal/giorno');
  const head = element('div', undefined, 'proposal-head');
  head.append(element('span', 'Ora: ' + fmtBal(p.current_kcal), 'muted'), element('strong', 'Proposto: ' + fmtBal(p.proposed_kcal)));
  card.append(head);
  const facts = [];
  if (p.weight) facts.push('Peso filtrato ' + fmt1(p.weight.value_kg) + ' kg (' + parseDate(p.weight.date).toLocaleDateString('it-IT') + ')');
  if (p.target_weight_kg != null) facts.push('obiettivo ' + fmt1(p.target_weight_kg) + ' kg');
  if (p.effective_pace_pct_per_week != null) facts.push('ritmo ' + p.effective_pace_pct_per_week.toLocaleString('it-IT', { maximumFractionDigits: 2 }) + '% del peso a settimana');
  if (p.expected_date) facts.push('arrivo stimato ' + parseDate(p.expected_date).toLocaleDateString('it-IT', { month: 'long', year: 'numeric' }));
  card.append(element('p', facts.join(' · ')));
  const ul = element('ul', undefined, 'reasons');
  (p.reasoning || []).forEach((r) => ul.append(element('li', r)));
  (p.uncertainty || []).forEach((r) => ul.append(element('li', r, 'tradeoff')));
  card.append(ul);
  const bar = element('div', undefined, 'meal-actions');
  [
    ['approve', 'Usa questo bilancio', 'primary small'],
    ['reject', 'Non ora', 'ghost small'],
  ].forEach(([decision, text, cls]) => {
    const b = element('button', text, cls);
    b.type = 'button';
    b.onclick = async () => {
      bar.querySelectorAll('button').forEach((x) => (x.disabled = true));
      try {
        const r = await api('goals/energy-proposal/' + p.id + '/' + decision, 'POST', { state_token: p.state_token });
        if (r.balance_changed) {
          profile.energy_balance_target_kcal = p.proposed_kcal;
          planningReady = false;
        }
        out.replaceChildren(element('p', r.balance_changed ? 'Bilancio aggiornato: vale per le prossime settimane generate.' : 'Proposta scartata, nulla è cambiato.', 'notice'));
      } catch (e) {
        out.replaceChildren(element('p', e.status === 409 ? 'Qualcosa è cambiato o la proposta non vale più: ricalcolala.' : e.message, 'error'));
      }
    };
    bar.append(b);
  });
  card.append(bar);
  return card;
}

// 8.5 — target quotidiani proposti dall'attività della settimana.
function dayTargetsBlock() {
  const box = element('div', undefined, 'goal-energy');
  box.append(
    element('h3', 'Target del giorno dall’attività'),
    element('p', 'Calorie di ogni giorno = base senza allenamenti + energia prudente di allenamenti e attività + bilancio approvato. Proteine costanti per kg, grassi protetti, i carboidrati assorbono la differenza.', 'muted small'),
  );
  const today = isoDate(new Date());
  const week = element('select');
  week.setAttribute('aria-label', 'Settimana');
  [
    [mondayOf(today), 'Questa settimana'],
    [addDays(mondayOf(today), 7), 'Prossima settimana'],
  ].forEach(([v, t]) => {
    const o = element('option', t + ' (' + shortDate(v) + ')');
    o.value = v;
    week.append(o);
  });
  const base = numberInput('', 1000, 6000, 10);
  base.placeholder = 'automatica';
  const row = element('div', undefined, 'goal-grid');
  row.append(goalsField('Settimana', week), goalsField('Base senza allenamenti (kcal)', base, 'Facoltativa: vuota usa Salute o la stima dal profilo'));
  const out = element('div');
  const ask = element('button', 'Calcola la proposta', 'secondary small');
  ask.type = 'button';
  ask.onclick = async () => {
    ask.disabled = true;
    out.replaceChildren(element('p', 'Calcolo…', 'muted small'));
    const body = { week_start: week.value };
    if (base.value !== '') body.estimated_non_workout_kcal = Number(base.value);
    try {
      const r = await api('goals/day-targets/proposal', 'POST', body);
      out.replaceChildren(r.status === 'available' ? dayTargetsCard(r.proposal, out) : element('p', r.reason || 'Proposta non disponibile.', 'notice'));
    } catch (e) {
      out.replaceChildren(element('p', e.message, 'error'));
    } finally {
      ask.disabled = false;
    }
  };
  box.append(row, ask, out);
  return box;
}

function dayTargetsCard(p, out) {
  const card = element('article', undefined, 'card proposal-card');
  const b = p.baseline || {};
  const facts = [];
  facts.push('Base ' + fmt0(b.central_kcal) + ' kcal (' + (b.source === 'user_declared_non_workout_estimate' ? 'dichiarata da te' : b.source === 'current_target_minus_approved_balance_estimate' ? 'stimata dal profilo, non misurata' : 'da Salute') + ')');
  facts.push('bilancio approvato ' + (p.energy_balance_target_kcal > 0 ? '+' : '') + fmt0(p.energy_balance_target_kcal) + ' kcal');
  if (p.weight) facts.push('peso filtrato ' + fmt1(p.weight.value_kg) + ' kg (' + parseDate(p.weight.date).toLocaleDateString('it-IT') + ')');
  const pr = p.parameters || {};
  if (pr.protein_g_per_kg) facts.push('proteine ' + fmt1(pr.protein_g_per_kg) + ' g/kg, come già scelto');
  card.append(element('p', facts.join(' · ')));
  const table = element('table', undefined, 'targets-table');
  const head = element('tr');
  ['Giorno', 'Attività', 'Ora', 'Richiesto', 'Proposto', 'P · C · G'].forEach((h) => head.append(element('th', h)));
  table.append(head);
  let limited = false;
  (p.days || []).forEach((d) => {
    const tr = element('tr');
    const t = d.targets || {};
    const prev = d.before?.kcal_100g?.target ?? d.proposed_kcal - (d.delta_kcal || 0);
    if (d.limited) limited = true;
    tr.append(
      element('td', parseDate(d.date).toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' })),
      element('td', d.net_activity_low_kcal ? '+' + fmt0(d.net_activity_low_kcal) : '—'),
      element('td', fmt0(prev)),
      element('td', fmt0(d.requested_kcal)),
      element('td', fmt0(d.proposed_kcal) + (d.limited ? ' *' : ''), d.delta_kcal ? 'changed' : ''),
      element('td', [t.protein_g_100g, t.carbs_available_g_100g, t.fat_g_100g].map((x) => fmt0(x?.target)).join(' · ')),
    );
    table.append(tr);
  });
  const wrap = element('div', undefined, 'table-scroll');
  wrap.append(table);
  card.append(wrap);
  if (limited) card.append(element('p', '* Variazione limitata a ' + fmt0(pr.maximum_weekly_change_kcal || 100) + ' kcal o 5% a settimana: il resto arriverà gradualmente.', 'muted small'));
  const ul = element('ul', undefined, 'reasons');
  (p.reasoning || []).forEach((r) => ul.append(element('li', r)));
  [...new Set([b.uncertainty, ...(p.uncertainty || [])].filter(Boolean))].forEach((r) => ul.append(element('li', r, 'tradeoff')));
  card.append(ul);
  const bar = element('div', undefined, 'meal-actions');
  [
    ['approve', 'Usa i valori proposti', 'primary small'],
    ['reject', 'Mantieni i valori attuali', 'ghost small'],
  ].forEach(([decision, text, cls]) => {
    const btn = element('button', text, cls);
    btn.type = 'button';
    btn.onclick = async () => {
      bar.querySelectorAll('button').forEach((x) => (x.disabled = true));
      try {
        const r = await api('goals/day-targets/proposal/' + p.id + '/' + decision, 'POST', { state_token: p.state_token });
        if (r.targets_changed) {
          profile = (await api('profile')).profile;
          planningReady = false;
        }
        out.replaceChildren(element('p', r.targets_changed ? 'Target aggiornati. Rigenera il piano della settimana per applicarli: pasti e allenamenti già applicati non cambiano.' : 'Proposta scartata, nulla è cambiato.', 'notice'));
      } catch (e) {
        out.replaceChildren(element('p', e.status === 409 ? 'Dati, programma o profilo sono cambiati: ricalcola la proposta.' : e.message, 'error'));
      }
    };
    bar.append(btn);
  });
  card.append(bar);
  return card;
}

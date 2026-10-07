// Profilo guidato: tre passi, uno stato e un'azione ciascuno. Il resto sta in «Impostazioni avanzate».
// 1 · I tuoi dati (peso e consumo)   2 · Il tuo obiettivo (bilancio)   3 · Calorie del giorno (riposo/palestra)

async function renderSetup() {
  const root = $('setup-panel');
  if (!root) return;
  const [health, measures, g] = await Promise.all([api('health').catch(() => null), api('measurements').catch(() => []), goals ? Promise.resolve(goals) : api('goals')]);
  goals = g;
  const today = isoDate(new Date());
  const yearAgo = addDays(today, -365);
  const weights = measures.filter((m) => m.kind === 'weight' && m.date >= yearAgo).sort((a, b) => (a.date < b.date ? 1 : -1));
  const weightDays = new Set(weights.map((m) => m.date)).size;
  const latest = weights[0];
  const rep = health?.imported ? health.report : null;
  const sc = rep?.scenarios;
  const body = goals.body || {};
  const dt = profile.day_type_targets;
  const personalTargets = dt?.rest?.kcal_100g?.target && !!profile.approved_activity_targets?.approved_on;

  const step1ok = weightDays >= 2;
  const step2ok = profile.energy_balance_target_kcal != null && (body.target_weight_kg || body.target_body_fat_pct);
  const step3ok = !!personalTargets;

  root.replaceChildren(element('h2', 'Le tue calorie'), element('p', 'Tre passi. Ognuno parte dai dati del precedente.', 'muted'));
  root.append(
    setupStep(1, 'I tuoi dati', step1ok, (box) => {
      const facts = element('div', undefined, 'setup-facts');
      facts.append(
        setupFact('Peso', latest ? fmt1(latest.value) + ' kg' : '—', latest ? shortDate(latest.date) + (latest.source === 'apple_health' ? ' · Salute' : '') : 'mai registrato'),
        setupFact('Consumo medio', sc?.status === 'available' ? fmt0(sc.central_kcal) + ' kcal' : '—', sc?.status === 'available' ? 'al giorno, da Salute' : rep ? 'dati Salute vecchi' : 'Salute non importata'),
        setupFact('Altezza', rep?.measures?.height ? fmt0(rep.measures.height.value) + ' cm' : '—', rep?.measures?.height ? 'da Salute' : 'non indicata'),
      );
      box.append(facts);
      if (!step1ok) box.append(element('p', weightDays ? 'Serve un’altra pesata in un giorno diverso per vedere l’andamento.' : 'Servono due pesate in giorni diversi per vedere l’andamento.', 'setup-hint'));
      box.append(weightForm());
    }),
    setupStep(2, 'Il tuo obiettivo', step2ok, (box) => {
      const weight = numberInput(body.target_weight_kg, 30, 300, 0.1);
      weight.placeholder = 'es. 75';
      const pace = element('div', undefined, 'segmented small-seg');
      let paceValue = body.pace === 'custom' ? 'custom' : body.pace || 'gentle';
      [
        ['gentle', 'Tranquillo'],
        ['moderate', 'Moderato'],
      ].forEach(([v, t]) => {
        const b = element('button', t, 'seg' + (paceValue === v ? ' active' : ''));
        b.type = 'button';
        b.onclick = () => {
          paceValue = v;
          pace.querySelectorAll('.seg').forEach((x) => x.classList.toggle('active', x === b));
        };
        pace.append(b);
      });
      const row = element('div', undefined, 'setup-row');
      row.append(goalsField('Peso obiettivo (kg)', weight), goalsField('Ritmo', pace));
      box.append(row);
      if (profile.energy_balance_target_kcal != null) box.append(element('p', 'Bilancio attuale: ' + balanceText(profile.energy_balance_target_kcal), 'setup-current'));
      const out = element('div');
      const go = element('button', 'Calcola il bilancio', 'primary');
      go.type = 'button';
      go.disabled = !step1ok;
      if (!step1ok) box.append(element('p', 'Prima completa il passo 1.', 'muted small'));
      go.onclick = async () => {
        go.disabled = true;
        out.replaceChildren(element('p', 'Calcolo…', 'muted small'));
        try {
          if (weight.value) {
            const next = { ...body, target_weight_kg: Number(weight.value), pace: paceValue };
            if (paceValue !== 'custom') delete next.pace_pct_per_week;
            Object.keys(next).forEach((k) => next[k] == null && delete next[k]);
            goals = await api('goals/body', 'PUT', next);
          }
          const r = await api('goals/energy-proposal', 'POST', {});
          out.replaceChildren(r.status === 'available' ? balanceProposal(r.proposal) : element('p', r.reason, 'setup-hint'));
        } catch (e) {
          out.replaceChildren(element('p', e.message, 'error'));
        } finally {
          go.disabled = false;
        }
      };
      box.append(go, out);
    }),
    setupStep(3, 'Calorie del giorno', step3ok, (box) => {
      if (personalTargets) {
        const facts = element('div', undefined, 'setup-facts');
        facts.append(setupFact('Giorno di riposo', fmt0(dt.rest.kcal_100g.target) + ' kcal', 'P ' + fmt0(dt.rest.protein_g_100g?.target) + ' g'));
        if (dt.training?.kcal_100g) facts.append(setupFact('Giorno di palestra', fmt0(dt.training.kcal_100g.target) + ' kcal', 'P ' + fmt0(dt.training.protein_g_100g?.target) + ' g'));
        box.append(facts);
      } else box.append(element('p', 'Ancora valori di prova: calcolali dai tuoi dati.', 'setup-hint'));
      const out = element('div');
      const go = element('button', personalTargets ? 'Ricalcola per questa settimana' : 'Calcola le mie calorie', personalTargets ? 'secondary' : 'primary');
      go.type = 'button';
      go.disabled = !step1ok;
      if (!step1ok) box.append(element('p', 'Prima completa il passo 1.', 'muted small'));
      go.onclick = async () => {
        go.disabled = true;
        out.replaceChildren(element('p', 'Calcolo…', 'muted small'));
        try {
          // Whole-day calories need the whole-day mode (breakfast and snacks included): enable it rather than dead-ending.
          if (!profile.daily_meals?.enabled) await saveProfilePatch({ daily_meals: { ...profile.daily_meals, enabled: true } });
          const r = await api('goals/day-targets/proposal', 'POST', { week_start: mondayOf(today) });
          out.replaceChildren(r.status === 'available' ? dayTargetsCard(r.proposal, out) : element('p', r.reason || 'Proposta non disponibile.', 'setup-hint'));
        } catch (e) {
          out.replaceChildren(element('p', e.message, 'error'));
        } finally {
          go.disabled = false;
        }
      };
      box.append(go, out);
    }),
  );
}

function setupStep(n, title, ok, build) {
  const step = element('section', undefined, 'setup-step' + (ok ? ' done' : ''));
  const head = element('div', undefined, 'setup-head');
  head.append(element('span', ok ? '✓' : String(n), 'setup-num'), element('h3', title));
  step.append(head);
  const body = element('div', undefined, 'setup-body');
  build(body);
  step.append(body);
  return step;
}
function setupFact(label, value, note) {
  const f = element('div', undefined, 'setup-fact');
  f.append(element('span', label, 'muted small'), element('strong', value));
  if (note) f.append(element('span', note, 'muted small'));
  return f;
}
const balanceText = (v) => (v === 0 ? 'mantenimento' : (v < 0 ? '−' : '+') + fmt0(Math.abs(v)) + ' kcal al giorno');

function weightForm() {
  const form = element('form', undefined, 'setup-inline');
  const input = numberInput('', 30, 300, 0.1);
  input.placeholder = 'kg';
  input.setAttribute('aria-label', 'Peso di oggi in kg');
  const b = element('button', 'Registra il peso di oggi', 'secondary small');
  b.type = 'submit';
  form.append(input, b);
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!input.value) return input.focus();
    b.disabled = true;
    try {
      await api('measurements', 'POST', { date: isoDate(new Date()), kind: 'weight', value: Number(input.value), unit: 'kg' });
      message('Peso registrato');
      renderSetup();
    } catch (err) {
      message(err.message);
      b.disabled = false;
    }
  };
  return form;
}

function balanceProposal(p) {
  const card = element('div', undefined, 'setup-proposal');
  card.append(element('strong', 'Proposta: ' + balanceText(p.proposed_kcal)));
  const facts = [];
  if (p.expected_date) facts.push('arrivo stimato ' + parseDate(p.expected_date).toLocaleDateString('it-IT', { month: 'long', year: 'numeric' }));
  if (p.effective_pace_pct_per_week != null) facts.push(p.effective_pace_pct_per_week.toLocaleString('it-IT', { maximumFractionDigits: 2 }) + '% del peso a settimana');
  if (facts.length) card.append(element('p', facts.join(' · '), 'muted small'));
  if (p.reasoning?.length || p.uncertainty?.length) {
    const more = element('details');
    more.append(element('summary', 'Perché'));
    [...(p.reasoning || []), ...(p.uncertainty || [])].forEach((r) => more.append(element('p', r, 'muted small')));
    card.append(more);
  }
  const bar = element('div', undefined, 'meal-actions');
  [
    ['approve', 'Usa questo bilancio', 'primary small'],
    ['reject', 'Non ora', 'ghost small'],
  ].forEach(([d, t, c]) => {
    const b = element('button', t, c);
    b.type = 'button';
    b.onclick = async () => {
      bar.querySelectorAll('button').forEach((x) => (x.disabled = true));
      try {
        const r = await api('goals/energy-proposal/' + p.id + '/' + d, 'POST', { state_token: p.state_token });
        if (r.balance_changed) {
          profile.energy_balance_target_kcal = p.proposed_kcal;
          planningReady = false;
          message('Bilancio salvato. Ora il passo 3.');
        }
        renderSetup();
      } catch (e) {
        card.append(element('p', e.status === 409 ? 'Qualcosa è cambiato: ricalcola.' : e.message, 'error'));
      }
    };
    bar.append(b);
  });
  card.append(bar);
  return card;
}

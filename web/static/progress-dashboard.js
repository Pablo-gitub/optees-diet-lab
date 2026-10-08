// Energy and ordered milestones share existing APIs, tokens and navigation.
let energyRequest = 0, milestoneData;
const milestoneLabels = { weight_kg: 'Peso', body_fat_pct: 'Grasso corporeo', sessions_per_week: 'Sessioni per settimana' };
const dashboardErrorText = e => /failed to fetch|networkerror/i.test(e.message || '') ? 'Connessione non disponibile. I dati sono conservati; riprova.' : e.message;
const milestoneUnits = { weight_kg: 'kg', body_fat_pct: '%', sessions_per_week: 'sessioni' };
const energyRangeText = r => !r ? '—' : r.min === r.max ? fmt0(r.min) : fmt0(r.min) + '–' + fmt0(r.max);
function dashboardError(box, error, retry) {
  box.replaceChildren(element('p', dashboardErrorText(error) || 'Dati non disponibili. Riprova.', 'notice'));
  const b = element('button', 'Riprova', 'secondary'); b.type = 'button'; b.onclick = retry; box.append(b);
}
async function loadEnergy() {
  const request = ++energyRequest, box = $('energy-content');
  box.setAttribute('aria-busy', 'true');
  try {
    const data = await api('progress/energy?start=' + $('energy-start').value);
    if (request !== energyRequest) return;
    box.replaceChildren();
    if(data.synthetic)box.append(element('p','Demo: dati energetici e misure sintetici, per verificare i grafici.','notice'));
    box.append(element('p', 'Assunzione meno dispendio = saldo. Un saldo giornaliero compare solo con tutti i pasti e dati Salute sufficienti. Le sessioni sono già incluse nel dispendio.', 'muted small'));
    const versions = element('select'); versions.setAttribute('aria-label', 'Versione del piano energetico');
    versions.append(new Option('Piano attuale', ''));
    data.versions.forEach(v => versions.append(new Option('Versione ' + v.id + ' · ' + new Date(v.created * 1000).toLocaleString('it-IT'), String(v.id))));
    const charts = element('div', undefined, 'energy-charts'), detail = element('div', undefined, 'energy-day-detail'); detail.setAttribute('aria-live', 'polite');
    const table = element('details'); table.append(element('summary', 'Valori, copertura e dettaglio dei giorni'));
    function render() {
      const selected = data.versions.find(v => String(v.id) === versions.value);
      const rows = data.days.map(d => ({ ...d, ...(selected?.payload.days.find(p => p.date === d.date) || {}) }));
      charts.replaceChildren(energyChart(rows, false), energyChart(rows, true));
      table.replaceChildren(element('summary', 'Valori, copertura e dettaglio dei giorni'));
      table.append(healthTable(['Giorno', 'Ambito previsto', 'Assunzione prevista', 'Dispendio previsto', 'Registrato', 'Salute', 'Copertura'], rows.map(d => [shortDate(d.date), d.scope==='full_day_planned_meals'?'Giornata intera':'Parziale/non specificato', energyRangeText(d.planned_intake), d.planned_expenditure ? fmt0(d.planned_expenditure.central) + ' (' + fmt0(d.planned_expenditure.low) + '–' + fmt0(d.planned_expenditure.high) + ')' : '—', energyRangeText(d.registered_intake), d.health_expenditure == null ? '—' : fmt0(d.health_expenditure), (d.diary_complete ? 'Diario completo' : d.logged_slots + '/5 pasti · parziale') + ' · ' + (d.health_complete ? 'Salute sufficiente' : 'Salute assente/parziale')])));
      const days = element('div', undefined, 'energy-days');
      rows.forEach(d => { const b = element('button', shortDate(d.date), 'ghost small'); b.type = 'button'; b.onclick = () => {
        detail.replaceChildren(element('h3', longDate(d.date)), element('p', d.scope === 'full_day_planned_meals' ? 'Ambito: giornata intera.' : 'Ambito parziale: non confrontare i pasti previsti con il dispendio dell’intera giornata.'), element('p', 'Diario: ' + d.logged_slots + '/5 pasti dichiarati. Riposo Salute: ' + (d.health_coverage == null ? 'copertura assente' : fmt0(d.health_coverage * 100) + '% di copertura') + '.'), element('p', d.balance ? 'Saldo registrato: ' + energyRangeText(d.balance) + ' kcal.' : 'Saldo giornaliero non disponibile: dati incompleti.'));
        if(d.forecast_recorded_at)detail.append(element('p','Scenari conservati dal piano applicato il '+new Date(d.forecast_recorded_at*1000).toLocaleString('it-IT')+'.','muted small'));
        const open = element('button', 'Apri i pasti di questo giorno', 'secondary'); open.type = 'button'; open.onclick = () => { homeDate = d.date; document.querySelector('[data-page=home]').click(); history.replaceState(null, '', '#oggi?data=' + d.date); }; detail.append(open);
      }; days.append(b); }); table.append(days);
    }
    versions.onchange = render;
    box.append(versions, charts, element('p', 'Assunzione: linea continua e punti tondi. Dispendio: linea tratteggiata e punti quadrati. Intervalli verticali; nessuna linea attraversa dati mancanti. Un punto registrato può essere parziale: consulta la copertura.', 'muted small'), detail, table);
    render();
  } catch (e) { if (request === energyRequest) dashboardError(box, e, loadEnergy); }
  finally { if (request === energyRequest) box.removeAttribute('aria-busy'); }
}
function energyChart(rows, registered) {
  const box = element('article', undefined, 'energy-chart'); box.append(element('h3', registered ? 'Giorni registrati · kcal' : 'Settimana prevista · kcal'));
  const intake = rows.map(d => registered ? d.registered_intake : d.planned_intake), expenditure = rows.map(d => registered ? (d.health_expenditure == null ? null : { min: d.health_expenditure, max: d.health_expenditure }) : (d.planned_expenditure ? { min: d.planned_expenditure.low, max: d.planned_expenditure.high } : null));
  const values = intake.concat(expenditure).filter(Boolean);
  if (!values.length) { box.append(element('p', registered ? 'Registra i pasti o importa Salute per iniziare il confronto.' : 'Applica una settimana. Il dispendio previsto richiede scenari energetici disponibili.', 'muted')); return box; }
  const W = 340, H = 220, top = 12, bottom = 185, max = Math.max(500, ...values.map(v => v.max)) * 1.08;
  const x = i => 42 + i * 46, y = v => bottom - v / max * (bottom - top);
  const chart = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': registered ? 'Energia dichiarata e stimata da Salute: valori nella tabella sottostante' : 'Energia del piano: valori nella tabella sottostante' }, 'chart-svg');
  for (let i = 0; i <= 4; i++) { const value = max * i / 4; chart.append(svg('line', { x1: 40, x2: 326, y1: y(value), y2: y(value) }, 'grid-line')); const text = svg('text', { x: 36, y: y(value) + 4, 'text-anchor': 'end' }, 'axis-label'); text.textContent = fmt0(value); chart.append(text); }
  [intake, expenditure].forEach((series, s) => { let previous = null; series.forEach((v, i) => {
    if (!v) { previous = null; return; } const center = (v.min + v.max) / 2, cls = s ? 'energy-expenditure' : 'energy-intake';
    if (previous) chart.append(svg('line', { x1: previous.x, y1: previous.y, x2: x(i), y2: y(center), 'stroke-dasharray': s ? '5 4' : '' }, cls));
    if (v.min !== v.max) chart.append(svg('line', { x1: x(i), x2: x(i), y1: y(v.min), y2: y(v.max) }, cls + ' energy-interval'));
    const dot = svg(s ? 'rect' : 'circle', s ? { x: x(i) - 3, y: y(center) - 3, width: 6, height: 6 } : { cx: x(i), cy: y(center), r: 3 }, cls); const title = svg('title'); title.textContent = shortDate(rows[i].date) + ': ' + energyRangeText(v) + ' kcal'; dot.append(title); chart.append(dot); previous = { x: x(i), y: y(center) };
  }); });
  rows.forEach((d, i) => { const text = svg('text', { x: x(i), y: 207, 'text-anchor': 'middle' }, 'axis-label'); text.textContent = d.date.slice(8); chart.append(text); }); box.append(chart); return box;
}
async function loadMilestones() {
  try { milestoneData = await api('progress/milestones'); renderMilestones(); if(progressChartData)renderWeightChart(progressChartData); }
  catch (e) { dashboardError($('milestone-progress'), e, loadMilestones); }
}
function renderMilestones() {
  const box = $('milestone-progress'); box.replaceChildren();
  if (!milestoneData.rows.length) box.append(element('p', 'Aggiungi il primo traguardo dal Profilo. Il piano conserva gli obiettivi calorici che hai scelto.', 'muted'));
  milestoneData.rows.forEach((r, index) => {
    const card = element('article', undefined, 'milestone-card' + (r.active ? ' active' : ''));
    card.append(element('h3', (index + 1) + ' · ' + milestoneLabels[r.metric] + ' ' + (r.comparison === 'at_most' ? '≤ ' : '≥ ') + r.target + ' ' + milestoneUnits[r.metric]), element('p', r.active ? 'Traguardo attivo · guida il prossimo piano' : r.state === 'achieved' ? 'Completato con conferma' : r.state === 'skipped' ? 'Saltato con conferma' : 'Successivo'));
    if (r.evidence.value != null) card.append(element('p', 'Ultimo valore: ' + kgText(r.evidence.value) + ' ' + milestoneUnits[r.metric] + ' · distanza ' + kgText(Math.abs(r.target - r.evidence.value)) + '.'));
    card.append(element('p', r.evidence.rule + '.', 'muted small'));
    if(r.active && r.metric!=='sessions_per_week'){const out=element('div');const ask=element('button','Valuta il bilancio per questo traguardo','secondary small');ask.type='button';ask.onclick=async()=>{ask.disabled=true;try{const result=await api('goals/energy-proposal','POST',{});out.replaceChildren(result.status==='available'?energyProposalCard(result.proposal,out):element('p',result.reason,'notice'));}catch(error){out.replaceChildren(element('p',dashboardErrorText(error),'notice'));}finally{ask.disabled=false;}};if(milestoneData.balance_proposal)out.append(energyProposalCard(milestoneData.balance_proposal,out));card.append(ask,out);}
    if (r.desired_date) card.append(element('p', 'Data desiderata: ' + longDate(r.desired_date), 'muted'));
    const p = r.projection;
    if (p.status === 'available') {
      card.append(element('p', 'Se continui con questo andamento: ' + parseDate(p.earliest).toLocaleDateString('it-IT') + ' – ' + parseDate(p.latest).toLocaleDateString('it-IT') + '.', 'headline'), element('p', 'Aggiornamento ' + shortDate(p.updated_on) + ' · ' + p.days + ' giorni di pesata. ' + p.note, 'muted small'));
      if (p.previous?.status === 'available') { const shift = Math.round((parseDate(p.latest) - parseDate(p.previous.latest)) / 86400000); if (shift) card.append(element('p', 'La fine della finestra è ' + Math.abs(shift) + ' giorni ' + (shift < 0 ? 'prima' : 'dopo') + ' rispetto alla stima precedente.')); }
    } else card.append(element('p', 'Data non ancora stimabile. ' + p.reason, 'muted small'));
    if (r.state === 'pending' && r.evidence.reached) {
      const earlier = milestoneData.items.slice(0, index).filter(i => i.state === 'pending');
      const decision = element('details'); decision.open = r.prompt; decision.append(element('summary', r.prompt ? 'Raggiungimento da confermare' : 'Rivedi il raggiungimento'));
      decision.append(element('p', earlier.length ? 'Confermando, salterai i traguardi ' + milestoneData.items.slice(0, index).map((i, n) => i.state === 'pending' ? String(n + 1) : null).filter(Boolean).join(', ') + ' e completerai il ' + (index + 1) + '. Il primo successivo ancora da perseguire guiderà il nuovo piano. Piani e calorie approvate restano come sono.' : 'Conferma questo traguardo per attivare il primo successivo ancora da perseguire.'));
      const actions = element('div', undefined, 'actions');
      [[earlier.length ? 'skip_previous' : 'complete', earlier.length ? 'Salta e prosegui' : 'Conferma completamento'], ['keep', 'Mantieni l’ordine'], ['later', 'Decidi più tardi']].forEach(([action, label]) => { const b = element('button', label, action === 'complete' || action === 'skip_previous' ? 'primary' : 'ghost'); b.type = 'button'; b.onclick = async () => { b.disabled = true; try { await api('progress/milestones/decide', 'POST', { id: r.id, revision: milestoneData.revision, evidence_token: r.evidence.token, action }); await loadMilestones(); } catch (e) { b.disabled = false; decision.append(element('p', dashboardErrorText(e), 'notice')); } }; actions.append(b); }); decision.append(actions); card.append(decision);
    }
    box.append(card);
  });
  renderMilestoneEditor();
  const active = milestoneData.active;
  $('planning-milestone').textContent = active ? 'Traguardo attivo: ' + milestoneLabels[active.metric] + ' ' + active.target + ' ' + milestoneUnits[active.metric] + (active.metric === 'sessions_per_week' ? ' · imposta il minimo di sessioni per i nuovi piani di attività.' : ' · monitorato nelle misure; gli obiettivi calorici richiedono una proposta e approvazione esplicita.') : 'Nessun traguardo attivo. Puoi organizzare la sequenza nel Profilo.';
}
function renderMilestoneEditor() {
  const box = $('milestone-editor'); box.replaceChildren();
  let items = structuredClone(milestoneData.items);
  const list = element('div'), status = element('p'); status.setAttribute('role', 'status');
  function rows() {
    list.replaceChildren(); items.forEach((item, n) => {
      const row = element('div', undefined, 'milestone-edit-row'); row.append(element('strong', String(n + 1)));
      const metric = element('select'); metric.setAttribute('aria-label', 'Metrica del traguardo ' + (n + 1)); Object.entries(milestoneLabels).forEach(([v, label]) => metric.append(new Option(label, v))); metric.value = item.metric;
      const target = element('input'); target.type = 'number'; target.step = '0.1'; target.value = item.target; target.setAttribute('aria-label', 'Valore del traguardo ' + (n + 1));
      const direction = element('select'); direction.setAttribute('aria-label', 'Direzione del traguardo ' + (n + 1)); direction.append(new Option('Al massimo', 'at_most'), new Option('Almeno', 'at_least')); direction.value = item.comparison;
      const date = element('input'); date.type = 'date'; date.value = item.desired_date || ''; date.setAttribute('aria-label', 'Data desiderata del traguardo ' + (n + 1));
      const window = element('input'); window.type = 'number'; window.min = '1'; window.max = '52'; window.value = item.window_weeks; window.setAttribute('aria-label', 'Settimane consecutive del traguardo ' + (n + 1)); window.hidden = item.metric !== 'sessions_per_week';
      const done = item.state !== 'pending'; [metric, target, direction, date, window].forEach(c => c.disabled = done);
      metric.onchange = () => { item.metric = metric.value; item.target = item.metric === 'weight_kg' ? 70 : item.metric === 'body_fat_pct' ? 20 : 3; item.window_weeks = 1; if (item.metric === 'sessions_per_week') item.comparison = 'at_least'; rows(); }; target.oninput = () => item.target = Number(target.value); direction.onchange = () => item.comparison = direction.value; date.onchange = () => item.desired_date = date.value || null; window.oninput = () => item.window_weeks = Number(window.value);
      row.append(metric, target, direction, date, window);
      if (!done) { const up = element('button', '↑', 'ghost'); up.type = 'button'; up.disabled = n === 0; up.setAttribute('aria-label', 'Sposta prima il traguardo ' + (n + 1)); up.onclick = () => { [items[n - 1], items[n]] = [items[n], items[n - 1]]; rows(); }; const remove = element('button', 'Rimuovi', 'ghost'); remove.type = 'button'; remove.onclick = () => { items.splice(n, 1); rows(); }; row.append(up, remove); } else row.append(element('span', item.state === 'achieved' ? 'Completato' : 'Saltato', 'chip'));
      list.append(row);
    });
  }
  rows();
  const add = element('button', 'Aggiungi traguardo', 'secondary'); add.type = 'button'; add.onclick = () => { if (items.length >= 30) return; items.push({ id: crypto.randomUUID(), metric: 'weight_kg', target: 70, comparison: 'at_most', state: 'pending', desired_date: null, window_weeks: 1 }); rows(); };
  const save = element('button', 'Salva sequenza', 'primary'); save.type = 'button'; save.onclick = async () => { save.disabled = true; try { await api('progress/milestones', 'PUT', { revision: milestoneData.revision, items }); await loadMilestones(); $('milestone-editor').append(element('p', 'Sequenza salvata. Il primo traguardo aperto guida le nuove generazioni.', 'notice')); } catch (e) { status.textContent = dashboardErrorText(e); if (e.status === 409) { const reload = element('button', 'Ricarica sequenza', 'secondary'); reload.type = 'button'; reload.onclick = loadMilestones; box.append(reload); } } finally { save.disabled = false; } };
  box.append(element('p', 'Un criterio per traguardo. L’ordine determina quello attivo; modificare la sequenza rende obsolete le bozze precedenti. Per le sessioni, indica quante settimane consecutive devono raggiungere il minimo.', 'muted small'), list, add, save, status);
}
$('energy-start').value = mondayOf(isoDate(new Date()));
$('energy-start').onchange = () => { if($('energy-start').value){history.replaceState(null,'','#progressi?data='+$('energy-start').value);loadEnergy();} };
const originalLoadProgressDashboard = loadProgress;
loadProgress = async function () { await Promise.allSettled([originalLoadProgressDashboard(), loadEnergy(), loadMilestones()]); };
const originalLoadGoalsDashboard = loadGoals;
loadGoals = async function (...args) { const result = await originalLoadGoalsDashboard(...args); await loadMilestones(); return result; };
document.querySelector('[data-page=planning]').addEventListener('click', loadMilestones);

function recipeWeekAction(recipe) {
  const details = element('details'); details.append(element('summary', 'Fissa in un pasto futuro'));
  const form = element('form', undefined, 'controls');
  const dateLabel = element('label', 'Giorno'), date = element('input'); date.type = 'date'; date.min = addDays(isoDate(new Date()), 1); date.required = true; dateLabel.append(date);
  const slotLabel = element('label', 'Pasto'), slot = element('select'); slot.append(new Option('Pranzo', 'lunch'), new Option('Cena', 'dinner')); slotLabel.append(slot);
  const portionsLabel = element('label', 'Porzioni'), portions = element('input'); portions.type = 'number'; portions.min = '1'; portions.max = '4'; portions.step = '1'; portions.value = '1'; portionsLabel.append(portions);
  const submit = element('button', 'Fissa per la prossima generazione', 'primary'); submit.type = 'submit';
  const status = element('p'); status.setAttribute('role', 'status'); form.append(dateLabel, slotLabel, portionsLabel, submit);
  form.onsubmit = async e => { e.preventDefault(); submit.disabled = true; try { const week = mondayOf(date.value); await api('week/' + week + '/locked-dishes', 'PUT', { date: date.value, slot: slot.value, recipe: { id: recipe.id, portions: Number(portions.value) } }); status.replaceChildren(element('span', 'Piatto fissato. Genera una nuova bozza per inserirlo nel piano. ')); const open = element('button', 'Apri la settimana', 'secondary'); open.type = 'button'; open.onclick = async () => { const button = document.querySelector('[data-page=planning]'); await button.onclick(); await restorePlanningContext(new URLSearchParams({ data: week })); history.replaceState(null, '', '#settimana?data=' + week); }; status.append(open); } catch (error) { status.textContent = dashboardErrorText(error); } finally { submit.disabled = false; } };
  details.append(form, status); return details;
}

const originalPlanningWeekDashboard = loadPlanningWeek;
loadPlanningWeek = async function () {
  await originalPlanningWeekDashboard();
  const start = $('week-start').value, panel = $('active-week').querySelector('.active-week-panel');
  if (!panel) return;
  try {
    const data = await api('progress/energy?start=' + start);
    if (start !== $('week-start').value || !panel.isConnected) return;
    const details = element('details'); details.append(element('summary', 'Energia prevista della settimana'), energyChart(data.days, false));
    details.append(element('p', 'Il previsto riguarda i pasti applicati nell’ambito indicato. Il dispendio richiede scenari disponibili; i valori mancanti restano vuoti.', 'muted small'));
    const open = element('button', 'Confronta con diario e Salute', 'secondary'); open.type = 'button'; open.onclick = async () => { $('energy-start').value = start; await document.querySelector('[data-page=progress]').onclick(); }; details.append(open); panel.append(details);
  } catch (e) { panel.append(element('p', 'Energia non disponibile: ' + e.message, 'muted small')); }
};

const originalRestoreDashboard = restoreAppRoute;
restoreAppRoute = async function(hash = location.hash) {
  const [route, query = ''] = hash.slice(1).split('?'), date = new URLSearchParams(query).get('data');
  if(route === 'progressi' && date && /^\d{4}-\d{2}-\d{2}$/.test(date)) $('energy-start').value = date;
  await originalRestoreDashboard(hash);
  if(route === 'progressi' && date) await loadEnergy();
};

function candidateEnergy(plan) {
  const rows=(plan.days||[]).map(d=>({date:d.date,planned_intake:d.nutrient_ranges?.kcal||(Number.isFinite(d.nutrients?.kcal)?{min:d.nutrients.kcal,max:d.nutrients.kcal}:null),planned_expenditure:d.energy_scenarios?.status==='available'?d.energy_scenarios.consumption_kcal:null}));
  const details=element('details');details.append(element('summary','Energia prevista di questa proposta'),element('p','Bozza: questi pasti non sono ancora applicati. Ambito della proposta; i soli pasti principali non coprono l’intera giornata.','muted small'),energyChart(rows,false));
  details.append(healthTable(['Giorno','Assunzione prevista kcal','Dispendio previsto kcal'],rows.map(d=>[shortDate(d.date),energyRangeText(d.planned_intake),d.planned_expenditure?fmt0(d.planned_expenditure.central):'—'])));return details;
}

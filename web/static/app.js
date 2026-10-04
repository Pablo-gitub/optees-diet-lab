let csrf = '',
  profile = null,
  plans = [],
  cuisineOptions = [],
  recipeOffset = 0,
  recipeSolverData = null,
  recipeDietData = null,
  recipeDietRequest = 0;
const $ = (id) => document.getElementById(id);
const nutrients = [
  ['kcal_100g', 'Energia (kcal)'],
  ['protein_g_100g', 'Proteine (g)'],
  ['fat_g_100g', 'Grassi (g)'],
  ['carbs_available_g_100g', 'Carboidrati (g)'],
];
function message(text) {
  $('message').textContent = text;
  $('message').hidden = false;
  setTimeout(() => ($('message').hidden = true), 7000);
}
async function api(path, method = 'GET', data) {
  const response = await fetch('/api/' + path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const value = await response.json();
  if (!response.ok) throw Error(typeof value.detail === 'string' ? value.detail : 'Richiesta non valida');
  return value;
}
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function modes() {
  return profile.personal_diets
    ? [
        ['sedentary', 'Dieta sedentaria'],
        ['training', 'Dieta palestra'],
        ['free', 'Algoritmo libero'],
      ]
    : [['free', 'Algoritmo libero']];
}
function fillModes(id) {
  $(id).replaceChildren(
    ...modes().map(([value, label]) => {
      const o = element('option', label);
      o.value = value;
      return o;
    }),
  );
  $(id).value = profile.mode;
}
function targetFields() {
  const target = $('targets');
  target.replaceChildren();
  const head = element('div', undefined, 'target-row');
  ['Nutriente', 'Minimo', 'Bersaglio', 'Massimo'].forEach((x) => head.append(element('span', x)));
  target.append(head);
  nutrients.forEach(([key, label]) => {
    const row = element('div', undefined, 'target-row');
    row.append(element('span', label));
    ['min', 'target', 'max'].forEach((k) => {
      const input = element('input');
      input.type = 'number';
      input.step = 'any';
      input.min = 0;
      input.id = key + '-' + k;
      input.value = profile.targets[key][k];
      input.required = true;
      input.setAttribute('aria-label', label + ' ' + k);
      row.append(input);
    });
    target.append(row);
  });
  const local = $('local-targets');
  local.replaceChildren();
  ['lunch', 'dinner'].forEach((meal) => {
    local.append(element('h3', meal === 'lunch' ? 'Pranzo' : 'Cena'));
    nutrients.forEach(([key, label]) => {
      const row = element('div', undefined, 'target-row');
      row.append(element('span', label));
      ['min', 'max'].forEach((k) => {
        const input = element('input');
        input.type = 'number';
        input.step = 'any';
        input.min = 0;
        input.id = meal + '-' + key + '-' + k;
        input.placeholder = k === 'min' ? 'Minimo' : 'Massimo';
        input.value = profile.meal_targets[meal]?.[key]?.[k] ?? '';
        input.setAttribute('aria-label', meal + ' ' + label + ' ' + k);
        row.append(input);
      });
      local.append(row);
    });
  });
}
async function load() {
  recipeDietData = null;
  if ($('recipe-diet-mode')) {
    $('recipe-diet-mode').replaceChildren();
    $('recipe-diet-day').replaceChildren();
    $('recipe-diet-options').replaceChildren();
  }
  recipeSolverData = null;
  const data = await api('profile');
  csrf = data.csrf;
  profile = data.profile;
  $('login').hidden = true;
  $('workspace').hidden = false;
  $('user-name').textContent = profile.display_name;
  $('user-initial').textContent = (profile.display_name || '?').trim().charAt(0);
  $('display-name').value = profile.display_name;
  $('preferences').value = profile.preference_note.replace('Preferenze registrate, non ancora applicate ai calcoli.','Preferenze di colazione e spuntini applicate quando il bilancio giornaliero è attivo.');
  $('demo').checked = profile.targets_demo;
  $('exclusions').value = profile.excluded_crea_ids.join(', ');
  fillModes('profile-mode');
  fillModes('planning-mode');
  targetFields();
  dailyFields();
  await loadCuisines();
  await loadPlans();
}
async function loadPlans() {
  plans = await api('plans');
  renderPlans();
}
const mealMeta = {
  breakfast: ['Colazione', '☕'],
  morning_snack: ['Metà mattina', '🍎'],
  lunch: ['Pranzo', '🍝'],
  afternoon_snack: ['Metà pomeriggio', '🍌'],
  dinner: ['Cena', '🍽️'],
};
const macroMeta = [
  ['kcal', 'Energia', 'kcal'],
  ['protein_g', 'Proteine', 'g'],
  ['carbs_available_g', 'Carboidrati', 'g'],
  ['fat_g', 'Grassi', 'g'],
];
const fmt0 = (value) => Math.round(value).toLocaleString('it-IT');
const percent = (value) => Math.max(0, Math.min(100, value * 100)) + '%';
function foodSource(f) {
  if (f.source === 'user_label') return ['tua etichetta', 'src src-user'];
  if (f.source === 'Open Food Facts') return ['marca', 'src src-brand'];
  return null;
}
const foodKey = (f) => f.meal + '|' + (f.crea_id || f.id || f.food);
function meter(label, unit, value, check) {
  const wrap = element('div', undefined, 'meter');
  const head = element('div', undefined, 'meter-head');
  const shown = element('span', fmt0(value) + ' ' + unit, 'meter-value');
  if (check?.target != null) shown.append(element('em', ' / ' + fmt0(check.target)));
  head.append(element('span', label, 'meter-label'), shown);
  wrap.append(head);
  if (check) {
    const scale = Math.max(check.max, value) * 1.08 || 1;
    const track = element('div', undefined, 'meter-track');
    const range = element('span', undefined, 'meter-range');
    range.style.left = percent(check.min / scale);
    range.style.width = percent((check.max - check.min) / scale);
    const fill = element('span', undefined, 'meter-fill' + (check.respected ? '' : ' out'));
    fill.style.width = percent(value / scale);
    track.append(range, fill);
    if (check.target != null) {
      const tick = element('span', undefined, 'meter-target');
      tick.style.left = percent(check.target / scale);
      track.append(tick);
    }
    track.title = 'Limiti ' + fmt0(check.min) + '–' + fmt0(check.max) + ' ' + unit + (check.target != null ? ' · bersaglio ' + fmt0(check.target) : '');
    wrap.append(track);
    if (!check.respected) wrap.append(element('div', '⚠ Fuori dai limiti ' + fmt0(check.min) + '–' + fmt0(check.max) + ' ' + unit, 'meter-out'));
  }
  return wrap;
}
function technicalDetails(p) {
  const details = element('details', undefined, 'tech');
  details.append(element('summary', 'Dettagli tecnici'));
  const opt = p.optimization;
  if (opt) {
    const names = { balanced: 'Bilanciato', pareto: 'Pareto · campione di compromessi', minmax: 'Min-Max', maxmin: 'Max-Min' };
    details.append(element('p', 'Metodo: ' + names[opt.strategy] + (opt.requested === 'bandit' ? ' · suggerito dal bandit (' + (opt.bandit_reason === 'exploration' ? 'esplorazione' : 'UCB1') + ')' : ''), 'muted'));
    if (opt.relative_errors) {
      const labels = { kcal: 'Energia', protein_g: 'Proteine', fat_g: 'Grassi', carbs_available_g: 'Carboidrati' };
      details.append(element('p', 'Scarto relativo peggiore: ' + (100 * opt.worst_relative_error).toFixed(1) + '% · Soddisfazione minima: ' + (100 * opt.minimum_satisfaction).toFixed(1) + '%', 'muted'));
      details.append(element('p', Object.entries(opt.relative_errors).map(([k, v]) => labels[k] + ': scarto ' + (100 * v).toFixed(1) + '%').join(' · '), 'muted'));
    }
    if (opt.strategy === 'pareto') details.append(element('p', 'Non dominata nel campione calcolato; la frontiera completa non è garantita.', 'muted'));
  }
  if (p.diet_note) details.append(element('p', p.diet_note, 'muted'));
  (p.preference_changes || []).forEach((note) => details.append(element('p', note, 'muted')));
  const report = p.constraint_report;
  if (report) {
    details.append(element('p', 'Porzioni, confezioni intere e scelte alimentari del modello verificate. Il bersaglio è un obiettivo: minimo e massimo sono i limiti obbligatori.', 'muted'));
    const scroll = element('div', undefined, 'table-scroll');
    const table = element('table');
    const heading = element('tr');
    ['Ambito / nutriente', 'Risultato', 'Limiti', 'Bersaglio', 'Esito'].forEach((t) => heading.append(element('th', t)));
    const thead = element('thead');
    thead.append(heading);
    table.append(thead);
    const body = element('tbody');
    const labels = { kcal: 'Energia', protein_g: 'Proteine', carbs_available_g: 'Carboidrati', fat_g: 'Grassi' };
    const scopes = { day: p.scope === 'full_day_planned_meals' ? 'Giornata' : 'Pranzo + cena', ...Object.fromEntries(Object.entries(mealMeta).map(([k, v]) => [k, v[0]])) };
    const number = (value) => value.toLocaleString('it-IT', { maximumFractionDigits: 2 });
    report.checks.forEach((c) => {
      const unit = c.nutrient === 'kcal' ? ' kcal' : ' g';
      const row = element('tr');
      [scopes[c.meal] + ' · ' + labels[c.nutrient], number(c.actual) + unit, number(c.min) + '–' + number(c.max) + unit, c.target == null ? '—' : number(c.target) + unit, c.respected ? '✓' : 'Fuori limite'].forEach((t) => row.append(element('td', t)));
      body.append(row);
    });
    table.append(body);
    scroll.append(table);
    details.append(scroll, element('p', report.rounding_note, 'muted'));
  } else details.append(element('p', 'Storico: dettaglio dei vincoli non disponibile. Genera nuove alternative per visualizzarlo.', 'muted'));
  return details;
}
function ratingControl(entry) {
  const box = element('div', undefined, 'feedback');
  box.append(element('span', entry.feedback == null ? 'L’hai provato? Valutalo' : 'La tua valutazione', 'feedback-label'));
  const stars = element('div', undefined, 'stars');
  stars.setAttribute('role', 'group');
  stars.setAttribute('aria-label', 'Valutazione del piano provato');
  for (let i = 1; i <= 5; i++) {
    const star = element('button', '★', 'star' + (entry.feedback >= i ? ' on' : ''));
    star.type = 'button';
    star.title = 'L’ho provato · ' + i + ' su 5';
    star.setAttribute('aria-label', 'L’ho provato, voto ' + i + ' su 5');
    star.onclick = async () => {
      try {
        await api('plans/' + entry.id + '/feedback', 'POST', { tried: true, rating: i });
        await loadPlans();
        message('Valutazione salvata: ' + i + ' su 5');
      } catch (e) {
        message(e.message);
      }
    };
    stars.append(star);
  }
  box.append(stars);
  return box;
}
function renderPlans() {
  const day = Number($('day').value),
    mode = $('planning-mode').value;
  const visible = plans.filter((x) => x.plan.day_index === day && x.plan.mode === mode);
  $('plans').replaceChildren();
  $('empty').hidden = visible.length > 0;
  const solved = visible.filter((x) => ['optimal', 'feasible'].includes(x.plan.status));
  // Highlight foods that are not shared by every solved alternative.
  const counts = {};
  solved.forEach((x) => new Set(x.plan.selections.map(foodKey)).forEach((k) => (counts[k] = (counts[k] || 0) + 1)));
  const compare = solved.length > 1;
  $('count').replaceChildren();
  if (visible.length) {
    $('count').append(document.createTextNode(visible.length + (visible.length === 1 ? ' alternativa' : ' alternative')));
    if (compare) $('count').append(document.createTextNode(' · '), element('span', 'cosa cambia', 'legend-varies'));
  }
  visible.forEach((entry, index) => {
    const p = entry.plan;
    const card = element('article', undefined, 'card' + (entry.selected ? ' selected' : ''));
    const header = element('div', undefined, 'card-header');
    header.append(element('h3', 'Alternativa ' + (index + 1)), element('span', entry.selected ? '✓ Scelta' : p.demo ? 'Demo' : 'Configurata', 'tag' + (entry.selected ? ' is-selected' : '')));
    card.append(header);
    if (!['optimal', 'feasible'].includes(p.status)) {
      card.append(element('p', 'Nessuna soluzione nel sottoinsieme modellato con questi vincoli. Questo non prova che la dieta completa sia impossibile.', 'error'));
      $('plans').append(card);
      return;
    }
    const checks = Object.fromEntries((p.constraint_report?.checks || []).filter((c) => c.meal === 'day').map((c) => [c.nutrient, c]));
    const hero = element('div', undefined, 'plan-hero');
    const left = element('div');
    const kcal = element('div', fmt0(p.nutrients.kcal), 'hero-kcal');
    kcal.append(element('small', 'kcal'));
    left.append(kcal, element('div', p.scope === 'full_day_planned_meals' ? 'Totale della giornata pianificata' : 'Totale di pranzo + cena', 'hero-caption'));
    hero.append(left);
    const report = p.constraint_report;
    if (report) hero.append(element('span', report.verified && report.all_respected ? '✓ Vincoli rispettati' : '⚠ Vincoli da controllare', 'status' + (report.all_respected ? '' : ' bad')));
    card.append(hero);
    const meters = element('div', undefined, 'meters');
    macroMeta.forEach(([key, label, unit]) => meters.append(meter(label, unit, p.nutrients[key], checks[key])));
    card.append(meters);
    const meals = p.scope === 'full_day_planned_meals' ? ['breakfast', 'morning_snack', 'lunch', 'afternoon_snack', 'dinner'] : ['lunch', 'dinner'];
    meals.forEach((meal) => {
      const slot = p.slots[meal];
      const block = element('div', undefined, 'meal');
      const head = element('div', undefined, 'meal-head');
      head.append(element('span', mealMeta[meal][1], 'meal-icon'), element('h4', mealMeta[meal][0]));
      if (slot === 'personalized_habits') head.append(element('span', 'abitudini', 'chip'));
      else if (slot === 'not_planned') head.append(element('span', 'non pianificato', 'chip'));
      else if (slot) head.append(element('span', 'schema ' + slot, 'chip'));
      const mealNutrients = p.nutrients_by_meal?.[meal];
      if (mealNutrients && slot !== 'not_planned') head.append(element('span', fmt0(mealNutrients.kcal) + ' kcal', 'meal-kcal'));
      block.append(head);
      p.selections
        .filter((f) => f.meal === meal)
        .forEach((f) => {
          const row = element('div', undefined, 'food' + (compare && counts[foodKey(f)] < solved.length ? ' varies' : ''));
          const name = element('span', f.food.replace(/,\s*/g, ', '), 'food-name');
          const source = foodSource(f);
          if (source) name.append(element('span', source[0], source[1]));
          const amount = element('span', fmt0(f.grams) + ' g', 'food-grams');
          if (f.units) amount.append(element('small', ' · ' + f.units + ' conf.'));
          row.append(name, amount);
          block.append(row);
        });
      if (mealNutrients && slot !== 'not_planned')
        block.append(element('p', 'P ' + fmt0(mealNutrients.protein_g) + ' g · C ' + fmt0(mealNutrients.carbs_available_g) + ' g · G ' + fmt0(mealNutrients.fat_g) + ' g', 'meal-macros'));
      card.append(block);
    });
    card.append(technicalDetails(p), ratingControl(entry));
    const button = element('button', entry.selected ? '✓ Piano scelto' : 'Scegli questo piano', 'card-cta ' + (entry.selected ? 'secondary' : 'primary'));
    button.disabled = entry.selected;
    button.onclick = async () => {
      try {
        await api('plans/' + entry.id + '/select', 'POST', {});
        await loadPlans();
        message('Piano scelto per questa giornata');
      } catch (e) {
        message(e.message);
      }
    };
    card.append(button);
    $('plans').append(card);
  });
}
async function save() {
  const targets = {};
  nutrients.forEach(([key]) => {
    targets[key] = {};
    ['min', 'target', 'max'].forEach((k) => (targets[key][k] = Number($(key + '-' + k).value)));
  });
  const meal_targets = {};
  for (const meal of ['lunch', 'dinner'])
    for (const [key] of nutrients) {
      const a = $(meal + '-' + key + '-min').value,
        b = $(meal + '-' + key + '-max').value;
      if (a !== '' || b !== '') {
        if (a === '' || b === '') throw Error('Inserisci entrambi i limiti del pasto');
        meal_targets[meal] ??= {};
        meal_targets[meal][key] = { min: Number(a), max: Number(b) };
      }
    }
  await api('profile', 'PUT', {
    display_name: $('display-name').value,
    mode: $('profile-mode').value,
    preference_note: $('preferences').value,
    targets,
    meal_targets,
    excluded_crea_ids: $('exclusions')
      .value.split(',')
      .map((x) => x.trim())
      .filter(Boolean),
    targets_demo: $('demo').checked,
    daily_meals:readDailyFields(),
    preferred_cuisines: [...document.querySelectorAll('#cuisine-preferences input:checked')].map((x) => x.value),
  });
  await load();
}
$('login-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    const data = await api('login', 'POST', { username: $('username').value, password: $('password').value });
    csrf = data.csrf;
    $('password').value = '';
    await load();
  } catch (e) {
    message(e.message);
  }
};
$('register').onclick = async () => {
  try {
    await api('register', 'POST', { username: $('username').value, password: $('password').value });
    message('Profilo creato. Ora puoi accedere.');
  } catch (e) {
    message(e.message);
  }
};
$('logout').onclick = async () => {
  try {
    await api('logout', 'POST', {});
    location.reload();
  } catch (e) {
    message(e.message);
  }
};
$('profile-form').onsubmit = async (e) => {
  e.preventDefault();
  try {
    await save();
    message('Configurazione salvata');
  } catch (e) {
    message(e.message);
  }
};
$('planning-mode').onchange = renderPlans;
$('day').onchange = renderPlans;
$('generate').onclick = async () => {
  const button = $('generate');
  button.disabled = true;
  button.textContent = 'Optees sta calcolando…';
  try {
    if (profile.mode !== $('planning-mode').value) {
      await api('profile', 'PUT', { ...profile, mode: $('planning-mode').value });
      profile.mode = $('planning-mode').value;
      $('profile-mode').value = profile.mode;
    }
    const r = await api('generate', 'POST', { day_index: Number($('day').value), strategy:$('optimization-strategy').value });
    await loadPlans();
    message(r.count + ' alternative salvate');
  } catch (e) {
    message(e.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Genera alternative';
  }
};
const pageMeta = {
  planning: ['Dalle possibilità al piano', 'Pianificazione', 'Genera e confronta le alternative per una giornata.'],
  recipes: ['Cucina', 'Ricette', 'Sfoglia il catalogo, controlla la compatibilità con la dieta, adatta un piatto.'],
  profile: ['Impostazioni', 'Il mio profilo', 'Obiettivi, abitudini e preferenze che guidano i calcoli.'],
  health: ['Dati personali', 'Salute', 'Misure e dispendio importati da Apple Salute.'],
};
document.querySelectorAll('[data-page]').forEach(
  (button) =>
    (button.onclick = () => {
      const page = button.dataset.page;
      ['profile', 'planning', 'recipes', 'health'].forEach((id) => ($(id).hidden = id !== page));
      document.querySelectorAll('[data-page]').forEach((b) => b.classList.toggle('active', b === button));
      const meta = pageMeta[page];
      $('page-eyebrow').textContent = meta[0];
      $('page-title').textContent = meta[1];
      $('page-subtitle').textContent = meta[2];
      window.scrollTo({ top: 0 });
      if (page === 'health') loadHealth().catch(e => message(e.message));
      if (page === 'recipes') Promise.all([loadRecipes(), loadRecipeSolver()]).catch((e) => message(e.message));
    }),
);
const names = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'];
for (let i = 0; i < 14; i++) {
  const option = element('option', names[i % 7] + ' · settimana ' + (Math.floor(i / 7) + 1));
  option.value = i;
  $('day').append(option);
}
load().catch(() => {});

const cuisineLabels = {
  'afghan': 'Afghana',
  'albanian': 'Albanese',
  'algerian': 'Algerina',
  'american': 'Americana',
  'argentinian': 'Argentina',
  'armenian': 'Armena',
  'australian': 'Australiana',
  'austrian': 'Austriaca',
  'azerbaijani': 'Azera',
  'belarusian': 'Bielorussa',
  'belgian': 'Belga',
  'bengali': 'Bengalese',
  'bhutanese': 'Bhutanese',
  'bolivian': 'Boliviana',
  'bosnian': 'Bosniaca',
  'brazilian': 'Brasiliana',
  'british': 'Britannica',
  'bulgarian': 'Bulgara',
  'burmese': 'Birmana',
  'cameroonian': 'Camerunese',
  'canadian': 'Canadese',
  'chilean': 'Cilena',
  'chinese': 'Cinese',
  'colombian': 'Colombiana',
  'congolese': 'Congolese',
  'costa-rican': 'Costaricana',
  'croatian': 'Croata',
  'cuban': 'Cubana',
  'cypriot': 'Cipriota',
  'czech': 'Ceca',
  'danish': 'Danese',
  'dominican': 'Dominicana',
  'dutch': 'Olandese',
  'east-asian': 'Asia orientale',
  'eastern-european': 'Europa orientale',
  'ecuadorian': 'Ecuadoriana',
  'egyptian': 'Egiziana',
  'emirati': 'Emiratina',
  'estonian': 'Estone',
  'ethiopian': 'Etiope',
  'filipino': 'Filippina',
  'finnish': 'Finlandese',
  'french': 'Francese',
  'georgian': 'Georgiana',
  'german': 'Tedesca',
  'ghanaian': 'Ghanese',
  'greek': 'Greca',
  'guatemalan': 'Guatemalteca',
  'honduran': 'Honduregna',
  'hungarian': 'Ungherese',
  'icelandic': 'Islandese',
  'indian': 'Indiana',
  'indonesian': 'Indonesiana',
  'iraqi': 'Irachena',
  'irish': 'Irlandese',
  'israeli': 'Israeliana',
  'italian': 'Italiana',
  'ivorian': 'Ivoriana',
  'jamaican': 'Giamaicana',
  'japanese': 'Giapponese',
  'jordanian': 'Giordana',
  'kazakh': 'Kazaka',
  'kenyan': 'Keniota',
  'khmer': 'Khmer',
  'korean': 'Coreana',
  'kosovar': 'Kosovara',
  'kuwaiti': 'Kuwaitiana',
  'kyrgyz': 'Kirghisa',
  'lao': 'Laotiana',
  'latvian': 'Lettone',
  'lebanese': 'Libanese',
  'lithuanian': 'Lituana',
  'luxembourgish': 'Lussemburghese',
  'macedonian': 'Macedone',
  'malagasy': 'Malgascia',
  'malaysian': 'Malese',
  'maldivian': 'Maldiviana',
  'malian': 'Maliana',
  'maltese': 'Maltese',
  'mediterranean': 'Mediterranea',
  'mexican': 'Messicana',
  'middle-eastern': 'Mediorientale',
  'modern-european': 'Europea moderna',
  'moldovan': 'Moldava',
  'mongolian': 'Mongola',
  'montenegrin': 'Montenegrina',
  'moroccan': 'Marocchina',
  'mozambican': 'Mozambicana',
  'nepali': 'Nepalese',
  'new-zealand': 'Neozelandese',
  'nicaraguan': 'Nicaraguense',
  'nigerian': 'Nigeriana',
  'north-indian': 'India del nord',
  'northern-european': 'Nord Europa',
  'norwegian': 'Norvegese',
  'omani': 'Omanita',
  'pakistani': 'Pakistana',
  'panamanian': 'Panamense',
  'paraguayan': 'Paraguaiana',
  'persian': 'Persiana',
  'peruvian': 'Peruviana',
  'polish': 'Polacca',
  'portuguese': 'Portoghese',
  'romanian': 'Rumena',
  'russian': 'Russa',
  'saudi': 'Saudita',
  'senegalese': 'Senegalese',
  'serbian': 'Serba',
  'singaporean': 'Singaporiana',
  'slovak': 'Slovacca',
  'slovenian': 'Slovena',
  'south-african': 'Sudafricana',
  'south-indian': 'India del sud',
  'southeast-asian': 'Sud-est asiatico',
  'spanish': 'Spagnola',
  'sri-lankan': 'Singalese',
  'sudanese': 'Sudanese',
  'swedish': 'Svedese',
  'swiss': 'Svizzera',
  'syrian': 'Siriana',
  'taiwanese': 'Taiwanese',
  'tajik': 'Tagika',
  'tanzanian': 'Tanzaniana',
  'thai': 'Thailandese',
  'trinidadian': 'Trinidadiana',
  'tunisian': 'Tunisina',
  'turkish': 'Turca',
  'turkmen': 'Turkmena',
  'ugandan': 'Ugandese',
  'ukrainian': 'Ucraina',
  'uruguayan': 'Uruguaiana',
  'uzbek': 'Uzbeka',
  'venezuelan': 'Venezuelana',
  'vietnamese': 'Vietnamita',
  'west-african': 'Africa occidentale',
  'yemeni': 'Yemenita',
  'zimbabwean': 'Zimbabwese',
};
async function loadCuisines() {
  cuisineOptions = (await api('cuisines')).sort((a, b) => (cuisineLabels[a.id] || a.name).localeCompare(cuisineLabels[b.id] || b.name, 'it'));
  $('cuisine-preferences').replaceChildren();
  $('recipe-cuisine').replaceChildren(element('option', 'Tutte le cucine'));
  $('recipe-cuisine').firstChild.value = '';
  cuisineOptions.forEach((c) => {
    const label = element('label', undefined, 'check');
    const input = element('input');
    input.type = 'checkbox';
    input.value = c.id;
    input.checked = (profile.preferred_cuisines || []).includes(c.id);
    label.append(input, element('span', (cuisineLabels[c.id] || c.name) + ' (' + c.count + ')'));
    $('cuisine-preferences').append(label);
    const option = element('option', (cuisineLabels[c.id] || c.name) + ' · ' + c.count);
    option.value = c.id;
    $('recipe-cuisine').append(option);
  });
}
const dishIcons = [
  [/pasta|spaghetti|noodle|lasagn|ravioli|gnocchi|mantu|dumpling|pierogi/i, '🍝'],
  [/rice|risotto|pilaf|plov|paella|biryani|pilau/i, '🍚'],
  [/soup|stew|broth|chowder|borscht|minestr|goulash/i, '🥣'],
  [/salad/i, '🥗'],
  [/curry|dal|dhal|masala/i, '🍛'],
  [/fish|salmon|cod|tuna|shrimp|prawn|saltfish|seafood/i, '🐟'],
  [/chicken|poultry|turkey/i, '🍗'],
  [/beef|lamb|pork|steak|meat|kebab|sausage/i, '🥩'],
  [/bread|flatbread|naan|pita|tortilla|arepa/i, '🥖'],
  [/cake|biscuit|cookie|tart|pie|pudding|strudel|alfajor|dessert|sweet|baklava/i, '🍰'],
  [/bean|lentil|chickpea|hummus|falafel/i, '🫘'],
  [/egg|omelet|frittata|shakshuka/i, '🍳'],
  [/oat|porridge|pancake/i, '🥞'],
];
const dishIcon = (title) => (dishIcons.find(([re]) => re.test(title)) || [null, '🍲'])[1];
const hash = (text) => [...(text || '')].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
async function loadRecipes() {
  const params = new URLSearchParams({
    q: $('recipe-search').value,
    cuisine: $('recipe-cuisine').value,
    preferred: $('only-preferred').checked,
    offset: recipeOffset,
  });
  const data = await api('recipes?' + params);
  $('recipe-count').textContent =
    data.total.toLocaleString('it-IT') +
    ' ricette · ' +
    (data.recipes.length ? recipeOffset + 1 : 0) +
    '–' +
    (recipeOffset + data.recipes.length);
  $('recipe-list').replaceChildren();
  data.recipes.forEach((r) => {
    const card = element('article', undefined, 'card recipe-card');
    if (r.illustrative_image) {
      const img = element('img', undefined, 'recipe-thumb');
      img.src = r.illustrative_image.thumbnail_url || r.illustrative_image.image_url;
      img.alt = r.title;
      img.loading = 'lazy';
      const attr = element('div', undefined, 'recipe-image-attribution');
      if (r.illustrative_image.author) attr.append(element('span', 'Foto: ' + r.illustrative_image.author + ' · '));
      const lic = element('a', r.illustrative_image.license || 'Commons');
      lic.href = r.illustrative_image.license_url || r.illustrative_image.source_page;
      lic.target = '_blank';
      lic.rel = 'noopener noreferrer';
      attr.append(lic, element('span', ' · '));
      const srcLink = element('a', 'Wikimedia Commons');
      srcLink.href = r.illustrative_image.source_page;
      srcLink.target = '_blank';
      srcLink.rel = 'noopener noreferrer';
      attr.append(srcLink, element('span', 'Foto illustrativa — ingredienti e porzioni possono differire.', 'disclaimer'));
      card.append(img, attr);
    } else card.append(element('div', dishIcon(r.title), 'recipe-placeholder tone-' + (hash(r.cuisine_id) % 4)));
    const body = element('div', undefined, 'recipe-body');
    body.append(element('h3', r.title), element('p', cuisineLabels[r.cuisine_id] || r.cuisine, 'muted'));
    const n = r.declared_nutrition;
    const facts = element('div', undefined, 'recipe-facts');
    [
      '⏱ ' + (r.total_minutes ?? '?') + ' min',
      r.servings + ' porzioni',
      (n.kcal ?? '?') + ' kcal/porz.',
      (n.protein_g ?? '?') + ' g proteine',
    ].forEach((text) => facts.append(element('span', text, 'chip')));
    body.append(facts);
    const details = element('details');
    details.append(element('summary', 'Ingredienti e procedimento'));
    r.ingredients.forEach((i) => {
      const mass = i.grams_whole_recipe === null ? 'peso da convertire' : i.grams_whole_recipe + ' g';
      details.append(element('p', i.name + ' — ' + (i.quantity ?? 'q.b.') + ' ' + i.unit + ' (' + mass + ')', 'muted'));
    });
    if (r.steps.length) {
      const steps = element('ol');
      r.steps.forEach((text) => steps.append(element('li', text)));
      details.append(steps);
    } else details.append(element('p', 'Procedimento disponibile nella pagina originale.', 'muted'));
    body.append(details);
    const link = element('a', r.source + ' · ' + r.license);
    if (r.source_url.startsWith('https://')) link.href = r.source_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    body.append(link, element('p', 'Abbinamento ingredienti da verificare.', 'muted small'));
    card.append(body);
    $('recipe-list').append(card);
  });
  $('recipe-prev').disabled = recipeOffset === 0;
  $('recipe-next').disabled = recipeOffset + 30 >= data.total;
}
$('search-recipes').onclick = () => {
  recipeOffset = 0;
  loadRecipes().catch((e) => message(e.message));
};
$('recipe-cuisine').onchange = $('search-recipes').onclick;
$('only-preferred').onchange = $('search-recipes').onclick;
$('recipe-prev').onclick = () => {
  recipeOffset = Math.max(0, recipeOffset - 30);
  loadRecipes().catch((e) => message(e.message));
};
$('recipe-next').onclick = () => {
  recipeOffset += 30;
  loadRecipes().catch((e) => message(e.message));
};

const recipeNutrients = [
  ['kcal', 'Energia (kcal)'],
  ['protein_g', 'Proteine (g)'],
  ['fat_g', 'Grassi (g)'],
  ['carbs_g', 'Carboidrati (g)'],
];
async function loadRecipeSolver() {
  if (!recipeSolverData) {
    recipeSolverData = await api('recipe-solver');
    $('solver-recipe').replaceChildren(
      ...recipeSolverData.recipes.map((r) => {
        const o = element('option', r.title);
        o.value = r.id;
        return o;
      }),
    );
    const fields = $('recipe-targets');
    const heading = element('div', undefined, 'target-row');
    ['Nutriente', 'Minimo', 'Bersaglio', 'Massimo'].forEach((t) => heading.append(element('span', t)));
    fields.replaceChildren(heading);
    recipeNutrients.forEach(([n, label]) => {
      const row = element('div', undefined, 'target-row');
      row.append(element('span', label));
      ['min', 'target', 'max'].forEach((k) => {
        const input = element('input');
        input.id = 'recipe-' + n + '-' + k;
        input.type = 'number';
        input.step = 'any';
        input.min = k === 'target' ? '0.000001' : '0';
        input.max = '10000';
        input.required = true;
        input.value = recipeSolverData.defaults.targets[n][k];
        input.setAttribute('aria-label', 'Ricetta ' + label + ' ' + k);
        row.append(input);
      });
      fields.append(row);
    });
    recipeProductFields();
    await loadRecipeDietOptions();
  }
  await loadRecipeHistory();
}
function recipeProductFields() {
  const r = recipeSolverData.recipes.find((r) => r.id === $('solver-recipe').value);
  $('recipe-mapping-note').textContent = r.reference_note;
  $('recipe-products').replaceChildren();
  r.ingredients.forEach((i) => {
    const block = element('div');
    block.append(
      element('strong', i.name + ' · riferimento ' + i.grams_per_reference_portion + ' g'),
      element('p', i.state, 'muted'),
    );
    i.candidates.forEach((c) => {
      const label = element('label', undefined, 'check');
      const input = element('input');
      input.type = 'checkbox';
      input.checked = true;
      input.value = c.source + ':' + c.id;
      input.dataset.recipeProduct = '1';
      label.append(
        input,
        element(
          'span',
          (c.label || c.source + ' · ' + c.id) +
            (c.source === 'CREA'
              ? ' · alimento generico — database italiano CREA (non è una marca)'
              : c.source === 'Open Food Facts'
                ? ' · prodotto di marca'
                : ''),
        ),
      );
      block.append(label);
    });
    $('recipe-products').append(block);
  });
}
function recipeResultCard(r) {
  const card = element('article', undefined, 'card');
  card.append(element('h3', r.title));
  if (!['optimal', 'feasible'].includes(r.status)) {
    card.append(
      element(
        'p',
        'Nessuna soluzione con questi intervalli e limiti di porzione. Prova a rivedere gli obiettivi o i prodotti disponibili.',
        'error',
      ),
    );
    return card;
  }
  card.append(
    element(
      'p',
      'Porzione: ' +
        r.portion_scale.toFixed(3) +
        ' × riferimento · flessibilità ±' +
        Math.round(r.flexibility * 100) +
        '%',
      'muted',
    ),
  );
  r.selections.forEach((i) => {
    const row = element('div', undefined, 'food');
    row.append(
      element('span', i.ingredient + ' — ' + i.food + (i.brands ? ' · ' + i.brands : '')),
      element('strong', i.grams.toLocaleString('it-IT') + ' g'),
    );
    card.append(
      row,
      element(
        'p',
        i.state +
          ' · scostamento proporzione ' +
          i.proportion_change_percent +
          '% · ' +
          (i.source === 'CREA'
            ? 'Valori generici · database italiano CREA (non è una marca)'
            : i.source === 'Open Food Facts'
              ? 'Valori del prodotto di marca · Open Food Facts'
              : i.source) +
          ' · codice ' +
          i.id,
        'muted',
      ),
    );
  });
  const metrics = element('div', undefined, 'metrics');
  recipeNutrients.forEach(([n, label]) => {
    const cell = element('div');
    cell.append(element('strong', r.nutrients[n].toFixed(1)), element('small', label));
    metrics.append(cell);
  });
  card.append(metrics, element('p', r.note, 'muted'));
  if (r.adaptation_notes?.length) {
    const details = element('details');
    details.append(element('summary', 'Sostituzioni rispetto alla ricetta originale'));
    r.adaptation_notes.forEach((note) => details.append(element('p', note, 'muted')));
    card.append(details);
  }
  if (r.source_url?.startsWith('https://')) {
    const link = element('a', 'Ricetta originale · ' + (r.license || 'fonte'));
    link.href = r.source_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    card.append(link);
  }
  return card;
}
async function loadRecipeHistory() {
  const runs = await api('recipe-runs');
  $('recipe-history').replaceChildren(...runs.map((r) => recipeResultCard(r.result)));
}
$('solver-recipe').onchange = () => {
  recipeProductFields();
  $('recipe-solution').replaceChildren();
};
$('recipe-solver-form').onsubmit = async (e) => {
  e.preventDefault();
  const button = $('optimize-recipe');
  button.disabled = true;
  button.textContent = 'Optees sta calcolando…';
  try {
    const targets = {};
    recipeNutrients.forEach(([n]) => {
      targets[n] = {};
      ['min', 'target', 'max'].forEach((k) => (targets[n][k] = Number($('recipe-' + n + '-' + k).value)));
    });
    const result = await api('recipe-optimize', 'POST', {
      recipe_id: $('solver-recipe').value,
      flexibility: Number($('recipe-flex').value) / 100,
      scale_min: Number($('recipe-scale-min').value),
      scale_max: Number($('recipe-scale-max').value),
      targets,
      disabled_products: [...document.querySelectorAll('[data-recipe-product]:not(:checked)')].map((x) => x.value),
    });
    $('recipe-solution').replaceChildren(recipeResultCard(result));
    await loadRecipeHistory();
  } catch (e) {
    message(e.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Ottimizza la ricetta';
  }
};

const dietGroupLabels = {
  pasta: 'pasta',
  rice: 'riso',
  bread: 'pane',
  vegetable: 'verdure',
  fruit: 'frutta',
  legume: 'legumi',
  nuts: 'frutta a guscio',
  potato: 'patate',
  poultry: 'pollo o tacchino',
  fish: 'pesce',
  shellfish: 'crostacei',
  mollusc: 'molluschi',
  tuna_oil: 'tonno sott’olio',
  tuna_brine: 'tonno al naturale',
  egg: 'uova',
  cheese: 'formaggio',
  beef: 'manzo',
  veal: 'vitello',
  rabbit: 'coniglio',
  horse: 'cavallo',
  ham: 'prosciutto',
  bresaola: 'bresaola',
  salami: 'salame',
  mortadella: 'mortadella',
  lean_pork: 'maiale magro',
  wurst: 'wurstel',
  vegetable_soup: 'minestrone o passato',
  cereal_soup: 'minestra di cereali',
};
async function loadRecipeDietOptions() {
  const request = ++recipeDietRequest;
  const mode = $('recipe-diet-mode');
  if (!mode.options.length) {
    fillModes('recipe-diet-mode');
    for (let i = 0; i < 14; i++) {
      const option = element('option', names[i % 7] + ' · settimana ' + (Math.floor(i / 7) + 1));
      option.value = i;
      $('recipe-diet-day').append(option);
    }
  }
  const params = new URLSearchParams({
    mode: mode.value,
    day_index: $('recipe-diet-day').value,
    meal: $('recipe-diet-meal').value,
  });
  const data = await api('recipe-diet-options?' + params);
  if (request !== recipeDietRequest) return;
  recipeDietData = data;
  renderRecipeDietOptions();
}
function renderRecipeDietOptions() {
  const data = recipeDietData;
  if (!data) return;
  const free = data.mode === 'free';
  $('recipe-diet-summary').textContent = free
    ? 'Modalità libera: nessun vincolo sugli abbinamenti della dieta.'
    : 'Lettere previste: ' +
      data.expression +
      ' · ricette con ramo coperto: ' +
      data.counts.compatible +
      ' · ' +
      data.counts.needs_complements +
      ' da completare · ' +
      data.counts.needs_review +
      ' da verificare. Copertura limitata ai rami modellati.';
  const list = $('recipe-diet-options');
  list.replaceChildren();
  const rank = { compatible: 0, needs_complements: 1, needs_review: 2, unconstrained: 0 };
  data.recipes
    .filter((r) => r.status !== 'needs_review' || $('recipe-diet-show-review').checked)
    .sort((a, b) => rank[a.status] - rank[b.status])
    .forEach((r) => {
      const item = element('details');
      item.append(element('summary', r.title + ' — ' + r.label));
      r.branches
        .filter((b) => b.status === r.status)
        .forEach((b) => {
          item.append(element('p', 'Lettera ' + b.letter + ' · ramo ' + b.branch_id.replaceAll('_', ' '), 'muted'));
          b.complement_options.forEach((c) =>
            item.append(
              element(
                'p',
                'Da aggiungere: ' +
                  c.role.replaceAll('_', ' ') +
                  ' — ' +
                  c.allowed_groups.map((g) => dietGroupLabels[g] || g).join(', '),
              ),
            ),
          );
        });
      if (r.status === 'needs_review') {
        const best = r.branches.slice().sort((a, b) => a.blocked.length - b.blocked.length)[0];
        if (best) {
          item.append(
            element('p', 'Esempio di controllo: lettera ' + best.letter + ' · ' + best.branch_id.replaceAll('_', ' ')),
          );
          best.blocked.forEach((b) =>
            item.append(
              element(
                'p',
                (b.ingredient || b.role || 'Ingrediente') +
                  ': ' +
                  b.reason +
                  (b.group ? ' (' + (dietGroupLabels[b.group] || b.group) + ')' : ''),
                'muted',
              ),
            ),
          );
        } else item.append(element('p', 'Le alternative di questa scheda non sono ancora modellate.'));
      }
      if (r.status !== 'needs_review') {
        const button = element('button', 'Prova questa ricetta', 'secondary');
        button.type = 'button';
        button.onclick = () => {
          $('solver-recipe').value = r.recipe_id;
          recipeProductFields();
          $('recipe-solution').replaceChildren();
          showRecipeTab('solver');
          message(r.label + '. La prova del solver resta separata dal piano giornaliero.');
        };
        item.append(button);
      }
      list.append(item);
    });
}
['recipe-diet-mode', 'recipe-diet-day', 'recipe-diet-meal'].forEach(
  (id) => ($(id).onchange = () => loadRecipeDietOptions().catch((e) => message(e.message))),
);
$('recipe-diet-show-review').onchange = renderRecipeDietOptions;

function dailyFields(){
 const d=profile.daily_meals;$('daily-enabled').checked=d.enabled;$('daily-second-bar').checked=d.allow_second_bar;$('daily-afternoon-fruit').checked=d.afternoon_fruit;$('daily-banana-min').value=d.banana_min_g;$('daily-banana-max').value=d.banana_max_g;$('daily-demo').checked=d.targets_demo;
 const ps=profile.food_preferences?.products||[];$('daily-products').textContent=ps.length?ps.map(p=>p.name+' · '+p.serving_g+' g · '+p.kcal_per_serving+' kcal per unità (etichetta fornita da te)').join('; '):'Nessun prodotto personale registrato: la prima scelta disponibile è una banana per colazione e ciascuno spuntino pianificato.';
 $('daily-second-bar').disabled=!ps.length;$('planning-scope-note').textContent=d.enabled?'Il prossimo calcolo include colazione, spuntini pianificati, pranzo e cena. Colazione e spuntini seguono una variante personalizzata.':'Il prossimo calcolo copre pranzo e cena. Puoi includere colazione e spuntini dal profilo.';
 const fields=$('daily-targets');fields.replaceChildren();const head=element('div',undefined,'target-row');['Nutriente','Minimo','Bersaglio','Massimo'].forEach(t=>head.append(element('span',t)));fields.append(head);
 nutrients.forEach(([n,label])=>{const row=element('div',undefined,'target-row');row.append(element('span',label));['min','target','max'].forEach(k=>{const input=element('input');input.id='daily-'+n+'-'+k;input.type='number';input.min='0';input.step='any';input.max='10000';input.required=true;input.value=d.targets[n][k];input.setAttribute('aria-label','Giornata '+label+' '+k);row.append(input)});fields.append(row)});
}
function readDailyFields(){const targets={};nutrients.forEach(([n])=>{targets[n]={};['min','target','max'].forEach(k=>targets[n][k]=Number($('daily-'+n+'-'+k).value))});return {enabled:$('daily-enabled').checked,allow_second_bar:$('daily-second-bar').checked,afternoon_fruit:$('daily-afternoon-fruit').checked,banana_min_g:Number($('daily-banana-min').value),banana_max_g:Number($('daily-banana-max').value),targets,targets_demo:$('daily-demo').checked,policy:'personalized_habits'}}

let healthPoll = null;
function healthTable(headers,rows){const table=element('table',undefined,'health-table');const head=element('thead'),tr=element('tr');headers.forEach(h=>tr.append(element('th',h)));head.append(tr);table.append(head);const body=element('tbody');rows.forEach(values=>{const r=element('tr');values.forEach(v=>r.append(element('td',String(v))));body.append(r)});table.append(body);return table}
async function loadHealth(){
 const response=await api('health');$('health-import').hidden=!response.can_import;
 const job=response.job;const running=job&&['starting','parsing','summarizing'].includes(job.state);
 $('health-import').disabled=running;
 $('health-import-status').textContent=running?'Importazione in corso · '+(job.records??0).toLocaleString('it-IT')+' record esaminati':job?.state==='failed'?job.message:job?.state==='complete'?(job.reused?'Esportazione già esaminata':'Importazione completata'):'';
 const panel=$('health-summary');panel.replaceChildren();
 if(!response.imported){panel.append(element('p','Nessuna esportazione sanitaria importata per questo profilo.'))}
 else {
  const r=response.report;const fmt=v=>v==null?'—':Number(v).toLocaleString('it-IT',{maximumFractionDigits:1});
  panel.append(element('h2','Copertura e aggiornamento'));
  panel.append(element('p','Record esaminati: '+r.import.records_seen.toLocaleString('it-IT')+' · Allenamenti: '+r.import.workouts_stored+' · Ultimo giorno con energia: '+(r.latest_energy_date??'—')));
  panel.append(element('p',r.scenarios.status==='available'?'Base calorica disponibile per scenari di consumo.':'Base calorica insufficiente o obsoleta: non usare questi valori come consumo attuale.','notice'));
  panel.append(element('h2','Misure corporee e indicatori'));
  if(r.body_profile_needs_review)panel.append(element('p','Peso assente o non aggiornato negli ultimi 90 giorni: rivedere il profilo corporeo prima di personalizzare gli obiettivi.','notice'));
  const labels={weight:'Peso',height:'Altezza',body_fat:'Grasso corporeo',bmi:'BMI',resting_hr:'Frequenza a riposo',vo2max:'VO₂ max'};
  panel.append(healthTable(['Misura','Valore','Data','Fonte'],Object.entries(r.measures).map(([k,v])=>[labels[k]??k,fmt(v.value)+' '+v.unit,v.date+' · '+v.age_days+' giorni fa',v.source])));
  panel.append(element('h2','Dispendio recente stimato'));
  panel.append(element('p','Finestre ancorate agli ultimi giorni utilizzabili, non necessariamente alla data odierna. I giorni mancanti non sono trattati come zero.','muted'));
  panel.append(healthTable(['Finestra','Giorni utilizzabili','Ultimo giorno','Media kcal/giorno','Equivalente kcal/settimana'],r.windows.map(w=>[w.days+' giorni',w.valid_days+'/'+w.days,w.end_date??'—',fmt(w.mean_daily_estimated_kcal),fmt(w.weekly_equivalent_estimated_kcal)])));
  panel.append(element('h3','Scenari empirici di consumo · ultimi 28 giorni disponibili'));
  panel.append(element('p','Basso: '+fmt(r.scenarios.low_kcal)+' · Centrale: '+fmt(r.scenarios.central_kcal)+' · Alto: '+fmt(r.scenarios.high_kcal)+' kcal/giorno. Dati di '+(r.scenarios.staleness_days??'—')+' giorni fa. Percentili 20/50/80: variabilità osservata, non intervallo di confidenza.'));
  panel.append(element('h2','Storico degli allenamenti'));
  panel.append(healthTable(['Data','Attività','Durata','Energia attiva stimata','Provenienza energia'],r.workouts.slice(-20).reverse().map(w=>[w.date,w.activity.replace('HKWorkoutActivityType',''),fmt(w.duration_minutes)+' min',fmt(w.active_kcal)+' kcal',w.active_energy_kind??'non disponibile'])));
  panel.append(element('h3','Modelli calorici preliminari per attività'));
  panel.append(healthTable(['Attività','Prove','kcal/min P20–P50–P80','Stato'],r.workout_forecasts.map(w=>[w.activity.replace('HKWorkoutActivityType',''),w.observations,[w.kcal_per_min_p20,w.kcal_per_min_p50,w.kcal_per_min_p80].map(fmt).join(' – '),w.status==='provisional'?'Preliminare':'Insufficiente/obsoleto'])));
  panel.append(element('h2','Dati disponibili per gli algoritmi'));
  panel.append(element('p','Misure con data e fonte, scenari di consumo e modelli preliminari degli allenamenti sono disponibili. Il solver congiunto dieta/palestra è il passaggio successivo; gli obiettivi demo restano invariati.'));
  const details=element('details');details.append(element('summary','Qualità dei dati e limiti'));r.limitations.forEach(note=>details.append(element('p',note,'muted')));details.append(element('p','Campioni scartati: '+JSON.stringify(r.import.invalid)+' · Duplicati saltati: '+r.import.duplicates_skipped,'muted'));panel.append(details);
 }
 if(healthPoll)clearTimeout(healthPoll);healthPoll=running?setTimeout(()=>loadHealth().catch(e=>message(e.message)),3000):null;
}
$('health-import').onclick=async()=>{try{await api('health/import','POST',{});await loadHealth()}catch(e){message(e.message)}};

function showRecipeTab(tab) {
  document.querySelectorAll('[data-recipe-tab]').forEach((b) => {
    const on = b.dataset.recipeTab === tab;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', String(on));
  });
  document.querySelectorAll('[data-recipe-panel]').forEach((panel) => (panel.hidden = panel.dataset.recipePanel !== tab));
}
document.querySelectorAll('[data-recipe-tab]').forEach((b) => (b.onclick = () => showRecipeTab(b.dataset.recipeTab)));

// Theme: follows the system unless the viewer picked one (kept only in this browser).
function applyTheme(theme) {
  if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
}
try {
  applyTheme(localStorage.getItem('diet-theme'));
} catch {}
$('theme-toggle').onclick = () => {
  const current = document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  try {
    localStorage.setItem('diet-theme', next);
  } catch {}
};

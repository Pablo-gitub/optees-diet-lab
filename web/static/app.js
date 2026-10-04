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
function renderPlans() {
  const day = Number($('day').value),
    mode = $('planning-mode').value;
  const visible = plans.filter((x) => x.plan.day_index === day && x.plan.mode === mode);
  $('plans').replaceChildren();
  $('empty').hidden = visible.length > 0;
  $('count').textContent = visible.length ? visible.length + ' alternative nello storico' : '';
  visible.forEach((entry, index) => {
    const p = entry.plan;
    const card = element('article', undefined, 'card' + (entry.selected ? ' selected' : ''));
    const header = element('div', undefined, 'card-header');
    header.append(
      element('h3', 'Alternativa ' + (index + 1)),
      element('span', entry.selected ? 'Scelta' : p.demo ? 'Demo' : 'Configurata', 'tag'),
    );
    card.append(header);
    if (!['optimal', 'feasible'].includes(p.status)) {
      card.append(
        element(
          'p',
          'Nessuna soluzione nel sottoinsieme modellato con questi vincoli. Questo non prova che la dieta completa sia impossibile.',
          'error',
        ),
      );
    } else {
      const opt=p.optimization;
      if(opt){
        const names={balanced:'Bilanciato',pareto:'Pareto · campione di compromessi',minmax:'Min-Max',maxmin:'Max-Min'};
        card.append(element('p',names[opt.strategy]+(opt.requested==='bandit'?' · suggerito dal bandit ('+(opt.bandit_reason==='exploration'?'esplorazione':'UCB1')+')':''),'muted'));
        if(opt.relative_errors)card.append(element('p','Scarto relativo peggiore: '+(100*opt.worst_relative_error).toFixed(1)+'% · Soddisfazione minima: '+(100*opt.minimum_satisfaction).toFixed(1)+'%','muted'));
        if(opt.relative_errors){const labels={kcal:'Energia',protein_g:'Proteine',fat_g:'Grassi',carbs_available_g:'Carboidrati'};card.append(element('p',Object.entries(opt.relative_errors).map(([k,v])=>labels[k]+': scarto '+(100*v).toFixed(1)+'%').join(' · '),'muted'))}
        if(opt.strategy==='pareto')card.append(element('p','Non dominata nel campione calcolato; la frontiera completa non è garantita.','muted'));
      }
      const meals=p.scope==='full_day_planned_meals'?['breakfast','morning_snack','lunch','afternoon_snack','dinner']:['lunch','dinner'];
      const mealNames={breakfast:'Colazione',morning_snack:'Metà mattina',lunch:'Pranzo',afternoon_snack:'Metà pomeriggio',dinner:'Cena'};
      card.append(element('p',p.scope==='full_day_planned_meals'?'Totali della giornata pianificata':'Totali di pranzo + cena','muted'));
      if(p.diet_note)card.append(element('p',p.diet_note,'muted'));
      (p.preference_changes||[]).forEach(note=>card.append(element('p',note,'muted')));
      meals.forEach((meal) => {
        const block = element('div', undefined, 'meal');
        block.append(element('h4', mealNames[meal]+(p.slots[meal]==='personalized_habits'?' · abitudini personali':p.slots[meal]==='not_planned'?' · non pianificato':' · '+p.slots[meal])));
        p.selections
          .filter((f) => f.meal === meal)
          .forEach((f) => {
            const row = element('div', undefined, 'food');
            row.append(element('span', f.food+((f.source==='CREA'||(!f.source&&f.crea_id))?' · alimento generico CREA':f.source==='user_label'?' · etichetta fornita nel profilo':'')), element('span', f.grams.toLocaleString('it-IT') + ' g' + (f.units ? ' · ' + f.units + (f.units === 1 ? ' confezione' : ' confezioni') : '')));
            block.append(row);
          });
        if(p.nutrients_by_meal?.[meal]&&p.slots[meal]!=='not_planned')block.append(element('p',Math.round(p.nutrients_by_meal[meal].kcal)+' kcal · '+p.nutrients_by_meal[meal].protein_g.toFixed(1)+' g proteine · '+p.nutrients_by_meal[meal].carbs_available_g.toFixed(1)+' g carboidrati · '+p.nutrients_by_meal[meal].fat_g.toFixed(1)+' g grassi','muted'));
        card.append(block);
      });
      const metrics = element('div', undefined, 'metrics');
      [
        ['kcal', 'kcal'],
        ['protein_g', 'proteine'],
        ['carbs_available_g', 'carboidrati'],
        ['fat_g', 'grassi'],
      ].forEach(([key, label]) => {
        const cell = element('div');
        cell.append(
          element('strong', Math.round(p.nutrients[key]) + (key === 'kcal' ? '' : ' g')),
          element('small', label),
        );
        metrics.append(cell);
      });
      card.append(metrics);
      const report = p.constraint_report;
      if (report) {
        card.append(element('p', report.verified && report.all_respected ? '✓ Vincoli modellati rispettati' : 'Verifica dei vincoli da controllare', report.all_respected ? 'constraint-ok' : 'error'));
        const details = element('details', undefined, 'constraint-details');
        details.append(element('summary', 'Quantità, obiettivi e limiti verificati'));
        details.append(element('p', 'Porzioni, confezioni intere e scelte alimentari del modello verificate. Il bersaglio è un obiettivo: minimo e massimo sono i limiti obbligatori.', 'muted'));
        const table = element('table');
        const heading = element('tr');
        ['Ambito / nutriente', 'Risultato', 'Limiti', 'Bersaglio', 'Esito'].forEach(t => heading.append(element('th', t)));
        const thead = element('thead'); thead.append(heading); table.append(thead);
        const body = element('tbody');
        const labels = {kcal:'Energia',protein_g:'Proteine',carbs_available_g:'Carboidrati',fat_g:'Grassi'};
        const scopes = {day:p.scope === 'full_day_planned_meals' ? 'Giornata' : 'Pranzo + cena',breakfast:'Colazione',morning_snack:'Metà mattina',lunch:'Pranzo',afternoon_snack:'Metà pomeriggio',dinner:'Cena'};
        const number = value => value.toLocaleString('it-IT', {maximumFractionDigits:2});
        report.checks.forEach(c => {
          const unit = c.nutrient === 'kcal' ? ' kcal' : ' g';
          const row = element('tr');
          [scopes[c.meal] + ' · ' + labels[c.nutrient], number(c.actual) + unit,
           number(c.min) + '–' + number(c.max) + unit,
           c.target == null ? '—' : number(c.target) + unit,
           c.respected ? '✓ Rispettato' : 'Fuori limite'].forEach(t => row.append(element('td', t)));
          body.append(row);
        });
        table.append(body); details.append(table);
        details.append(element('p', report.rounding_note, 'muted'));
        card.append(details);
      } else {
        card.append(element('p', 'Storico: dettaglio dei vincoli non disponibile. Genera nuove alternative per visualizzarlo.', 'muted'));
      }
      const button = element(
        'button',
        entry.selected ? 'Piano scelto' : 'Scegli questo piano',
        entry.selected ? 'secondary' : '',
      );
      const feedback=element('div',undefined,'feedback');
      const tried=element('input');tried.type='checkbox';tried.checked=entry.feedback!=null;
      const triedLabel=element('label');triedLabel.append(tried,document.createTextNode(' Ho effettivamente provato questo piano'));
      const rating=element('select');rating.setAttribute('aria-label','Valutazione del piano');
      for(let i=1;i<=5;i++){const o=element('option',i+' / 5');o.value=i;rating.append(o)}rating.value=entry.feedback??3;
      const send=element('button',entry.feedback==null?'Salva feedback':'Aggiorna feedback','secondary');
      send.onclick=async()=>{if(!tried.checked){message('Conferma di aver effettivamente provato il piano');return}try{await api('plans/'+entry.id+'/feedback','POST',{tried:true,rating:Number(rating.value)});await loadPlans();message('Feedback personale salvato')}catch(e){message(e.message)}};
      feedback.append(triedLabel,rating,send);card.append(feedback);
      button.disabled = entry.selected;
      button.onclick = async () => {
        try {
          await api('plans/' + entry.id + '/select', 'POST', {});
          await loadPlans();
        } catch (e) {
          message(e.message);
        }
      };
      card.append(button);
    }
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
document.querySelectorAll('[data-page]').forEach(
  (button) =>
    (button.onclick = () => {
      const page = button.dataset.page;
      ['profile', 'planning', 'recipes', 'health'].forEach((id) => ($(id).hidden = id !== page));
      document.querySelectorAll('[data-page]').forEach((b) => b.classList.toggle('active', b === button));
      $('page-title').textContent =
        page === 'profile' ? 'Il mio profilo' : page === 'recipes' ? 'Ricette dal mondo' : page === 'health' ? 'Salute · dati personali' : 'Pianificazione';
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
  italian: 'Italiana',
  chinese: 'Cinese',
  japanese: 'Giapponese',
  indian: 'Indiana',
  thai: 'Thailandese',
  french: 'Francese',
  mexican: 'Messicana',
  greek: 'Greca',
  spanish: 'Spagnola',
  korean: 'Coreana',
  mediterranean: 'Mediterranea',
};
async function loadCuisines() {
  cuisineOptions = await api('cuisines');
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
async function loadRecipes() {
  const params = new URLSearchParams({
    q: $('recipe-search').value,
    cuisine: $('recipe-cuisine').value,
    preferred: $('only-preferred').checked,
    offset: recipeOffset,
  });
  const data = await api('recipes?' + params);
  $('recipe-count').textContent =
    data.total +
    ' ricette · ' +
    (data.recipes.length ? recipeOffset + 1 : 0) +
    '–' +
    (recipeOffset + data.recipes.length);
  $('recipe-list').replaceChildren();
  data.recipes.forEach((r) => {
    const card = element('article', undefined, 'card');
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
      attr.append(
        srcLink,
        element('span', 'Foto illustrativa — ingredienti e porzioni possono differire.', 'disclaimer'),
      );
      card.append(img, attr);
    }
    card.append(
      element('h3', r.title),
      element(
        'p',
        (cuisineLabels[r.cuisine_id] || r.cuisine) +
          ' · ' +
          (r.total_minutes ?? '?') +
          ' min · ' +
          r.servings +
          ' porzioni',
        'muted',
      ),
    );
    const n = r.declared_nutrition;
    card.append(
      element('p', (n.kcal ?? '?') + ' kcal per porzione · ' + (n.protein_g ?? '?') + ' g proteine', 'subhead'),
    );
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
    card.append(details);
    const link = element('a', r.source + ' · ' + r.license);
    if (r.source_url.startsWith('https://')) link.href = r.source_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    card.append(link, element('p', 'Abbinamento ingredienti: da verificare.', 'muted'));
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

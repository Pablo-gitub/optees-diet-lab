/* Per-account drafts and supported preference effects; no browser-owned profile state. */
let tasteFoodNames = {}, tasteDraft = null, tasteStep = 1, tasteRevision = 0, tasteBusy = false;
const tasteStatus = {not_started:'Da completare', partial:'Iniziato', deferred:'Rimandato', completed:'Completato'};
function tasteButton(text, action, primary=false) {
  const button=element('button',text,primary?'primary':'secondary');button.type='button';button.onclick=action;return button;
}
function renderTasteSettings() {
  const state=profile.taste_onboarding, box=$('taste-summary');box.replaceChildren();
  box.append(element('p','Gusti e abitudini','eyebrow'),element('h2','Le tue preferenze'));
  box.append(element('p',tasteStatus[state.status]+' · risposte modificabili in qualsiasi momento.','muted'));
  box.append(element('p',`Cucine selezionate: ${profile.preferred_cuisines.length} · alimenti esclusi: ${profile.excluded_crea_ids.length}.`));
  const actions=element('div',undefined,'actions');
  actions.append(tasteButton(state.status==='completed'?'Modifica gusti e abitudini':'Completa gusti e abitudini',()=>openTasteSetup(),true));
  actions.append(tasteButton('Affina con Abbinamenti',()=>document.querySelector('[data-page="matches"]').click()));
  actions.append(tasteButton('Rivedi gli obiettivi',()=>{$('profile-objectives').open=true;$('goals-panel').scrollIntoView({block:'start'});}));
  const shortcuts=$('profile-shortcuts');shortcuts.replaceChildren(element('h2','Attività, dati e account'));
  shortcuts.append(tasteButton('Attività e attrezzatura',async()=>{await document.querySelector('[data-page="workout"]').onclick();showWorkoutTab('config');}),tasteButton('Dati Salute e misure',()=>document.querySelector('[data-page="progress"]').click()),element('p','Tema e uscita dal profilo sono disponibili nell’intestazione.','muted'));
  const invite=$('taste-invite');invite.hidden=state.status==='completed';invite.replaceChildren();if(!invite.hidden)invite.append(element('p','Gusti e abitudini: '+tasteStatus[state.status]+'. Puoi completarli quando vuoi.'),tasteButton('Apri le preferenze',()=>openTasteSetup()));
  if(state.status==='completed')actions.append(tasteButton('Prepara un piano',()=>document.querySelector('[data-page="planning"]').click()));
  box.append(actions,element('p','Le modifiche valgono per nuove proposte. Una settimana già applicata resta invariata.','muted'));
}
function openTasteSetup() {
  const state=profile.taste_onboarding;tasteDraft=structuredClone(state.draft);tasteStep=state.status==='completed'?1:state.step;tasteRevision=state.revision;
  ['home','planning','workout','recipes','matches','progress','profile'].forEach(id=>$(id).hidden=true);
  $('taste-onboarding').hidden=false;
  $('page-eyebrow').textContent='Preferenze personali';$('page-title').textContent='Gusti e abitudini';$('page-subtitle').textContent='Facoltativo · riprendibile · sempre modificabile nel Profilo';
  renderTasteStep();window.scrollTo({top:0});
}
function tasteInput(label,value,key,type='text') {
  const wrap=element('label',label);const input=element('input');input.type=type;input.value=value;input.dataset.taste=key;input.setAttribute('aria-describedby','taste-error');
  if(type==='number'){input.min=20;input.max=500;input.step=1;}
  wrap.append(input);return wrap;
}
function tasteCheckbox(label,key) {
  const wrap=element('label',undefined,'check');const input=element('input');input.type='checkbox';input.checked=tasteDraft[key];input.dataset.taste=key;wrap.append(input,document.createTextNode(label));return wrap;
}
function captureTasteDraft() {
  document.querySelectorAll('#taste-onboarding [data-taste]').forEach(input=>{
    tasteDraft[input.dataset.taste]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;
  });
  if(tasteStep===1)tasteDraft.preferred_cuisines=[...document.querySelectorAll('#taste-onboarding [name="taste-cuisine"]:checked')].map(x=>x.value);
}
function renderTasteStep() {
  const root=$('taste-onboarding');root.replaceChildren();const panel=element('div',undefined,'panel taste-panel');
  const heading=element('h2',['Cucine ed esclusioni','Le tue abitudini','Riepilogo delle preferenze'][tasteStep-1]);heading.id='taste-heading';heading.tabIndex=-1;
  panel.append(element('p',`Passo ${tasteStep} di 3`,'eyebrow'),heading);
  if(tasteStep===1){
    panel.append(element('p','Quali cucine vuoi trovare nel catalogo? Queste scelte filtrano le ricette, non modificano il solver.','muted'));
    const list=element('div',undefined,'taste-cuisines');
    cuisineOptions.forEach(c=>{const label=element('label',undefined,'check');const input=element('input');input.type='checkbox';input.name='taste-cuisine';input.value=c.id;input.checked=tasteDraft.preferred_cuisines.includes(c.id);label.append(input,document.createTextNode(cuisineLabels[c.id]||c.name));list.append(label);});
    const details=element('details');details.append(element('summary',`${tasteDraft.preferred_cuisines.length} cucine selezionate · scegli o modifica`),list);panel.append(details);
    panel.append(element('h3','Alimenti da escludere'),element('p','Un’esclusione vale per quel codice CREA nei nuovi calcoli. Non verifica tutti gli allergeni o gli ingredienti delle ricette.','muted'));
    const exclusions=element('div');exclusions.id='taste-exclusions';panel.append(exclusions);renderTasteExclusions(exclusions);
    const searchLabel=element('label','Cerca un alimento da escludere');const search=element('input');search.type='search';search.id='taste-search';search.placeholder='Es. banana, latte';searchLabel.append(search);panel.append(searchLabel);
    panel.append(tasteButton('Cerca alimenti',async()=>{
      try{const results=await api('foods/search?q='+encodeURIComponent(search.value)+'&limit=20');const target=$('taste-results');target.replaceChildren();const foods=results.filter(x=>x.food.source==='CREA');if(!foods.length)target.append(element('p','Nessun alimento CREA trovato. Prova un altro nome.'));
        foods.forEach(food=>{const button=tasteButton('Escludi '+food.name,()=>{if(!tasteDraft.excluded_crea_ids.includes(food.food.id))tasteDraft.excluded_crea_ids.push(food.food.id);tasteFoodNames[food.food.id]=food.name;renderTasteExclusions();tasteDirty=true;queueTasteDraft();});target.append(button);});
      }catch(e){tasteError(e.message)}
    }));const results=element('div',undefined,'taste-results');results.id='taste-results';panel.append(results);
  } else if(tasteStep===2){
    panel.append(element('p',profile.daily_meals.enabled?'Giornata intera attiva: queste scelte influenzano le nuove proposte.':'La giornata intera è disattivata: conserveremo queste scelte per quando la attiverai nel Profilo. Il questionario non cambia modalità o obiettivi.','notice'));
    panel.append(tasteCheckbox('Pianifica anche un frutto a metà pomeriggio','afternoon_fruit'),tasteCheckbox('Consenti una seconda barretta a colazione, se ho un prodotto personale compatibile','allow_second_bar'));
    panel.append(tasteInput('Banana · minimo g senza buccia',tasteDraft.banana_min_g,'banana_min_g','number'),tasteInput('Banana · massimo g senza buccia',tasteDraft.banana_max_g,'banana_max_g','number'));
    panel.append(element('p','Porzioni 20–500 g. Le opzioni effettive dipendono dalle etichette e dalle esclusioni.','muted'));
    const label=element('label','Nota personale · promemoria, non un vincolo del piano');const note=element('textarea');note.rows=3;note.maxLength=2000;note.value=tasteDraft.preference_note;note.dataset.taste='preference_note';label.append(note);panel.append(label);
  } else {
    const names=tasteDraft.preferred_cuisines.map(id=>cuisineLabels[id]||cuisineOptions.find(x=>x.id===id)?.name||id);
    panel.append(element('p','Cucine del catalogo: '+(names.join(', ')||'tutte')),element('p','Alimenti esclusi: '+(tasteDraft.excluded_crea_ids.map(id=>tasteFoodNames[id]||id).join(', ')||'nessuno')));
    panel.append(element('p',`Frutto pomeridiano: ${tasteDraft.afternoon_fruit?'sì':'no'} · seconda barretta compatibile: ${tasteDraft.allow_second_bar?'sì':'no'} · banana: ${tasteDraft.banana_min_g}–${tasteDraft.banana_max_g} g.`));
    panel.append(element('p','Nota personale: '+(tasteDraft.preference_note||'nessuna')));
    panel.append(element('p','Salva applica queste preferenze ai nuovi calcoli e al catalogo. Non cambia obiettivi, modalità o settimana già applicata.','notice'));
    panel.append(element('p',profile.targets_demo?'Stai usando obiettivi dimostrativi. Conferma gli obiettivi separatamente nel Profilo prima di un piano personale.':'Gli obiettivi personali restano quelli del Profilo.','muted'));
  }
  const error=element('p');error.id='taste-error';error.setAttribute('role','alert');panel.append(error);
  const actions=element('div',undefined,'actions');
  if(tasteStep>1)actions.append(tasteButton('Indietro',()=>persistTaste('draft',tasteStep-1)));
  actions.append(tasteButton(tasteStep<3?'Salva bozza e continua':'Salva preferenze',()=>persistTaste(tasteStep<3?'draft':'complete',Math.min(3,tasteStep+1)),true));
  actions.append(tasteButton('Non ora · conserva la bozza',()=>persistTaste('defer',tasteStep)));
  const draftState=element('p','Bozza conservata dopo ogni modifica','muted small');draftState.id='taste-draft-state';draftState.setAttribute('role','status');panel.append(draftState);
  panel.append(actions,element('p','Usa “Non ora” per ritrovare la bozza anche dopo logout. Nessuna riapertura automatica dopo il rinvio.','muted'));root.append(panel);heading.focus();
}
function renderTasteExclusions(box=$('taste-exclusions')){box.replaceChildren();tasteDraft.excluded_crea_ids.forEach(id=>{box.append(tasteButton('Rimuovi esclusione '+(tasteFoodNames[id]||id),()=>{tasteDraft.excluded_crea_ids=tasteDraft.excluded_crea_ids.filter(x=>x!==id);renderTasteExclusions();tasteDirty=true;queueTasteDraft();}));});if(!tasteDraft.excluded_crea_ids.length)box.append(element('p','Nessuna esclusione indicata.'))}
function tasteError(text){$('taste-error').textContent=text;}
async function persistTaste(action,step){
  if(tasteBusy)return;clearTimeout(tasteSaveTimer);captureTasteDraft();if(action==='draft'&&step>tasteStep&&tasteStep===2&&!(20<=tasteDraft.banana_min_g&&tasteDraft.banana_min_g<=tasteDraft.banana_max_g&&tasteDraft.banana_max_g<=500)){tasteError('Porzioni banana: 20–500 g, minimo ≤ massimo. Puoi anche rimandare e conservare la bozza.');return;}tasteBusy=true;await tasteSaveQueue;
  document.querySelectorAll('#taste-onboarding button').forEach(b=>b.disabled=true);
  try{
    const data=await api('profile/tastes','PUT',{revision:tasteRevision,action,step,draft:tasteDraft});profile=data.profile;tasteFoodNames=data.taste_food_names||tasteFoodNames;tasteRevision=profile.taste_onboarding.revision;tasteStep=step;tasteDirty=false;
    if(action==='draft'){renderTasteStep();return;}
    await load();$('taste-onboarding').hidden=true;await document.querySelector('[data-page="profile"]').onclick();$('taste-summary').tabIndex=-1;$('taste-summary').focus();
    message(action==='complete'?'Preferenze salvate · piano applicato invariato':'Bozza conservata · riprendila dal Profilo');
  }catch(e){tasteError(e.message);if(e.status===409)renderTasteConflict();}
  finally{tasteBusy=false;document.querySelectorAll('#taste-onboarding button').forEach(b=>b.disabled=false);}
}

let tasteSaveQueue=Promise.resolve(), tasteSaveTimer=null, tasteDirty=false;
function queueTasteDraft(){
  clearTimeout(tasteSaveTimer);captureTasteDraft();const draft=structuredClone(tasteDraft),step=tasteStep;
  tasteSaveQueue=tasteSaveQueue.then(async()=>{
    const data=await api('profile/tastes','PUT',{revision:tasteRevision,action:'draft',step,draft});
    profile=data.profile;tasteFoodNames=data.taste_food_names||tasteFoodNames;tasteRevision=profile.taste_onboarding.revision;
    if(JSON.stringify(tasteDraft)===JSON.stringify(draft)){tasteDirty=false;const state=$('taste-draft-state');if(state)state.textContent='Bozza salvata nel profilo';if(!$('taste-onboarding').hidden)tasteError('');}
  }).catch(e=>{tasteDirty=true;if(!$('taste-onboarding').hidden){tasteError(e.message);if(e.status===409)renderTasteConflict();}});
  return tasteSaveQueue;
}
$('taste-onboarding').addEventListener('input',()=>{tasteDirty=true;clearTimeout(tasteSaveTimer);const state=$('taste-draft-state');if(state)state.textContent='Salvataggio della bozza…';tasteSaveTimer=setTimeout(()=>queueTasteDraft(),500);});
$('taste-onboarding').addEventListener('change',()=>{tasteDirty=true;queueTasteDraft();});
async function leaveTasteSetup(){
  if($('taste-onboarding').hidden)return true;
  if(!tasteDirty){await tasteSaveQueue;return !tasteDirty;}
  await queueTasteDraft();return !tasteDirty;
}
window.addEventListener('beforeunload',e=>{if(tasteDirty&&!$('taste-onboarding').hidden){e.preventDefault();e.returnValue='';}});

function renderTasteConflict(){
  let box=$('taste-conflict');if(!box){box=element('div',undefined,'notice');box.id='taste-conflict';$('taste-error').after(box);}box.replaceChildren(element('p','Un’altra sessione ha salvato preferenze più recenti. La tua bozza è ancora visibile: scegli quale riprendere.'));
  const recover=async keep=>{try{captureTasteDraft();const local=structuredClone(tasteDraft);const data=await api('profile');profile=data.profile;tasteFoodNames=data.taste_food_names||{};tasteRevision=profile.taste_onboarding.revision;
    if(keep){tasteDraft=local;await queueTasteDraft();if(!tasteDirty)renderTasteStep();}else{tasteDirty=false;openTasteSetup();}
  }catch(e){tasteError(e.message);}};
  box.append(tasteButton('Conserva la mia bozza sulla versione aggiornata',()=>recover(true)),tasteButton('Usa la bozza salvata (sostituisce la mia)',()=>recover(false)));
}

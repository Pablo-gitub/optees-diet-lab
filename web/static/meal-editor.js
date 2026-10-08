// Meal changes are drafts; only commit replaces the diary, atomically.
let mealDraft=null,mealDraftDirty=false,mealDraftBusy=false,mealDraftQueue=Promise.resolve(),mealDraftTimer=null;
function mealEditorButton(text,action,primary=false){const b=element('button',text,primary?'primary':'secondary');b.type='button';b.onclick=action;return b;}
function mealDraftBody(){return {date:mealDraft.date,slot:mealDraft.slot,revision:mealDraft.revision,items:mealDraft.items.map(i=>({food:i.food,...(i.units!=null?{units:i.units}:{grams:i.grams})}))};}
async function openMealEditor(day,slot){
  try{$('message').hidden=true;mealDraft=await api('diary/draft?date='+day.date+'&slot='+slot);mealDraftDirty=false;if(!mealRouteRestoring)history.pushState(null,'','#pasto?data='+day.date+'&slot='+slot);$('home').hidden=true;$('meal-editor').hidden=false;renderMealEditor();}
  catch(e){const error=$('home-load-error');error.hidden=false;error.replaceChildren(element('p',e.message),mealEditorButton('Riprova apertura',()=>openMealEditor(day,slot)));}
}
function renderMealEditor(){
  const editedDraft=mealDraft;const root=$('meal-editor');root.replaceChildren();const box=element('div',undefined,'panel taste-panel');
  const heading=element('h2','Modifica '+mealMeta[mealDraft.slot][0].toLowerCase());heading.tabIndex=-1;heading.id='meal-editor-heading';
  box.append(element('p',longDate(mealDraft.date)+' · bozza','eyebrow'),heading,element('p','Le quantità sono una bozza. Il diario cambia soltanto quando premi “Salva pasto”.','muted'));
  if(mealDraft.stale)box.append(element('p','Il pasto o il piano è cambiato dall’apertura della bozza. Rivedi il diario prima di sostituirlo.','notice'));
  mealDraft.items.forEach((item,index)=>{
    const row=element('div',undefined,'meal-draft-row');const label=element('label',item.name||item.food.id);const input=element('input');input.type='number';input.min=1;input.max=item.units!=null?20:3000;input.step=1;input.value=item.units??item.grams;input.setAttribute('aria-label','Quantità di '+(item.name||item.food.id));input.setAttribute('aria-describedby','meal-draft-error');
    input.oninput=()=>{if(item.units!=null)item.units=Number(input.value);else item.grams=Number(input.value);mealDraftDirty=true;queueMealAutosave();};label.append(input,element('span',item.units!=null?' confezioni':' g','muted'));
    row.append(label,mealEditorButton('Rimuovi',()=>{mealDraft.items.splice(index,1);mealDraftDirty=true;queueMealAutosave();renderMealEditor();}),mealEditorButton('Sostituisci',()=>{
      const picker=foodSearch({date:mealDraft.date},mealDraft.slot,f=>{if(mealDraftBusy||mealDraft!==editedDraft)return;const targetIndex=mealDraft.items.indexOf(item);if(targetIndex<0)return;mealDraft.items[targetIndex]={...f,grams:f.unit_g||item.grams||100,units:f.unit_g?1:null};mealDraftDirty=true;queueMealAutosave();renderMealEditor();},'Sostituisci '+item.name+' con…');row.append(picker);picker.querySelector('input').focus();
    }));box.append(row);
  });
  if(!mealDraft.items.length)box.append(element('p','Nessun alimento nella bozza. Aggiungine uno; per saltare il pasto torna al diario e usa “Salta”.','muted'));
  box.append(foodSearch({date:mealDraft.date},mealDraft.slot,(f,grams)=>{if(mealDraftBusy||mealDraft!==editedDraft)return;mealDraft.items.push({...f,grams:grams||f.unit_g||100,units:grams?null:f.unit_g?1:null});mealDraftDirty=true;queueMealAutosave();renderMealEditor();}));
  const status=element('p',mealDraftDirty?'Bozza in aggiornamento…':'Bozza conservata nel profilo','muted');status.id='meal-draft-status';status.setAttribute('role','status');const error=element('p');error.id='meal-draft-error';error.setAttribute('role','alert');box.append(status,error);
  const actions=element('div',undefined,'actions');actions.append(mealEditorButton('Salva pasto',()=>finishMealEditor('commit'),true),mealEditorButton('Annulla modifiche',()=>finishMealEditor('discard')),mealEditorButton('Conserva bozza e torna',async()=>{if(await leaveMealEditor())await closeMealEditor();}));
  if(mealDraft.stale)actions.append(mealEditorButton('Scarta bozza e riparti dal diario',async()=>{const date=mealDraft.date,slot=mealDraft.slot;await finishMealEditor('discard');if(!mealDraft)await openMealEditor({date},slot);}));
  box.append(actions);root.append(box);heading.focus();
}
function mealDraftError(e){if(e.code==='draft_conflict'){let box=$('meal-draft-recovery');if(!box){box=element('div',undefined,'actions');box.id='meal-draft-recovery';$('meal-draft-error').after(box);}box.replaceChildren(mealEditorButton('Usa la bozza salvata (sostituisce la mia)',()=>openMealEditor({date:mealDraft.date},mealDraft.slot)),mealEditorButton('Conserva la mia bozza sulla nuova versione',async()=>{try{const items=structuredClone(mealDraft.items);const fresh=await api('diary/draft?date='+mealDraft.date+'&slot='+mealDraft.slot);mealDraft=fresh;mealDraft.items=items;mealDraftDirty=true;await persistMealDraft();renderMealEditor();}catch(error){mealDraftError(error);}}));}
if($('meal-draft-error'))$('meal-draft-error').textContent=e.message||e;if(e.code==='meal_conflict'){mealDraft.stale=true;renderMealEditor();$('meal-draft-error').textContent=e.message;}}
function queueMealAutosave(){clearTimeout(mealDraftTimer);mealDraftTimer=setTimeout(()=>persistMealDraft(),450);}
function persistMealDraft(){
  clearTimeout(mealDraftTimer);if(!mealDraft)return mealDraftQueue;
  const snapshot=structuredClone(mealDraftBody());
  mealDraftQueue=mealDraftQueue.then(async()=>{
    snapshot.revision=mealDraft.revision;const updated=await api('diary/draft','PUT',snapshot);mealDraft.revision=updated.revision;mealDraft.stale=updated.stale;
    if(JSON.stringify(snapshot.items)===JSON.stringify(mealDraftBody().items)){mealDraftDirty=false;if($('meal-draft-status'))$('meal-draft-status').textContent='Bozza conservata nel profilo';if($('meal-draft-error'))$('meal-draft-error').textContent='';}
  }).catch(mealDraftError);return mealDraftQueue;
}
async function leaveMealEditor(){if(mealDraftBusy)return false;if($('meal-editor').hidden)return true;if(mealDraftDirty)await persistMealDraft();else await mealDraftQueue;return !mealDraftDirty;}
async function closeMealEditor(day=null){const date=mealDraft.date,slot=mealDraft.slot;mealDraft=null;mealDraftDirty=false;$('meal-editor').hidden=true;homeDate=date;history.replaceState(null,'','#oggi?data='+date);$('home').hidden=false;if(day){renderDay(day);$('home-load-error').hidden=true;refreshWeek();}else await loadHome();const card=document.querySelector('[data-meal-slot="'+slot+'"]');const target=card?.querySelector('summary,h3');if(target){if(target.tagName==='H3')target.tabIndex=-1;target.focus();}}
async function finishMealEditor(action){
  if(mealDraftBusy)return;mealDraftBusy=true;clearTimeout(mealDraftTimer);document.querySelectorAll('#meal-editor input,#meal-editor button').forEach(el=>el.disabled=true);
  try{await mealDraftQueue;if(action==='commit'&&mealDraftDirty){await persistMealDraft();if(mealDraftDirty)return;}const result=await api('diary/draft/'+action,'POST',action==='commit'?mealDraftBody():{date:mealDraft.date,slot:mealDraft.slot,revision:mealDraft.revision});await closeMealEditor(result);message(action==='commit'?'Pasto salvato':'Modifiche annullate · diario invariato');}
  catch(e){mealDraftError(e);}finally{mealDraftBusy=false;document.querySelectorAll('#meal-editor input,#meal-editor button').forEach(el=>el.disabled=false);}
}
window.addEventListener('beforeunload',e=>{if(mealDraftDirty&&!$('meal-editor').hidden){e.preventDefault();e.returnValue='';}});

const mealPageRoutes={home:'oggi',planning:'settimana',workout:'allenamento',recipes:'cucina',matches:'abbinamenti',progress:'progressi',profile:'profilo'};
let mealRouteRestoring=false;
document.querySelectorAll('[data-page]').forEach(button=>{const original=button.onclick;button.onclick=async e=>{await original(e);if(!$(button.dataset.page).hidden&&!mealRouteRestoring){const route=mealPageRoutes[button.dataset.page];const hash=button.dataset.page==='planning'?planningHash():'#'+route+(button.dataset.page==='home'?'?data='+homeDate:'');if(location.hash!==hash)history.pushState(null,'',hash);}};});
async function restoreAppRoute(hash=location.hash){
  if(!profile||profile.taste_onboarding.welcome)return;
  const [route,query='']=hash.slice(1).split('?'),params=new URLSearchParams(query);const date=params.get('data');
  if(date&&/^\d{4}-\d{2}-\d{2}$/.test(date))homeDate=date;
  if(hash&&location.hash!==hash)history.replaceState(null,'',hash);
  mealRouteRestoring=true;
  try{if(route==='pasto'){await document.querySelector('[data-page="home"]').onclick();await openMealEditor({date:homeDate},params.get('slot'));}
    else if(route==='sessione'){if(params.get('log'))await openWorkoutLog(Number(params.get('log')));else if(params.get('piano'))await openPlannedWorkout(Number(params.get('piano')));}
    else {const page=Object.keys(mealPageRoutes).find(k=>mealPageRoutes[k]===route);if(page){await document.querySelector('[data-page="'+page+'"]').onclick();if(page==='planning')await restorePlanningContext(params);}}}
  finally{mealRouteRestoring=false;}
}
window.addEventListener('popstate',async()=>{if(await leaveMealEditor()){$('meal-editor').hidden=true;await restoreAppRoute();}});

// Calendar → draft → comparison → review → atomic application.
let weekSet=null,weekCompare=[],weekPlanningBusy=false,weekResumeOwner=null,weekRecent=null,weekLoadSequence=0;
const planningKinds={week:'Solo alimentazione',joint:'Alimentazione e allenamento',workout:'Solo allenamento'};
const weekButton=(text,action,style='secondary')=>{const b=element('button',text,style);b.type='button';b.onclick=action;return b;};
const planningKey=()=> 'diet-planning-draft:'+window.planningOwner;
function planningHash(){return '#settimana?data='+$('week-start').value+(weekSet?'&bozza='+weekSet.run_id:'');}
function savePlanningConfig(){try{const targets={rest:{},training:{}};$('joint-targets').querySelectorAll('input').forEach(i=>{targets[i.dataset.type][i.dataset.key]??={};targets[i.dataset.type][i.dataset.key][i.dataset.part]=i.value;});localStorage.setItem(planningKey(),JSON.stringify({week:$('week-start').value,alternatives:$('week-alternatives').value,kind:$('week-kind').value,mode:$('week-mode').value,balanceSelect:$('joint-balance').value,balanceCustom:$('joint-balance-custom').value,targets,availability:{days:Object.fromEntries([...$('joint-availability').querySelectorAll('input')].map(i=>[i.dataset.date,i.value]))},workoutLimits:Object.fromEntries([...document.querySelectorAll('[data-workout-param]')].map(i=>[i.dataset.workoutParam,i.value])),activities:jointActivities,job:weekPlanningJob,set:weekSet?.run_id}));}catch{}}
function renderPlanningSource(){
  const root=$('week-target-source');if(!profile)return;
  const approved=profile.approved_activity_targets?.approved_on;
  root.replaceChildren(element('strong',(profile.daily_meals?.enabled?profile.daily_meals.targets_demo:profile.targets_demo)?'Obiettivi dimostrativi':'Obiettivi dal Profilo'),element('p',(approved?'Approvati il '+shortDate(approved.slice(0,10))+'. ':'')+($('week-kind').value==='joint'?'Puoi variare obiettivi e bilancio per questa bozza.':profile.daily_meals?.enabled?'Alimentazione della giornata completa.':'Obiettivi alimentari riferiti a pranzo e cena.'),'muted small'));
  root.append(weekButton('Riparti dai valori del Profilo',()=>{renderJointTargets();setBalance(profile.energy_balance_target_kcal);savePlanningConfig();},'secondary small'),weekButton('Modifica obiettivi nel Profilo',()=>document.querySelector('[data-page="profile"]').click(),'ghost small'));
}
async function changePlanningWeek(){
  if(weekPlanningBusy)return;
  weekSet=null;weekCompare=[];$('week-warnings').replaceChildren();$('week-robustness').replaceChildren();$('week-plans').replaceChildren();$('week-draft-context').replaceChildren();$('week-review').hidden=true;
  availabilityInputs($('joint-availability'),$('week-start').value);renderLockedDishes();if(!mealRouteRestoring)history.pushState(null,'',planningHash());savePlanningConfig();await loadPlanningWeek();
}
function selectPlanningDate(date){if(!/^\d{4}-\d{2}-\d{2}$/.test(date))return;const select=$('week-start');if(![...select.options].some(o=>o.value===date)){const o=element('option','Dal '+shortDate(date));o.value=date;select.append(o);}select.value=date;}
async function loadPlanningWeek(){
  const root=$('active-week'),start=$('week-start').value,seq=++weekLoadSequence;root.replaceChildren(element('p','Carico il calendario…','muted'));
  try{const week=await api('week?start='+start);if(seq!==weekLoadSequence||start!==$('week-start').value)return;
    root.replaceChildren();const panel=element('div',undefined,'panel active-week-panel');panel.append(element('p',shortDate(start)+' – '+shortDate(addDays(start,6))+' · '+(week.plan_status==='active'?'Piano attivo':'Nessun piano applicato'),'eyebrow'));
    if(week.plan_status!=='active')panel.append(element('p','Puoi consultare le registrazioni oppure preparare la prima bozza.','muted'));
    const calendar=element('div',undefined,'planning-calendar');
    (week.calendar||[]).forEach(day=>{const card=element('article',undefined,'calendar-day');card.append(element('h3',parseDate(day.date).toLocaleDateString('it-IT',{weekday:'long',day:'numeric'})));
      const listed=day.meals.filter(m=>m.foods.length||m.state!=='unknown'||m.locked);
      listed.forEach(m=>{const row=element('div',undefined,'calendar-meal');row.append(element('strong',mealMeta[m.slot][0]),element('span',m.foods.slice(0,2).join(', ')|| (m.estimate?'Pasto stimato':m.state==='skipped'?'Pasto saltato':'Pasto registrato')));if(m.state!=='unknown'||m.locked)row.append(element('small',m.locked?'Bloccato':stateMeta[m.state]?.[0]||m.state,'calendar-state'));card.append(row);});
      if(!listed.length)card.append(element('p','Nessun pasto pianificato','muted small'));
      day.workouts.forEach(w=>card.append(element('p',w.title+' · '+fmt0(w.minutes)+' min · '+(workoutStatus[w.status]?.[0]||w.status),'calendar-workout')));
      card.append(weekButton('Apri giornata',async()=>{homeDate=day.date;await document.querySelector('[data-page="home"]').onclick();},'ghost small'));calendar.append(card);});
    panel.append(calendar);if(week.plan_status==='active'){panel.append(shoppingBlock(start));const rebalance=weekButton('Valuta il rientro dai pasti registrati',async()=>{homeDate=start;await document.querySelector('[data-page="home"]').onclick();$('week-rebalance').scrollIntoView({block:'center'});},'secondary small');if(start===mondayOf(isoDate(new Date()))&&addDays(start,6)!==isoDate(new Date()))panel.append(rebalance);}root.append(panel);
  }catch(e){if(seq===weekLoadSequence)root.replaceChildren(element('p',e.message,'error'),weekButton('Riprova calendario',loadPlanningWeek));}
}
let weekPlanningJob=null;
async function resumePlanning(){
  if(weekResumeOwner===window.planningOwner)return;
  weekResumeOwner=window.planningOwner;
  let saved={};try{saved=JSON.parse(localStorage.getItem(planningKey())||'{}');}catch{}
  const params=new URLSearchParams(location.hash.split('?')[1]||'');selectPlanningDate(params.get('data')||saved.week||$('week-start').value);
  if(saved.alternatives)$('week-alternatives').value=saved.alternatives;
  if(saved.kind&&planningKinds[saved.kind])$('week-kind').value=saved.kind;if(saved.mode)$('week-mode').value=saved.mode;if(saved.balance!==undefined)setBalance(saved.balance);if(saved.balanceSelect!==undefined){$('joint-balance').value=saved.balanceSelect;$('joint-balance-custom').value=saved.balanceCustom||'';$('joint-balance-custom-wrap').hidden=saved.balanceSelect!=='custom';}
  if(saved.targets) $('joint-targets').querySelectorAll('input').forEach(i=>{const v=saved.targets[i.dataset.type]?.[i.dataset.key]?.[i.dataset.part];if(v!=null)i.value=v;});
  availabilityInputs($('joint-availability'),$('week-start').value);if(saved.availability)$('joint-availability').querySelectorAll('input').forEach(i=>{if(saved.availability.days[i.dataset.date]!=null)i.value=saved.availability.days[i.dataset.date];});if(saved.workoutLimits)document.querySelectorAll('[data-workout-param]').forEach(i=>{if(saved.workoutLimits[i.dataset.workoutParam]!=null)i.value=saved.workoutLimits[i.dataset.workoutParam];});if(saved.activities)jointActivities=saved.activities;syncJointMode();renderLockedDishes();await loadPlanningWeek();
  try{weekRecent=await api('planning/recent');const job=weekRecent.jobs.find(j=>['queued','running'].includes(j.state));if(job){weekPlanningJob=job.id;followPlanningJob(job.id);return;}
    const id=params.get('bozza')||saved.set;const recent=weekRecent.sets.find(s=>String(s.id)===String(id));if(recent){selectPlanningDate(recent.week_start);await showWeekSet(await api('plan-sets/'+id));await loadPlanningWeek();}
    const interrupted=weekRecent.jobs.find(j=>j.state==='failed');if(interrupted&&saved.job===interrupted.id){const err=JSON.parse(interrupted.error||'{}');$('week-warnings').append(element('p',err.detail||'Calcolo interrotto: i parametri della bozza sono conservati.','error'));}
  }catch(e){$('week-warnings').append(element('p','Non riesco a riprendere la bozza: '+e.message,'error'));}
}
async function showWeekSet(set){
  weekSet=set;weekCompare=[];$('week-review').hidden=true;
  renderWarnings($('week-warnings'),(set.warnings||[]).filter(w=>!['robustness_unavailable','robust_role_omitted','limited_alternatives'].includes(w.code)));
  if(set.kind==='joint')robustnessSummary(set);else $('week-robustness').replaceChildren();
  const context=$('week-draft-context');context.replaceChildren(element('h2','Proposte da confrontare'),element('p',planningKinds[set.kind||'week']+' · dal '+shortDate(set.week_start)+'. Il calendario cambia soltanto dopo “Applica”.','muted'));
  const meta=weekRecent?.sets.find(s=>String(s.id)===String(set.run_id));if(meta)context.append(element('p','Calcolata il '+new Date(meta.created*1000).toLocaleString('it-IT')+' · '+(meta.source.targets_demo?'obiettivi dimostrativi':'obiettivi del Profilo'),'muted small'));
  if(meta?.request.day_targets)context.append(element('p','Obiettivi usati nella bozza: riposo '+fmt0(meta.request.day_targets.rest.kcal_100g.target)+' kcal · allenamento '+fmt0(meta.request.day_targets.training.kcal_100g.target)+' kcal.','muted small'));
  if(meta?.request.energy_balance_target_kcal!=null)context.append(element('p','Bilancio usato nella bozza: '+balanceText(meta.request.energy_balance_target_kcal)+'.','muted small'));
  const comparison=element('div');comparison.id='week-comparison';context.append(comparison);
  const scale=Math.max(1,...set.plans.map(p=>p.robustness?.max_loss_kcal||0));
  $('week-plans').replaceChildren(...set.plans.map(p=>set.kind==='workout'?workoutPlanCard(p,set):weekPlanCard(p,set,scale)));
  if(!set.plans.length)$('week-warnings').append(element('p','Nessuna proposta rispetta questi vincoli. Modifica i parametri conservati e genera di nuovo.','error'));
  else if(set.plans.length===1)$('week-warnings').append(element('p','È disponibile una proposta: puoi esaminarla e applicarla.','notice'));
  if((!set.kind||set.kind==='week')&&set.plans.length)$('week-plans').append(moreAlternativesButton(set,showWeekSet));
  if(!mealRouteRestoring&&!$('planning').hidden)history.replaceState(null,'',planningHash());savePlanningConfig();
}
function toggleWeekCompare(p,set,button){if(weekSet?.run_id!==set.run_id)weekSet=set;const at=weekCompare.findIndex(x=>x.id===p.id);if(at>=0)weekCompare.splice(at,1);else{if(weekCompare.length>=3){$('week-warnings').append(element('p','Confronta al massimo tre proposte alla volta.','notice'));return;}weekCompare.push(p);}button.textContent=at>=0?'Confronta':'Togli dal confronto';renderWeekComparison();}
function renderWeekComparison(){const root=$('week-comparison');if(!root)return;root.replaceChildren();if(!weekCompare.length)return;root.append(element('h3','Confronto delle proposte'));const wrap=element('div',undefined,'comparison-scroll');const table=element('table',undefined,'week-comparison-table');const head=element('tr');head.append(element('th','Criterio'));weekCompare.forEach(p=>head.append(element('th',roleMeta[p.role]?.[0]||String(p.role||'Proposta '+p.id).replace(/^alternative_/,'Alternativa '))));table.append(head);
  const rows=[['Calorie medie',p=>p.days?.length?fmt0(p.days.reduce((n,d)=>n+(d.nutrients?.kcal||0),0)/p.days.length)+' kcal':'—'],['Allenamenti',p=>p.workout_sessions?String(p.workout_sessions.length):'Ambito alimentazione'],['Minuti di allenamento',p=>p.workout_sessions?fmt0(p.workout_sessions.reduce((n,s)=>n+(s.minutes||s.session?.duration_seconds/60||0),0))+' min':'—'],['Indice di varietà del modello',p=>p.objectives?.variety!=null?Math.round(p.objectives.variety*100)+'%':'Non disponibile'],['Peggior scostamento energetico',p=>p.robustness?.status==='available'?fmt0(p.robustness.max_loss_kcal)+' kcal/giorno':'Non valutato'],['Preparazione',p=>p.objectives?.prep_minutes!=null?fmt0(p.objectives.prep_minutes)+' min':'Non disponibile']];rows.forEach(([label,get])=>{const tr=element('tr');tr.append(element('th',label));weekCompare.forEach(p=>tr.append(element('td',get(p))));table.append(tr);});wrap.append(table);root.append(wrap,element('p','Criteri delle proposte effettivamente calcolate. I dettagli di alimenti e giorni restano nelle singole schede.','muted small'));}
async function followPlanningJob(id){
  const box=$('week-job');box.hidden=false;weekPlanningBusy=true;$('week-generate').disabled=true;$('week-start').disabled=true;
  const text=element('p','Calcolo della bozza in corso…','job-text');box.replaceChildren(element('div',undefined,'progress-indeterminate'),text);
  try{const job=await waitJob(id,s=>text.textContent='Calcolo della bozza in corso · '+s+' s');weekPlanningJob=null;weekRecent=await api('planning/recent');const set=await api('plan-sets/'+job.result.plan_set_id);selectPlanningDate(set.week_start);await showWeekSet(set);$('week-config').open=false;}
  catch(e){$('week-warnings').replaceChildren(element('p',e.message+' I parametri sono conservati.','error'),e.jobFailed?weekButton('Modifica i parametri conservati',()=>{$('week-config').open=true;$('week-config').scrollIntoView({block:'start'});}):weekButton('Controlla il calcolo',()=>followPlanningJob(id)));}
  finally{box.hidden=true;weekPlanningBusy=false;$('week-generate').disabled=false;$('week-start').disabled=false;savePlanningConfig();}
}
$('week-kind').onchange=()=>{syncJointMode();savePlanningConfig();};
$('week-config').addEventListener('input',savePlanningConfig);
$('week-generate').onclick=async()=>{
  if(weekPlanningBusy)return;const button=$('week-generate');button.disabled=true;$('week-warnings').replaceChildren();let body;
  try{const kind=$('week-kind').value;body=kind==='joint'?await jointRequest():kind==='workout'?{week_start:$('week-start').value,...readAvailability($('joint-availability')),...readWorkoutDraftLimits(),...(jointActivities?.length?{activities:jointActivities}:{}),demo:true}:{week_start:$('week-start').value,mode:$('week-mode').value,k:Number($('week-alternatives').value),pool_size:Number($('week-alternatives').value)};savePlanningConfig();const result=await api(kind==='joint'?'plans/joint-week':kind==='workout'?'workouts/week':'plans/week','POST',body);weekPlanningJob=result.job_id;savePlanningConfig();await followPlanningJob(result.job_id);}
  catch(e){$('week-warnings').replaceChildren(element('p',e.message,'error'));$('week-config').open=true;if(/colazione e spuntini/i.test(e.message))$('week-warnings').append(weekButton('Completa il Profilo',()=>document.querySelector('[data-page="profile"]').click()));}
  finally{button.disabled=false;}
};
async function openPlanReview(p,set){
  const root=$('week-review');root.hidden=false;root.replaceChildren(element('p','Preparo il riepilogo dell’applicazione…','muted'));root.scrollIntoView({block:'start'});
  try{const request={plan_id:p.id,scope:'week'};const review=await api('plan-sets/'+set.run_id+'/review','POST',request);root.replaceChildren();const h=element('h2','Prima di applicare');h.tabIndex=-1;root.append(h,element('p',planningKinds[set.kind||'week']+' · '+shortDate(set.week_start)+' – '+shortDate(addDays(set.week_start,6))),element('p','Verranno aggiornati '+review.meals.length+' pasti e '+review.sessions.length+(review.sessions.length===1?' giorno':' giorni')+' di attività. '+review.protected_meals.length+' pasti e '+review.protected_sessions.length+' giorni di attività protetti rimangono invariati. Gli obiettivi permanenti del Profilo rimangono invariati.'));
    const details=element('details');details.append(element('summary','Cosa cambia e cosa resta protetto'));const list=element('ul');review.meals.forEach(x=>list.append(element('li',shortDate(x.date)+' · '+mealMeta[x.slot][0]+': '+(x.action==='replace'?'sostituisce il previsto':'aggiunge al piano')+' · '+x.foods.join(', '))));review.protected_meals.forEach(x=>list.append(element('li',shortDate(x.date)+' · '+mealMeta[x.slot][0]+': protetto ('+(x.reason==='slot_locked'?'bloccato':'già registrato')+')')));review.sessions.forEach(x=>list.append(element('li',shortDate(x.date)+' · attività: '+x.before+' → '+x.after+' sessioni'+(x.titles.length?' · '+x.titles.join(', '):' · nessuna attività prevista'))));review.protected_sessions.forEach(x=>list.append(element('li',shortDate(x.date)+' · attività protetta: già avviata o registrata')));details.append(list);root.append(details);
    const actions=element('div',undefined,'meal-actions');const apply=weekButton('Applica '+(set.kind==='joint'?'dieta e allenamento':set.kind==='workout'?'solo allenamento':'solo alimentazione'),async()=>{actions.querySelectorAll('button').forEach(b=>b.disabled=true);try{const r=await api('plan-sets/'+set.run_id+'/apply','POST',{...request,review_token:review.review_token});document.querySelectorAll('[data-plan-id="'+p.id+'"]').forEach(card=>{if(!card.querySelector('.is-selected'))card.prepend(element('span','Applicata in precedenza','tag is-selected'));});root.replaceChildren(element('h2','Piano applicato'),element('p',r.applied_slots.length+(r.applied_slots.length===1?' elemento aggiornato':' elementi aggiornati')+' · '+r.skipped_slots.length+' protetti. Il calendario e la spesa usano ora il piano applicato.','notice'),weekButton('Torna alle proposte',()=>root.hidden=true));selectPlanningDate(set.week_start);await loadPlanningWeek();await refreshWeek();}catch(e){root.append(element('p',e.status?e.message:'Connessione non disponibile. Riprova l’applicazione; il doppio invio è gestito.','error'));actions.querySelectorAll('button').forEach(b=>b.disabled=false);}},'primary');actions.append(apply,weekButton('Torna al confronto',()=>{root.hidden=true;}));root.append(actions);h.focus();
  }catch(e){root.replaceChildren(element('p',e.message,'error'),weekButton('Torna ai parametri conservati',()=>{root.hidden=true;$('week-config').open=true;$('week-config').scrollIntoView({block:'start'});}));}
}

async function restorePlanningContext(params){
  const start=params.get('data'),id=params.get('bozza');
  if(start&&start!==$('week-start').value){selectPlanningDate(start);await changePlanningWeek();}
  if(id&&String(weekSet?.run_id)!==id){try{const set=await api('plan-sets/'+id);selectPlanningDate(set.week_start);await showWeekSet(set);await loadPlanningWeek();}catch(e){$('week-warnings').replaceChildren(element('p',e.message,'error'));}}
}

function readWorkoutDraftLimits(){const result={};document.querySelectorAll('[data-workout-param]').forEach(i=>{if(i.value===''||!i.checkValidity())throw Error('Completa i limiti di attività con valori validi.');result[i.dataset.workoutParam]=Number(i.value);});if(result.sessions_min>result.sessions_max||result.strength_sessions_min>result.strength_sessions_max||result.strength_sessions_min>result.sessions_max)throw Error('I minimi delle sessioni devono rientrare nei massimi.');return result;}

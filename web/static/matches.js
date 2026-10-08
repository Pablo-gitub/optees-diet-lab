// 8.12 — abbinamenti a scorrimento: pasti calcolati da Optees, mi piace / no / lo adoro / salta.
const matchSlots = { breakfast: 'Colazione', morning_snack: 'Metà mattina', lunch: 'Pranzo', afternoon_snack: 'Merenda', dinner: 'Cena' };
const matchVotes = {
  like: ['Mi piace', '✓', 'primary'],
  dislike: ['No', '✕', 'ghost'],
  love: ['Lo adoro', '♥', 'love'],
  skip: ['Salta', '↑', 'ghost'],
};
let matchState = { slot: 'lunch', dayType: 'rest', cards: [], index: 0, last: null, loading: false, status: null };

function renderMatches() {
  const root = $('matches-root');
  root.replaceChildren();
  const bar = element('div', undefined, 'match-controls');
  const slot = element('select');
  slot.setAttribute('aria-label', 'Pasto');
  Object.entries(matchSlots).forEach(([v, t]) => {
    const o = element('option', t);
    o.value = v;
    slot.append(o);
  });
  slot.value = matchState.slot;
  const day = element('div', undefined, 'segmented small-seg');
  [
    ['rest', 'Giorno di riposo'],
    ['training', '🏋 Giorno di palestra'],
  ].forEach(([v, t]) => {
    const b = element('button', t, 'seg' + (matchState.dayType === v ? ' active' : ''));
    b.type = 'button';
    b.setAttribute('aria-pressed', String(matchState.dayType === v));
    b.onclick = () => {
      matchState.dayType = v;
      loadDeck();
    };
    day.append(b);
  });
  slot.onchange = () => {
    matchState.slot = slot.value;
    loadDeck();
  };
  bar.append(slot, day);
  root.append(bar);
  const stage = element('div', undefined, 'match-stage');
  root.append(stage);
  if (matchState.loading) {
    const job = element('div', undefined, 'job');
    job.append(element('div', undefined, 'progress-indeterminate'), element('p', 'Optees compone i pasti sui tuoi obiettivi…', 'job-text'));
    stage.append(job);
  } else if (matchState.error) stage.append(element('p', matchState.error, 'error'));
  else {
    const card = matchState.cards[matchState.index];
    if (card) stage.append(matchCard(card));
    else if (matchState.cards.length) {
      const done = element('div', undefined, 'match-done');
      done.append(element('strong', 'Mazzo finito'), element('p', 'Le scelte entrano nella prossima settimana che generi.', 'muted'));
      const more = element('button', 'Altre proposte', 'primary');
      more.type = 'button';
      more.onclick = loadDeck;
      done.append(more);
      stage.append(done);
    } else if (matchState.status) stage.append(element('p', matchState.reason || 'Nessuna proposta per questo pasto.', 'notice'));
  }
  if (matchState.cards.length && matchState.index < matchState.cards.length) root.append(voteBar());
  if (matchState.reason && matchState.status === 'partial') root.append(element('p', 'Mazzo parziale: ' + matchState.reason, 'muted small'));
  root.append(matchQuestionsBox());
}

function matchCard(c) {
  const card = element('article', undefined, 'card match-card');
  card.tabIndex = 0;
  card.setAttribute('aria-label', 'Proposta ' + (matchState.index + 1) + ' di ' + matchState.cards.length);
  const head = element('div', undefined, 'match-head');
  head.append(element('span', (matchState.index + 1) + ' / ' + matchState.cards.length, 'muted small'));
  const chips = element('div', undefined, 'match-head-chips');
  if (c.exploration) chips.append(element('span', 'Novità', 'chip'));
  if (c.typical_dish) {
    const chip = element('span', '🍽 ' + c.typical_dish, 'chip match-typical-chip');
    chip.title = c.typical_dish;
    chips.append(chip);
  }
  head.append(chips);
  card.append(head);
  const list = element('ul', undefined, 'match-foods');
  c.foods.forEach((f) => {
    const li = element('li');
    if (f.image?.url) {
      const img = element('img', undefined, 'match-thumb');
      img.src = f.image.thumbnail_url || f.image.url;
      img.alt = '';
      img.loading = 'lazy';
      li.append(img);
    }
    li.append(element('span', f.brand ? f.name + ' · ' + f.brand : f.name, 'match-name'), element('strong', fmt0(f.grams) + ' g'));
    list.append(li);
  });
  card.append(list);
  const n = c.nutrients || {};
  card.append(element('p', fmt0(n.kcal) + ' kcal · P ' + fmt0(n.protein_g) + ' g · C ' + fmt0(n.carbs_available_g) + ' g · G ' + fmt0(n.fat_g) + ' g', 'match-macros'));
  const credits = c.foods.filter((f) => f.image?.attribution).map((f) => f.image.attribution);
  if (credits.length) card.append(element('p', 'Foto: ' + credits.join('; '), 'muted small'));
  const stamp = element('span', '', 'match-stamp');
  card.append(stamp);
  swipeable(card, stamp);
  card.onkeydown = (e) => {
    const k = { ArrowRight: 'like', ArrowLeft: 'dislike', ArrowUp: 'skip', l: 'love' }[e.key];
    if (k) {
      e.preventDefault();
      vote(k);
    }
  };
  setTimeout(() => card.focus({ preventScroll: true }), 0);
  return card;
}

function swipeable(card, stamp) {
  let start = null;
  card.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    start = { x: e.clientX, y: e.clientY };
    card.setPointerCapture(e.pointerId);
    card.classList.add('dragging');
  });
  card.addEventListener('pointermove', (e) => {
    if (!start) return;
    const dx = e.clientX - start.x,
      dy = e.clientY - start.y;
    card.style.transform = 'translate(' + dx + 'px,' + Math.min(dy, 0) + 'px) rotate(' + dx / 20 + 'deg)';
    const v = gesture(dx, dy);
    stamp.textContent = v ? matchVotes[v][0] : '';
    stamp.className = 'match-stamp' + (v ? ' show ' + v : '');
  });
  const end = (e) => {
    if (!start) return;
    const v = gesture(e.clientX - start.x, e.clientY - start.y);
    start = null;
    card.classList.remove('dragging');
    if (v) {
      card.classList.add('fly-' + v);
      setTimeout(() => vote(v), 180);
    } else {
      card.style.transform = '';
      stamp.className = 'match-stamp';
    }
  };
  card.addEventListener('pointerup', end);
  card.addEventListener('pointercancel', end);
}
function gesture(dx, dy) {
  if (dy < -90 && Math.abs(dy) > Math.abs(dx)) return 'skip';
  if (dx > 90) return 'like';
  if (dx < -90) return 'dislike';
  return null;
}

function voteBar() {
  const bar = element('div', undefined, 'match-votes');
  ['dislike', 'skip', 'love', 'like'].forEach((v) => {
    const [label, icon, cls] = matchVotes[v];
    const b = element('button', undefined, 'match-vote ' + cls);
    b.type = 'button';
    b.append(element('span', icon, 'mv-icon'), element('span', label, 'mv-label'));
    b.onclick = () => vote(v);
    bar.append(b);
  });
  const undo = element('button', '↶ Annulla', 'ghost small match-undo');
  undo.type = 'button';
  undo.disabled = !matchState.last;
  undo.onclick = undoVote;
  bar.append(undo);
  return bar;
}

async function vote(v) {
  const c = matchState.cards[matchState.index];
  if (!c || matchState.busy) return;
  matchState.busy = true;
  try {
    await api('matches/' + encodeURIComponent(c.id) + '/vote', 'POST', { vote: v });
    c.vote = v;
    matchState.last = c;
    matchState.index++;
    if (v === 'dislike') matchState.questions = null;
  } catch (e) {
    message(e.message);
  } finally {
    matchState.busy = false;
    renderMatches();
  }
}

async function undoVote() {
  const c = matchState.last;
  if (!c) return;
  try {
    await api('matches/' + encodeURIComponent(c.id) + '/vote', 'DELETE');
    matchState.index = Math.max(0, matchState.cards.indexOf(c));
    c.vote = null;
    matchState.last = null;
    matchState.questions = null;
  } catch (e) {
    message(e.status === 409 ? 'Si può annullare solo l’ultima scelta.' : e.message);
  }
  renderMatches();
}

async function loadDeck() {
  matchState = { ...matchState, cards: [], index: 0, last: null, loading: true, error: null, status: null, reason: null };
  renderMatches();
  try {
    const r = await api('matches/deck?slot=' + matchState.slot + '&day_type=' + matchState.dayType);
    matchState.cards = r.cards || [];
    matchState.status = r.status;
    matchState.reason = r.reason;
  } catch (e) {
    matchState.error = e.status === 409 && e.code === 'solver_busy' ? 'Optees sta già calcolando: riprova fra qualche secondo.' : e.message;
  } finally {
    matchState.loading = false;
    renderMatches();
  }
}

function matchQuestionsBox() {
  const box = element('div', undefined, 'match-questions');
  if (!matchState.questions) {
    api('matches/questions')
      .then((r) => {
        matchState.questions = r.questions || [];
        box.replaceWith(matchQuestionsBox());
      })
      .catch(() => {});
    return box;
  }
  matchState.questions.forEach((q) => {
    const row = element('div', undefined, 'notice match-question');
    const p = element('p');
    p.append(document.createTextNode('Hai scartato ' + q.discarded_cards + ' proposte con '), element('strong', q.name), document.createTextNode('. Vuoi escluderlo dai piani?'));
    row.append(p);
    const actions = element('div', undefined, 'meal-actions');
    [
      ['yes', 'Sì, escludilo', 'secondary small'],
      ['no', 'No, mi piace', 'ghost small'],
    ].forEach(([answer, text, cls]) => {
      const b = element('button', text, cls);
      b.type = 'button';
      b.onclick = async () => {
        try {
          const r = await api('matches/questions/' + encodeURIComponent(q.food.id) + '/answer', 'POST', { answer });
          message(r.excluded ? q.name + ' escluso dai piani.' : 'Ok, non te lo chiedo più per un po’.');
          matchState.questions = matchState.questions.filter((x) => x !== q);
          renderMatches();
        } catch (e) {
          message(e.message);
        }
      };
      actions.append(b);
    });
    row.append(actions);
    box.append(row);
  });
  return box;
}

function openMatches() {
  if (!matchState.cards.length && !matchState.loading) loadDeck();
  else renderMatches();
}

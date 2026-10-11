// Ricalibrazione dopo correzione del diario (scheda T-006):
// GET /api/progress/check-in/review
// POST /api/progress/check-in/review/dismiss
// POST /api/progress/check-in/review/recalculate

let checkinReviewData = null;

async function loadCheckinReview() {
  const container = $('checkin-review');
  if (!container) return;
  try {
    const review = await api('progress/check-in/review');
    checkinReviewData = review;
    if (!review || !review.checkin_date || !review.corrected || review.dismissed) {
      container.hidden = true;
      container.replaceChildren();
      return;
    }
    renderCheckinReviewPrompt(container, review);
  } catch {
    container.hidden = true;
    container.replaceChildren();
  }
}

async function loadCheckinReviewHint() {
  const container = $('checkin-review-hint');
  if (!container) return;
  try {
    const review = await api('progress/check-in/review');
    checkinReviewData = review;
    if (!review || !review.checkin_date || !review.corrected || review.dismissed) {
      container.hidden = true;
      container.replaceChildren();
      return;
    }
    renderCheckinReviewHint(container, review);
  } catch {
    container.hidden = true;
    container.replaceChildren();
  }
}

function renderCheckinReviewPrompt(container, review) {
  container.replaceChildren();

  const panel = element('div', undefined, 'panel checkin-review-panel');

  const dayLabel = typeof longDate === 'function' ? longDate(review.checkin_date) : review.checkin_date;
  const title = element('h3', 'Hai corretto pasti usati nel check-in di ' + dayLabel);
  const desc = element(
    'p',
    'Vuoi ricalibrare i giorni successivi? Se rispondi no, le correzioni restano nel diario e contano nei prossimi check-in.',
    'checkin-review-desc'
  );

  const actions = element('div', undefined, 'checkin-review-actions');

  const yesBtn = element('button', 'Sì, ricalibra', 'primary small');
  yesBtn.type = 'button';

  const noBtn = element('button', 'No', 'secondary small');
  noBtn.type = 'button';

  actions.append(yesBtn, noBtn);

  const errorBox = element('div', undefined, 'checkin-review-error');
  errorBox.hidden = true;

  const setBusy = (busy) => {
    yesBtn.disabled = busy;
    noBtn.disabled = busy;
  };

  const showError = (text, retryFn) => {
    errorBox.replaceChildren();
    errorBox.append(element('span', text || 'Operazione non riuscita: riprova.'));
    if (retryFn) {
      const retryBtn = element('button', 'Riprova', 'secondary small');
      retryBtn.type = 'button';
      retryBtn.onclick = () => {
        errorBox.hidden = true;
        errorBox.replaceChildren();
        retryFn();
      };
      errorBox.append(retryBtn);
    }
    errorBox.hidden = false;
  };

  const clearError = () => {
    errorBox.hidden = true;
    errorBox.replaceChildren();
  };

  yesBtn.onclick = async () => {
    setBusy(true);
    clearError();
    try {
      const res = await api('progress/check-in/review/recalculate', 'POST', { checkin_date: review.checkin_date });
      checkinReviewData = null;
      const hint = $('checkin-review-hint');
      if (hint) {
        hint.hidden = true;
        hint.replaceChildren();
      }
      container.replaceChildren(recalibrationBlock(res));
      container.hidden = false;
    } catch (err) {
      setBusy(false);
      showError(err.message, () => yesBtn.onclick());
    }
  };

  noBtn.onclick = async () => {
    setBusy(true);
    clearError();
    try {
      await api('progress/check-in/review/dismiss', 'POST', { checkin_date: review.checkin_date });
      checkinReviewData = null;
      container.hidden = true;
      container.replaceChildren();
      const hint = $('checkin-review-hint');
      if (hint) {
        hint.hidden = true;
        hint.replaceChildren();
      }
      message('Va bene: le correzioni restano per i prossimi calcoli.');
    } catch (err) {
      setBusy(false);
      showError(err.message, () => noBtn.onclick());
    }
  };

  panel.append(title, desc, actions, errorBox);
  container.append(panel);
  container.hidden = false;
}

function renderCheckinReviewHint(container, review) {
  container.replaceChildren();

  const banner = element('div', undefined, 'pending-banner checkin-review-hint-banner');
  const bar = element('div', undefined, 'pending-bar checkin-review-hint-bar');

  const left = element('div', undefined, 'pending-bar-left checkin-review-hint-left');
  const dot = element('span', '●', 'pending-dot');
  dot.setAttribute('aria-hidden', 'true');
  const summary = element('span', 'Hai corretto pasti del check-in: vuoi ricalibrare?', 'pending-summary');
  left.append(dot, summary);

  const right = element('div', undefined, 'checkin-review-hint-right');
  const openBtn = element('button', 'Apri', 'secondary small checkin-review-open-btn');
  openBtn.type = 'button';
  openBtn.setAttribute('aria-label', 'Apri la ricalibrazione in Progressi');

  // Wait for the page switch (it scrolls to the top) and the panel refresh, then bring it into view.
  const goToReview = async () => {
    const navBtn = document.querySelector('[data-page="progress"]');
    if (navBtn) await navBtn.onclick();
    // The page handler does not wait for its data: load it here so the layout is stable before scrolling.
    if (typeof loadProgress === 'function') await loadProgress().catch(() => {});
    await loadCheckinReview();
    const target = $('checkin-review');
    if (!target || target.hidden) return;
    target.scrollIntoView({ block: 'center' });
    const focusTarget = target.querySelector('button');
    if (focusTarget) focusTarget.focus({ preventScroll: true });
  };

  openBtn.onclick = (e) => {
    e.stopPropagation();
    goToReview();
  };
  left.onclick = () => goToReview();
  left.style.cursor = 'pointer';

  right.append(openBtn);
  bar.append(left, right);
  banner.append(bar);
  container.append(banner);
  container.hidden = false;
}

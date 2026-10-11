// Banner «pasti da confermare» in Oggi (scheda T-002): GET /api/diary/pending, POST /api/diary/confirm-all.

let pendingData = null;
let pendingIsOpen = false;

function getDismissedKeys() {
  try {
    const key = 'diet-pending-dismissed:' + (profile?.display_name || 'default');
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function setDismissedKeys(keys) {
  try {
    const key = 'diet-pending-dismissed:' + (profile?.display_name || 'default');
    localStorage.setItem(key, JSON.stringify(keys));
  } catch {}
}

function dismissPendingBanner() {
  const allKeys = [];
  if (pendingData?.days) {
    for (const d of pendingData.days) {
      for (const m of d.meals) {
        allKeys.push(d.date + ':' + m.slot);
      }
    }
  }
  setDismissedKeys(allKeys);
  pendingIsOpen = false;
  const container = $('pending-meals');
  if (container) container.hidden = true;
}

function setPendingBusy(busy) {
  const container = $('pending-meals');
  if (!container) return;
  container.querySelectorAll('button').forEach((b) => {
    b.disabled = busy;
  });
}

function showPendingError(text, retryFn) {
  const box = $('pending-error');
  if (!box) return;
  box.replaceChildren();
  box.append(element('p', text, 'pending-error-text'));
  if (retryFn) {
    const retryBtn = element('button', 'Riprova', 'secondary small');
    retryBtn.type = 'button';
    retryBtn.onclick = () => {
      box.hidden = true;
      box.replaceChildren();
      retryFn();
    };
    box.append(retryBtn);
  }
  box.hidden = false;
}

function clearPendingError() {
  const box = $('pending-error');
  if (box) {
    box.hidden = true;
    box.replaceChildren();
  }
}

function showPendingNotice(text) {
  const box = $('pending-notice');
  if (box) {
    box.textContent = text;
    box.hidden = false;
  }
}

function clearPendingNotice() {
  const box = $('pending-notice');
  if (box) {
    box.textContent = '';
    box.hidden = true;
  }
}

function removePendingMeal(date, slot) {
  if (!pendingData || !pendingData.days) return;
  const day = pendingData.days.find((d) => d.date === date);
  if (day) {
    day.meals = day.meals.filter((m) => m.slot !== slot);
    if (day.meals.length === 0) {
      pendingData.days = pendingData.days.filter((d) => d.date !== date);
    }
  }
  pendingData.count = Math.max(0, (pendingData.count || 1) - 1);
}

async function goToMealDay(date, slot) {
  homeDate = date;
  history.pushState(null, '', '#oggi?data=' + homeDate);
  await loadHome();
  const card = document.querySelector('[data-meal-slot="' + slot + '"]');
  if (card) {
    if (card.tagName === 'DETAILS') card.open = true;
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    const target = card.querySelector('summary, h3');
    if (target) {
      if (target.tagName === 'H3') target.tabIndex = -1;
      target.focus();
    }
  }
}

async function confirmSinglePendingMeal(date, slot) {
  setPendingBusy(true);
  clearPendingError();
  clearPendingNotice();
  try {
    const revision = currentDay?.date === date ? currentDay.meals.find((m) => m.slot === slot)?.revision : undefined;
    const body = { date, slot };
    if (revision !== undefined) body.revision = revision;
    const updatedDay = await api('diary/confirm', 'POST', body);
    if (homeDate === date) {
      renderDay(updatedDay);
      refreshWeek();
    }
    removePendingMeal(date, slot);
    if (!pendingData || pendingData.count === 0) {
      const container = $('pending-meals');
      if (container) container.hidden = true;
      pendingIsOpen = false;
    } else {
      renderPendingBanner();
    }
  } catch (e) {
    showPendingError('Operazione non riuscita: ' + e.message, () => confirmSinglePendingMeal(date, slot));
  } finally {
    setPendingBusy(false);
  }
}

async function confirmAllPendingMeals() {
  const mealsToConfirm = [];
  if (pendingData?.days) {
    for (const d of pendingData.days) {
      for (const m of d.meals) {
        mealsToConfirm.push({ date: d.date, slot: m.slot });
      }
    }
  }
  if (!mealsToConfirm.length) return;
  setPendingBusy(true);
  clearPendingError();
  clearPendingNotice();
  try {
    const result = await api('diary/confirm-all', 'POST', { meals: mealsToConfirm });
    pendingData = result.pending;
    if (!pendingData || pendingData.count === 0) {
      const container = $('pending-meals');
      if (container) container.hidden = true;
      pendingIsOpen = false;
    } else {
      renderPendingBanner();
    }
    await loadHome();
    if (result.skipped && result.skipped.length > 0) {
      const n = result.skipped.length;
      const text = n === 1 ? '1 pasto era già stato registrato.' : n + ' pasti erano già stati registrati.';
      if (typeof message === 'function') message(text);
      showPendingNotice(text);
    }
  } catch (e) {
    showPendingError('Operazione non riuscita: ' + e.message, () => confirmAllPendingMeals());
  } finally {
    setPendingBusy(false);
  }
}

function openPendingDropdown() {
  pendingIsOpen = true;
  const dropdown = $('pending-dropdown');
  if (dropdown) dropdown.hidden = false;
  const toggleBtn = $('pending-toggle-btn');
  if (toggleBtn) {
    toggleBtn.textContent = '⌃';
    toggleBtn.setAttribute('aria-expanded', 'true');
    toggleBtn.setAttribute('aria-label', 'Nascondi i pasti da confermare');
  }
}

function closePendingDropdown() {
  pendingIsOpen = false;
  const dropdown = $('pending-dropdown');
  if (dropdown) dropdown.hidden = true;
  const toggleBtn = $('pending-toggle-btn');
  if (toggleBtn) {
    toggleBtn.textContent = '⌄';
    toggleBtn.setAttribute('aria-expanded', 'false');
    toggleBtn.setAttribute('aria-label', 'Mostra i pasti da confermare');
  }
}

function togglePendingDropdown() {
  if (pendingIsOpen) closePendingDropdown();
  else openPendingDropdown();
}

function renderPendingBanner() {
  const container = $('pending-meals');
  if (!container || !pendingData || pendingData.count === 0) {
    if (container) container.hidden = true;
    return;
  }
  container.replaceChildren();

  const banner = element('div', undefined, 'pending-banner');

  // Bar
  const bar = element('div', undefined, 'pending-bar');
  const barLeft = element('div', undefined, 'pending-bar-left');
  barLeft.onclick = () => togglePendingDropdown();

  const dot = element('span', '●', 'pending-dot');
  dot.setAttribute('aria-hidden', 'true');

  const count = pendingData.count;
  const countText = count === 1 ? 'Hai 1 pasto da confermare' : 'Hai ' + count + ' pasti da confermare';
  const summary = element('span', countText, 'pending-summary');
  barLeft.append(dot, summary);

  const barRight = element('div', undefined, 'pending-bar-right');

  const toggleBtn = element('button', pendingIsOpen ? '⌃' : '⌄', 'pending-toggle');
  toggleBtn.id = 'pending-toggle-btn';
  toggleBtn.type = 'button';
  toggleBtn.setAttribute('aria-expanded', pendingIsOpen ? 'true' : 'false');
  toggleBtn.setAttribute('aria-controls', 'pending-dropdown');
  toggleBtn.setAttribute('aria-label', pendingIsOpen ? 'Nascondi i pasti da confermare' : 'Mostra i pasti da confermare');
  toggleBtn.onclick = (e) => {
    e.stopPropagation();
    togglePendingDropdown();
  };

  const dismissBtn = element('button', '✕', 'pending-dismiss');
  dismissBtn.id = 'pending-dismiss-btn';
  dismissBtn.type = 'button';
  dismissBtn.setAttribute('aria-label', 'Nascondi');
  dismissBtn.onclick = (e) => {
    e.stopPropagation();
    dismissPendingBanner();
  };

  barRight.append(toggleBtn, dismissBtn);
  bar.append(barLeft, barRight);
  banner.append(bar);

  // Dropdown
  const dropdown = element('div', undefined, 'pending-dropdown');
  dropdown.id = 'pending-dropdown';
  dropdown.hidden = !pendingIsOpen;

  const todayStr = isoDate(new Date());
  const yesterdayStr = addDays(todayStr, -1);

  (pendingData.days || []).forEach((day) => {
    const group = element('div', undefined, 'pending-day-group');
    const dayLabelText = day.date === yesterdayStr ? 'IERI' : longDate(day.date).toUpperCase();
    group.append(element('div', dayLabelText, 'pending-day-title'));

    day.meals.forEach((meal) => {
      const row = element('div', undefined, 'pending-meal-row');

      const info = element('div', undefined, 'pending-meal-info');
      const mealNameStr = mealMeta[meal.slot]?.[0] || meal.slot;
      const nameBtn = element('button', mealNameStr, 'pending-meal-name');
      nameBtn.type = 'button';
      nameBtn.title = 'Vai a ' + mealNameStr + ' del ' + shortDate(day.date);
      nameBtn.onclick = () => goToMealDay(day.date, meal.slot);

      const kcalStr = (meal.kcal != null ? fmt0(meal.kcal) : '0') + ' kcal';
      const foodNames = (meal.items || []).map((i) => i.name || i.food?.name || i.food?.id || '').filter(Boolean);
      const foodsStr = foodNames.slice(0, 3).join(', ') + (foodNames.length > 3 ? '…' : '');

      const metaSpan = element('span', ' · ' + kcalStr, 'pending-meal-meta');
      const foodsSpan = element('span', foodsStr, 'pending-meal-foods');
      info.append(nameBtn, metaSpan, foodsSpan);

      const action = element('div', undefined, 'pending-meal-action');
      const confirmBtn = element('button', 'Conferma', 'secondary small pending-confirm-btn');
      confirmBtn.type = 'button';
      confirmBtn.onclick = () => confirmSinglePendingMeal(day.date, meal.slot);
      action.append(confirmBtn);

      row.append(info, action);
      group.append(row);
    });

    dropdown.append(group);
  });

  const footer = element('div', undefined, 'pending-footer');
  const confirmAllBtn = element('button', 'Conferma tutti', 'primary small pending-confirm-all-btn');
  confirmAllBtn.type = 'button';
  confirmAllBtn.onclick = () => confirmAllPendingMeals();
  footer.append(confirmAllBtn);
  dropdown.append(footer);

  const notice = element('p', undefined, 'pending-notice-box');
  notice.id = 'pending-notice';
  notice.hidden = true;
  dropdown.append(notice);

  banner.append(dropdown);

  const errorBox = element('div', undefined, 'pending-error-box');
  errorBox.id = 'pending-error';
  errorBox.hidden = true;
  banner.append(errorBox);

  container.append(banner);
}

async function loadPendingBanner() {
  const container = $('pending-meals');
  if (!container) return;
  try {
    const data = await api('diary/pending');
    pendingData = data;
    if (!data || data.count === 0 || !data.days || data.days.length === 0) {
      container.hidden = true;
      return;
    }
    const dismissed = getDismissedKeys();
    const dismissedSet = new Set(dismissed);
    const allKeys = [];
    for (const d of data.days) {
      for (const m of d.meals) {
        allKeys.push(d.date + ':' + m.slot);
      }
    }
    const hasUndismissed = allKeys.some((k) => !dismissedSet.has(k));
    if (!hasUndismissed) {
      container.hidden = true;
      return;
    }
    renderPendingBanner();
    container.hidden = false;
  } catch {
    container.hidden = true;
  }
}

// Escape keyboard handling: closes dropdown and restores focus to toggle button
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && pendingIsOpen) {
    closePendingDropdown();
    const toggleBtn = $('pending-toggle-btn');
    if (toggleBtn) toggleBtn.focus();
  }
});

// 8.10 — codice a barre: ricerca nel catalogo locale e registrazione dall'etichetta.
// The camera needs a secure context (HTTPS); without it the code is typed or read from a photo.

const barcodeFormats = ['ean_13', 'ean_8', 'upc_a', 'upc_e'];
const labelBases = [
  ['per_100g', 'per 100 g'],
  ['per_serving', 'per porzione'],
  ['per_100ml', 'per 100 ml'],
];

function barcodeDetector() {
  try {
    return 'BarcodeDetector' in window ? new BarcodeDetector({ formats: barcodeFormats }) : null;
  } catch {
    return null;
  }
}

// onFood(food, grams) receives a search-like food object and the suggested quantity.
function barcodeBox(onFood) {
  const box = element('div', undefined, 'barcode-box');
  const row = element('div', undefined, 'barcode-row');
  const code = element('input');
  code.inputMode = 'numeric';
  code.autocomplete = 'off';
  code.placeholder = 'Cifre sotto il codice a barre';
  code.setAttribute('aria-label', 'Codice a barre');
  const find = element('button', 'Cerca', 'secondary small');
  find.type = 'button';
  row.append(code);
  const detector = barcodeDetector();
  if (detector) {
    if (window.isSecureContext && navigator.mediaDevices?.getUserMedia) {
      const live = element('button', '📷 Inquadra', 'ghost small');
      live.type = 'button';
      live.onclick = () => scanLive(detector, box, (value) => ((code.value = value), lookup()));
      row.append(live);
    }
    const photo = element('label', '🖼 Foto', 'ghost small file-button');
    const file = element('input');
    file.type = 'file';
    file.accept = 'image/*';
    file.capture = 'environment';
    file.onchange = async () => {
      if (!file.files[0]) return;
      try {
        const found = await detector.detect(await createImageBitmap(file.files[0]));
        if (!found.length) return status.replaceChildren(element('p', 'Nessun codice leggibile nella foto: riprova più vicino o scrivi le cifre.', 'muted'));
        code.value = found[0].rawValue;
        lookup();
      } catch (e) {
        status.replaceChildren(element('p', 'Foto non leggibile: scrivi le cifre.', 'muted'));
      }
      file.value = '';
    };
    photo.append(file);
    row.append(photo);
  }
  row.append(find);
  const status = element('div', undefined, 'barcode-status');
  if (!detector) status.append(element('p', 'Questo browser non legge i codici dalla fotocamera: scrivi le cifre stampate sotto le barre.', 'muted small'));
  box.append(row, status);

  async function lookup() {
    const value = code.value.replace(/\s+/g, '');
    if (!/^\d{8}$|^\d{12,14}$/.test(value)) return status.replaceChildren(element('p', 'Un codice a barre ha 8, 12, 13 o 14 cifre.', 'error'));
    status.replaceChildren(element('p', 'Cerco ' + value + '…', 'muted'));
    try {
      const r = await api('foods/barcode/' + value);
      if (r.status === 'found') return status.replaceChildren(foundCard(r, onFood));
      status.replaceChildren(
        element('p', r.status === 'incomplete' ? 'Prodotto trovato ma senza valori completi: completali dall’etichetta.' : 'Prodotto non presente: registralo dall’etichetta, la prossima volta lo troverai subito.', 'notice'),
        labelForm(value, r, onFood),
      );
    } catch (e) {
      status.replaceChildren(element('p', e.message, 'error'));
    }
  }
  find.onclick = lookup;
  code.onkeydown = (e) => e.key === 'Enter' && (e.preventDefault(), lookup());
  return box;
}

function foundCard(r, onFood) {
  const f = r.food;
  const card = element('div', undefined, 'barcode-found');
  const v = f.per_100g;
  card.append(element('strong', f.name), element('span', [f.brand, f.source_label].filter(Boolean).join(' · '), 'muted'));
  card.append(element('p', fmt0(v.kcal) + ' kcal · P ' + fmt0(v.protein_g) + ' g · C ' + fmt0(v.carbs_available_g) + ' g · G ' + fmt0(v.fat_g) + ' g per 100 g', 'small'));
  const row = element('div', undefined, 'meal-actions');
  const grams = element('input');
  grams.type = 'number';
  grams.min = '1';
  grams.step = '1';
  grams.value = r.serving_g || 100;
  grams.className = 'grams-input';
  grams.setAttribute('aria-label', 'Grammi');
  const add = element('button', 'Aggiungi', 'primary small');
  add.type = 'button';
  add.onclick = () => {
    const g = Number(grams.value);
    if (!(g > 0)) return message('Indica i grammi');
    onFood(f, Math.round(g));
  };
  row.append(grams, element('span', 'g' + (r.serving_g ? ' (1 porzione = ' + fmt0(r.serving_g) + ' g)' : ''), 'muted'), add);
  card.append(row);
  return card;
}

function labelField(form, name, label, opts = {}) {
  const wrap = element('label', undefined, 'label-field');
  const input = element('input');
  input.name = name;
  input.type = opts.type || 'number';
  if (input.type === 'number') {
    input.min = '0';
    input.step = 'any';
    input.inputMode = 'decimal';
  }
  if (opts.required) input.required = true;
  if (opts.value != null) input.value = opts.value;
  wrap.append(element('span', label), input);
  form.append(wrap);
  return wrap;
}

function labelForm(barcode, prior, onFood) {
  const form = element('form', undefined, 'label-form');
  const known = prior.food || {};
  form.append(element('p', 'Copia i valori dalla tabella nutrizionale della confezione.', 'muted small'));
  labelField(form, 'name', 'Nome', { type: 'text', required: true, value: known.name });
  labelField(form, 'brand', 'Marca', { type: 'text', value: known.brand });
  const basisWrap = element('fieldset', undefined, 'label-basis');
  basisWrap.append(element('legend', 'I valori sono'));
  labelBases.forEach(([value, text], i) => {
    const l = element('label');
    const r = element('input');
    r.type = 'radio';
    r.name = 'basis';
    r.value = value;
    r.checked = i === 0;
    l.append(r, document.createTextNode(' ' + text));
    basisWrap.append(l);
  });
  form.append(basisWrap);
  const serving = labelField(form, 'serving_g', 'Peso della porzione (g)');
  const density = labelField(form, 'density_g_per_ml', 'Densità (g/ml, facoltativa)');
  const sync = () => {
    const b = form.elements.basis.value;
    serving.hidden = b !== 'per_serving';
    serving.querySelector('input').required = b === 'per_serving';
    density.hidden = b !== 'per_100ml';
  };
  basisWrap.onchange = sync;
  sync();
  const energy = element('div', undefined, 'label-energy');
  form.append(energy);
  labelField(energy, 'kcal', 'Energia (kcal)');
  labelField(energy, 'kj', 'oppure kJ');
  labelField(form, 'protein_g', 'Proteine (g)', { required: true });
  labelField(form, 'carbs_g', 'Carboidrati (g)', { required: true });
  labelField(form, 'fat_g', 'Grassi (g)', { required: true });
  const more = element('details', undefined, 'label-more');
  more.append(element('summary', 'Facoltativi: fibre, zuccheri, sale, confezione'));
  labelField(more, 'fiber_g', 'Fibre (g)');
  labelField(more, 'sugars_g', 'di cui zuccheri (g)');
  labelField(more, 'salt_g', 'Sale (g)');
  labelField(more, 'package_g', 'Peso della confezione (g)');
  form.append(more);
  const out = element('div');
  const save = element('button', 'Salva il prodotto', 'primary small');
  save.type = 'submit';
  form.append(save, out);
  form.onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const body = { barcode, basis: fd.get('basis') };
    for (const [k, v] of fd.entries()) {
      if (k === 'basis' || v === '') continue;
      body[k] = k === 'name' || k === 'brand' ? String(v).trim() : Number(v);
    }
    if (body.basis !== 'per_serving') delete body.serving_g;
    if (body.basis !== 'per_100ml') delete body.density_g_per_ml;
    if (body.kcal == null && body.kj == null) return out.replaceChildren(element('p', 'Serve l’energia: kcal oppure kJ.', 'error'));
    if (body.kcal != null) delete body.kj;
    save.disabled = true;
    try {
      const r = await api('foods/personal', 'POST', body);
      out.replaceChildren(savedSummary(r, onFood));
      form.querySelectorAll('input, button[type=submit]').forEach((x) => (x.disabled = true));
    } catch (err) {
      out.replaceChildren(element('p', err.code === 'duplicate_barcode' ? 'Hai già registrato un prodotto con questo codice.' : err.message, 'error'));
      save.disabled = false;
    }
  };
  return form;
}

function savedSummary(r, onFood) {
  const box = element('div', undefined, 'label-saved');
  const c = r.coherence || {};
  if (c.ok === false)
    box.append(
      element(
        'p',
        'Le calorie non tornano con proteine, carboidrati e grassi (dichiarate ' + fmt0(c.declared_kcal) + ' kcal, attese circa ' + fmt0(c.expected_kcal) + '): controlla l’etichetta. Il prodotto è salvato ma il pianificatore non lo userà finché non lo correggi.',
        'notice warn',
      ),
    );
  const v = r.per_100g || {};
  if (v.kcal == null) {
    box.append(element('p', 'Salvato con i valori per 100 ml. Senza densità non si può pesare in grammi: aggiungila per usarlo nel diario.', 'notice'));
    return box;
  }
  box.append(element('p', 'Salvato. Per 100 g: ' + fmt0(v.kcal) + ' kcal · P ' + fmt0(v.protein_g) + ' g · C ' + fmt0(v.carbs_available_g) + ' g · G ' + fmt0(v.fat_g) + ' g', 'small'));
  const food = { food: r.food, name: r.label?.name, brand: r.label?.brand, source_label: 'etichetta personale', per_100g: v, unit_g: null };
  box.append(foundCard({ food, serving_g: r.serving_g }, onFood));
  return box;
}

async function scanLive(detector, box, onCode) {
  const panel = element('div', undefined, 'scan-live');
  const video = element('video');
  video.muted = true;
  video.playsInline = true;
  video.setAttribute('playsinline', '');
  const stop = element('button', 'Chiudi', 'ghost small');
  stop.type = 'button';
  panel.append(video, stop);
  box.prepend(panel);
  let stream;
  let running = true;
  const end = () => {
    running = false;
    stream?.getTracks().forEach((t) => t.stop());
    panel.remove();
  };
  stop.onclick = end;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
    video.srcObject = stream;
    await video.play();
    while (running) {
      const found = await detector.detect(video).catch(() => []);
      if (found.length) {
        end();
        return onCode(found[0].rawValue);
      }
      await new Promise((r) => setTimeout(r, 250));
    }
  } catch (e) {
    end();
    message('Fotocamera non disponibile: scrivi le cifre o usa una foto.');
  }
}

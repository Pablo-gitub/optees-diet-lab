# Audit backend 8.12 — 2026-10-07

Suite completa: 345 test verdi (278,193 s); database temporanei e profili sintetici.
Prova HTTP con il vero server MCP Optees locale: 200, 10 schede per pranzo/riposo,
54 combinazioni candidate, 10 solve verificati, 100% esplorazione, 4,90 s.
`pool.certified=false`: il mazzo si ferma a dieci, non certifica l’esaurimento.
La verifica indipendente di ogni risultato precede la persistenza della scheda.

Test: target/grammi, id riproducibili, esclusioni, isolamento utenti, CSRF,
annullamento ultima scelta, salta senza ricompensa, domanda esplicita/silenzio
60 giorni, rapporti ±30%, premio doppio love, limite settimanale due, immagini
solo con licenza e attribuzione. Voti delle schede separati dalle prove del bandit.

Gli schemi legacy di colazione/spuntini hanno un solo componente: sono rispettati
senza inventare alimenti o dieci combinazioni. Risposta partial/unavailable se
il catalogo ammesso non offre dieci nuove schede fattibili. Gli abbinamenti
culinari proposti esternamente attendono revisione: il premio si applica solo
alle voci con reviewed=true in config/meal-matches.json.

Nessuna modifica a web/static/ o ai dati personali.

## Integrazione del catalogo tipico — 2026-10-07

Catalogo locale: 51 abbinamenti della proposta Gemini, con revisione rintracciabile in `docs/ingredient-proposals-log.md`. Identità esatta dei principali (oli esclusi) necessaria per esporre il nome del piatto; identità per categorie usata soltanto nell'ordinamento. Entrambi i pesi sono letti dalla configurazione. Strutture tipiche aggiuntive di colazione/spuntini solo nella modalità libera. Cache azzerabile esplicitamente e restituzione di copie per impedire modifiche accidentali. File assente, JSON invalido o struttura invalida producono un errore di dominio leggibile.

Verifica: 12 test mirati verdi, inclusi quattro test dedicati al caricamento/cache/errori, identità/categorie/pesi e strutture dei pasti. Nessuna modifica alla UI.

Suite completa: **362 test verdi** (292,599 s), database temporanei.

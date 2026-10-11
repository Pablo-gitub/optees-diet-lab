# T-007 · Diagnosi della varietà: perché le alternative condividono il 60–80% e quali leve la abbassano

**Per Codex.** Autore della scheda: Claude · Data: 2026-10-11 · Tappa del piano: 3
Esecutore: Codex (analisi del solver; nessuna modifica di produzione) · Revisore: Claude

## Obiettivo

Un rapporto che spieghi, per categoria di alimento e per vincolo, da dove viene la sovrapposizione fra le alternative settimanali e che **classifichi le leve** per avvicinarsi al 90% di diversità chiesto dal proprietario, con l'effetto misurato o stimato di ciascuna. Nessuna modifica al solver in questa scheda: le leve scelte diventeranno schede successive.

## Contesto

- Richiesta del proprietario: almeno 3 alternative con circa il 90% di ingredienti principali diversi (condimenti esclusi), «Calcolane altre», massima variazione possibile entro i vincoli delle sue diete (banana, barrette, abitudini). Varietà come obiettivo con ripiego, non vincolo rigido (guida v2.1).
- Già misurato in [phase8-diversity-audit.md](../phase8-diversity-audit.md): sovrapposizione massima fra le alternative **59–80%** (demo libera, diete sedentaria e palestra); il 10% di sovrapposizione non è raggiunto. Prova B16: il dominio libero ha **2 soli frutti** per 14 porzioni settimanali, quindi il minimo teorico è ≥ 10,87% anche con tempo illimitato; conclusione: «servirà ampliare i candidati della formulazione».
- Identità conservative (`ingredient_overlap.canonical`): per esempio tutte le voci `vegetable` condividono la stessa identità; marche non associate → `unclassified_product`.
- Ricette pronte nel catalogo: circa 34 (dopo T-001 della Tappa 1 solo queste sono in Cucina).
- Strumento esistente: `scripts/audit_ingredient_overlap.py` (solo aggregati, nessun database personale, HiGHS diagnostico).

## Domande a cui rispondere

1. **Scomposizione della sovrapposizione** per ciascuno scenario dell'audit: quota di grammi condivisi per categoria (frutta, verdura, amidi, proteine animali, proteine vegetali, latticini, colazione/spuntini fissi, ricette) e per pasto. Quale categoria pesa di più.
2. **Limite inferiore teorico** per scenario dato il dominio attuale (come in B16, ma per categoria): quanto della sovrapposizione è **inevitabile** con i candidati di oggi, quanto dipende da tempo di calcolo o ordine di ricerca.
3. **Vincoli che legano** di più: abitudini fisse (banana, barrette, frutto pomeridiano), frequenze proteiche, abbinamenti obbligati, porzioni a passi, pasti fissati. Quanto cambia la sovrapposizione rilassandoli uno alla volta **solo nell'esperimento** (mai in produzione).
4. **Leve candidate**, ciascuna con effetto misurato sull'audit (o stima motivata se troppo costosa da misurare) e costo stimato:
   - più frutti, verdure, amidi, proteine tra i candidati (quali e quanti servirebbero, dal catalogo CREA/OFF già presente);
   - identità più fini per le verdure (es. sottogruppi) senza inventare diversità;
   - ricette pronte come candidati della settimana;
   - colazione/spuntini con più varianti rispetto alle abitudini fisse;
   - eventuali altre leve emerse.
5. **Raccomandazione**: le 2–3 leve con il miglior rapporto effetto/costo, ordinate, con l'obiettivo realistico raggiungibile per ciascuno scenario (es. «≤ 35% con le leve A+B»).

## Vincoli

- Nessuna modifica a `scripts/` di produzione, a `web/`, ai profili o al database personale; nessun dato personale nel rapporto (solo profili sintetici o pubblici come nell'audit esistente).
- Gli esperimenti di rilassamento sono locali allo script di audit e dichiarati nel rapporto.
- Solver diagnostico come nell'audit esistente; dichiarare budget di tempo e stato di certificazione di ogni numero.
- Nessun download.

## Consegna

- `docs/variety-diagnosis.md`: risposte 1–5, tabelle, comandi per riprodurre, limiti dell'analisi.
- Estensioni allo script di audit (o un nuovo script diagnostico) per la scomposizione per categoria e gli esperimenti.
- Suite completa verde.

## Criteri di accettazione

- [ ] Per ogni scenario dell'audit: scomposizione per categoria che somma alla sovrapposizione misurata (entro l'arrotondamento).
- [ ] Limite inferiore teorico per scenario, con il ragionamento esplicito.
- [ ] Almeno quattro leve con effetto misurato o stimato e costo; raccomandazione ordinata.
- [ ] Ogni numero riporta budget e certificazione; nessun numero da dati personali.
- [ ] Nessun file di produzione modificato (`check_task` lo verifica).

## Base

```
8d7a56b1c80d542bc0e92c4cbec79009060da9a1
```

## File consentiti

```
docs/variety-diagnosis.md
scripts/audit_ingredient_overlap.py
scripts/diagnose_variety.py
```

## Test protetti

```
tests/test_ingredient_overlap.py
tests/test_week_orchestration.py
tests/test_plan_set_alternatives.py
```

## Test aggiuntivi consentiti

```
```

## Comando di test

```
set -a; . ./.env; set +a; PYTHONPATH=scripts:tests:. ${DIET_PYTHON:-python} -m unittest test_ingredient_overlap test_week_orchestration test_plan_set_alternatives -q
```

## Resoconto

<!-- Codex -->

## Revisione

<!-- Claude -->

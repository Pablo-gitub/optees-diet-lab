# Tracce CREA · T-008

Import offline del 12 ottobre 2026. Nessun download e nessun dato personale. Presenti le 832 pagine alimentari dell’indice e le tre pagine di contesto; tutte rilette dalla cache locale. `raw_sha256` di ciascuna scheda invariato: il dato grezzo non è stato modificato.

## Regola e provenienza

La legenda locale distingue «0 nutriente assente» da «tr nutriente presente in tracce». Solo il simbolo `tr`, ignorando maiuscole/spazi esterni, viene rappresentato numericamente come `0.0` per il solver, secondo il contratto della scheda. Non si afferma che la quantità fisica sia assente. Celle vuote, `n.d.`, trattini e altri simboli rimangono `None` nel JSON e vuoti nel CSV.

Il JSON mantiene `value_100g_raw` e aggiunge `value_100g_provenance: "tracce (tr) nel CREA"` soltanto alle righe con tracce. Ogni alimento elenca `trace_nutrients`; la stessa nuova colonna CSV contiene un array JSON dei nomi di campo (`[]` se nessuno). Anche la fibra è trattata allo stesso modo. Nessuna funzione del solver è modificata.

## Risultato del ricalcolo locale

Conteggi deterministici sull’intero dataset, senza solver o budget di ottimizzazione:

| Misura | Prima | Dopo |
|---|---:|---:|
| Schede importate | 832 | 832 |
| Quattro macro completi | 777 | 832 |
| Proteine mancanti/simboliche | 14 | 0 |
| Grassi mancanti/simbolici | 27 | 0 |
| Carboidrati disponibili mancanti/simbolici | 21 | 0 |
| Fibra mancante/simbolica | 30 | 24 |

62 celle dei macro essenziali cambiano da vuoto a zero, distribuite su 55 alimenti. Tutte sono `tr` nel JSON grezzo delle pagine rilette; nessun valore numerico preesistente cambia. Le sei fibre `tr` diventano zero con provenienza; le altre 24 restano mancanti. I 55 alimenti recuperati sono una misura di completezza del vettore, non una raccomandazione né garanzia di compatibilità con una dieta.

| Gruppo | Alimenti recuperati |
|---|---:|
| Frutta | 13 |
| Verdura | 8 |
| Amidi | 1 |
| Proteine | 12 |
| Latticini | 3 |
| Altri gruppi (bevande, dolci, prodotti vari) | 18 |
| **Totale** | **55** |

### Candidati della formulazione attuale

| ID CREA | Alimento | Traccia recuperata |
|---|---|---|
| `007120` | Mele, fresche, con buccia | ["fat_g_100g"] |
| `181100` | Uova di gallina, intero | ["carbs_available_g_100g"] |
| `166000` | Parmigiano Reggiano DOP | ["carbs_available_g_100g"] |

Nei gruppi principali della libera tornano utilizzabili mele `007120` e uova `181100`: frutti completi 1 → 2; fonti proteiche/legumi complete 6 → 7. Il test controlla la loro presenza tra le scelte di `formulate`; non vengono cambiati porzioni, target, frequenze o identità canoniche. Il limite B16 basato su due frutti rimane valido; i risultati numerici della diagnosi T-007 descrivono il dataset precedente e non sono stati riscritti retroattivamente.

### Le 14 proteine

Non risultano etichette diverse da `Proteine (g)` o un difetto di selezione della riga: tutte le 14 sorgenti riportano esattamente `tr`. Il problema era la conversione del simbolo a `None`, ora corretta. Elenco:

| ID CREA | Alimento | Esito sorgente |
|---|---|---|
| `202010` | Caramelle dure | `tr` → 0 con provenienza |
| `401100` | Bevanda tipo cola | `tr` → 0 con provenienza |
| `403010` | Bevanda alcolica, Aperitivo a base di vino | `tr` → 0 con provenienza |
| `405010` | Bevanda alcolica, Vino da pasto bianco | `tr` → 0 con provenienza |
| `405020` | Bevanda alcolica, Vino da pasto rosso | `tr` → 0 con provenienza |
| `406010` | Bevanda alcolica, Marsala tipico | `tr` → 0 con provenienza |
| `406500` | Bevanda alcolica, Vermouth dolce | `tr` → 0 con provenienza |
| `406510` | Bevanda alcolica, Vermouth secco | `tr` → 0 con provenienza |
| `407010` | Bevanda alcolica, Liquori da dessert | `tr` → 0 con provenienza |
| `407510` | Bevanda alcolica, Marsala all'uovo | `tr` → 0 con provenienza |
| `408010` | Bevanda alcolica, Brandy | `tr` → 0 con provenienza |
| `408100` | Bevanda alcolica, Grappa | `tr` → 0 con provenienza |
| `408900` | Bevanda alcolica, Whisky | `tr` → 0 con provenienza |
| `409000` | Bevanda alcolica, Spumante | `tr` → 0 con provenienza |

## Riproduzione e ambiente

`bs4` non è installato nell’interprete indicato da `.env`, ma è già presente nell’ambiente locale di base, insieme a `soupsieve`. Non sono state installate librerie: i due pacchetti Python già presenti sono esposti tramite collegamenti temporanei in `/tmp/optees-crea-pure`. Per ricreare l’ambiente locale:

```bash
mkdir -p /tmp/optees-crea-pure
ln -sfn /home/paolo/anaconda3/lib/python3.13/site-packages/bs4 /tmp/optees-crea-pure/bs4
ln -sfn /home/paolo/anaconda3/lib/python3.13/site-packages/soupsieve /tmp/optees-crea-pure/soupsieve
python scripts/import_crea.py --offline
set -a
. ./.env
set +a
PYTHONPATH=scripts:tests:.:/tmp/optees-crea-pure "$DIET_PYTHON" -m unittest test_import_crea test_ingredient_overlap test_diet_day -q
```

Questi percorsi descrivono questo ambiente. Su un altro ambiente con `bs4` già disponibile non serve il percorso temporaneo. L’import offline controlla che ogni pagina richiesta esista prima di aggiornare il dataset e si interrompe anche su un errore di parsing, lasciando gli output precedenti. Il test con cache sintetica incompleta verifica assenza di download e conservazione del dataset.

## Verifica

Cinque test dell’import verdi (ultima esecuzione: 5 test in 0,025 s). I tre test iniziali erano rossi per la conversione di `tr` a `None` prima della correzione. Test protetti invariati rispetto alla Base.

**Verifica generale non completata:** sotto sandbox il TestClient resta in attesa nell’event loop; fuori sandbox i test HTTP proseguono. Nel rilancio completo, 58 test conclusi verdi e poi circa 13,5 minuti senza conclusione del test `DailyMealsTests.test_daily_targets_do_not_reuse_main_meal_targets`. Il controllo della scheda (5 test nuovi più 17 protetti) è stato interrotto dopo oltre 20 minuti, ancora in calcolo; `check_task` restituisce `ESITO: non pronto (1 problemi)`, dovuto al codice -15 dell’interruzione. La suite generale è stata quindi fermata per lo stesso blocco. Non sono stati osservati errori di assertion, ma non è certificata una suite verde o una causa precisa dei tempi. Gli adattatori SciPy esistenti non impongono un limite per singola soluzione; nessun test o solver è stato modificato per aggirare questa attesa. Servono una diagnosi dei tempi e un perimetro autorizzato appropriato.

I test rossi T-009 sono una fase separata: file temporaneamente fuori dalla scoperta prima del suo commit, poi ripristinato e committato; nessun test esistente disabilitato. L’esecuzione finale T-009 dà 10 test, 10 fallimenti di assertion (due sottocasi di un metodo), nessun errore di fixture; non vengono dichiarati verdi. Nessun commit della T-008.

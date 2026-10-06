# 8.9 — sovrapposizione canonica e audit aggregato

## Identità e categorie

Versione `ingredient-overlap-v1`. Identità: gruppo esplicito di `config/recipe-diet-food-groups.json`; in assenza del gruppo, id CREA. Il livello è volutamente conservativo: per esempio tutte le voci esplicitamente classificate `vegetable` condividono la stessa identità. Non è una classificazione ricavata dai macro.

I prodotti OFF presenti nella mappa condividono il gruppo del generico. I prodotti personali e OFF associati con `/api/foods/preferred` condividono gruppo/id CREA scelto. Prodotti di marca senza associazione verificata finiscono nel solo gruppo conservativo `unclassified_product`: un cambio di marca non può inventare diversità. Warning `canonical_mapping_missing`; una successiva associazione verificata permette il confronto più preciso. Mai abbinamenti dedotti dal nome della marca.

Esclusi per categoria: gruppo `oil`, acqua e nomi di categoria espliciti per oli, sale, spezie, erbe, aceto, brodo/dadi e condimenti (maionese, senape, ketchup, salsa di soia). Le regole nominali sono esplicitate in `ingredient_overlap.EXCLUDED`, versionate nel codice; valgono a qualunque grammatura. Agli alimenti preferiti collegati a un generico si applica anche la categoria del generico. Aglio e cipolla non sono esclusi perché il gruppo `aroma` contiene anche alimenti: si escludono le erbe identificate, non l'intero gruppo. Passata/salsa di pomodoro, burro, frutta secca e altri alimenti restano conteggiati.

Le ricette con composizione verificata si scompongono in ingredienti con frazioni in peso: la ricetta demo ha già frazioni; le porzioni salvate in `recipe_runs` forniscono grammi e identità degli ingredienti. Acqua/condimenti sono rimossi dal denominatore. Composizioni non verificabili condividono `unclassified_composition`, senza attribuire falsa diversità fra titoli di ricette. L'inserimento delle nuove ricette nel solver resta il passo 8.7.

## Modello e garanzie

Per B si misura la quota dei suoi grammi, non esclusi, con identità presente in A. Le direzioni possono differire: si riporta e si limita **il massimo di A→B e B→A**. Per ogni piano già nel pool si aggiungono:

- il vincolo lineare sui grammi di B: grammi condivisi ≤ t × grammi totali;
- il vincolo lineare sui grammi costanti di A e indicatori binari della presenza delle identità in B: grammi di A condivisi ≤ t × grammi di A.

Gli indicatori sono OR delle scelte selezionate. Le porzioni non escluse hanno minimo positivo; il risultato viene nuovamente controllato sui grammi decodificati. Nel confronto per pasto entra solo lo slot richiesto; nel confronto settimanale tutti i giorni e pasti, compresi quelli fissati. Le chiavi non includono data o marca: spostare la stessa pasta a un altro giorno non è una nuova identità.

Si cerca prima t=0,10. Se certificato impossibile, bisezione del massimo rapporto, con tolleranza assoluta di **un punto percentuale**. Ogni problema a soglia fissa è lineare: nessun prodotto tra soglia variabile e grammi. Il limite inferiore cambia solo su infeasibilità certificata; un timeout non dimostra impossibilità. `lower_bound`, `threshold`, `precision_pct`, `certified` espongono l'intervallo e la certezza della ricerca. L'ottimo è relativo ai piani **già fissati**, non l'ottimo globale simultaneo di tutte le possibili terne; seed, primo riferimento e ordine restano rilevanti.

I minimi/massimi nutrizionali, le porzioni a passi di 5 g, gli abbinamenti, le esclusioni, i blocchi e le frequenze proteiche non vengono rilassati. Il vecchio limite epsilon sullo scarto ottimo era un limite su un obiettivo soft: per la nuova ricerca non è un vincolo (`near_optimal_enforced:false`). Il suo valore resta una diagnostica, senza essere gonfiato per far apparire quasi ottimi piani più distanti dai bersagli. S3 valuta gli scarti e il fronte Pareto; S4 mantiene la robustezza, S6 il bandit. Una terza alternativa fattibile fuori dal fronte campionato viene indicata nei tradeoff.

I percorsi normali cercano almeno tre piani fattibili, anche quando l'ottimo del riferimento non è certificato: `partial` continua a segnalarlo. Budget o vincoli possono limitarne il numero, con warning. Le richieste interne/diagnostiche `k:1|2` conservano il conteggio, per evitare moltiplicazioni nel solver congiunto. Un'estensione confronta il nuovo candidato con **tutte** le alternative del pool, e mostra soltanto candidati che cambiano almeno il 50% degli ingredienti. Non modifica il diario né applica un piano. CSRF, proprietà, controllo stato e scrittura atomica sono coperti dai test.

La varietà **interna** alla settimana è distinta: limite proteico rigido invariato e penalità euristica 0,002 per ripetizione della fonte principale oltre due pasti, nel riferimento della generazione. Soglia provvisoria dichiarata in `pool.within_week_variety`; non è un parametro scientifico o un nuovo divieto, e non altera i modelli di rientro/ricalibrazione.

## Misura prima/dopo

Audit riproducibile con `scripts/audit_ingredient_overlap.py`, baseline `fe2216e`. Solver diagnostico indipendente SciPy/HiGHS, massimo 5 secondi per solve e 120 secondi per generazione, tre alternative richieste. La produzione usa Optees e verifica indipendentemente ogni risultato. I tempi possono cambiare il numero dei piani certificati fra macchine o carichi di lavoro.

Nessun database utente, dato corporeo, alimento personale o piano effettivo entra nel report. Demo libera con porzioni sintetiche fisse e pesabili; per entrambe le settimane delle due diete, sole regole degli abbinamenti e target pubblici demo di giornata completa, senza etichette/preferenze personali. Colazione e spuntini sono abilitati: i limiti del solo pranzo/cena non rendono tutte le giornate confrontabili.

| Scenario | Alternative prima → dopo | Sovrapposizione massima prima → dopo | Media fra coppie prima → dopo |
|---|---:|---:|---:|
| Demo libera | 2 → 3 | 100,00% → 59,46% | 100,00% → 57,14% |
| Dieta sedentaria, settimana 1 | 2 → 3 | 99,20% → 69,76% | 99,20% → 64,75% |
| Dieta sedentaria, settimana 2 | 1 → 3 | non confrontabile → 78,76% | non confrontabile → 69,45% |
| Dieta palestra, settimana 1 | 2 → 3 | 100,00% → 78,20% | 100,00% → 77,84% |
| Dieta palestra, settimana 2 | 1 → 3 | non confrontabile → 80,30% | non confrontabile → 72,46% |

Tutti i piani rispettano i vincoli nutrizionali e le frequenze del modello. Nella prova precedente alcuni riferimenti/obiettivi secondari hanno esaurito il tempo (`partial`); dopo, demo e dieta sedentaria sono `ok`, le settimane palestra sono `partial` per l'ottimo del riferimento, ma hanno tre piani verificati. In **tutti e cinque** i pool nuovi le due ricerche minimax verso i piani precedenti sono certificate entro un punto percentuale.

Il 10% non è raggiunto in queste prove. Le categorie condivise e i pasti invariabili impongono sovrapposizione; il programma la mostra, anziché chiamare diverse alternative che cambiano solo qualche condimento. Una prova esplorativa senza limite temporale sul solve aveva tre alternative libere con massimo 100% e media 99,36%; non è usata come confronto principale, perché i budget non erano uguali.

Test sintetici aggiuntivi: soglia 10% fattibile verso due riferimenti contemporaneamente; limite minimax inevitabile del 50%; marche equivalenti; categoria olio anche con quantità elevate e prodotti preferiti; ingredienti delle ricette; timeout senza falsa certificazione; tre alternative giornata/settimana; pasto con gli altri pasti intatti; estensione dello stesso pool, nessuna scrittura al diario, CSRF e rollback 409.

### B16 — verifica su database nuovo

Profilo predefinito libero, database SQLite temporaneo nuovo, settimana
2026-10-05, Optees reale, `k=3`, `pool_size=3`, `time_limit=45`.
La prova finale ha prodotto 2 alternative, sovrapposizione 71,86%, stato
`partial`; entrambe le ricerche sono non certificate. Il valore dipende dal
budget e dai test concorrenti: **non è una prova dell'ottimo**. Ordinare i giorni
intercambiabili non ha dato un beneficio nel confronto ed è stato scartato.

La spiegazione dell'impossibilità richiesta non dipende dal risultato del
solver: il dominio libero contiene solo 2 frutti (non tutto CREA); ogni settimana
contiene 14 porzioni di frutta di almeno 100 g. Fra tre supporti non vuoti di due
identità, due sono inclusi uno nell'altro. Tutta la frutta del supporto minore
si sovrappone: almeno 1.400 g. La massa non esclusa di ogni settimana è al massimo
14 × (120 g amido + 300 g verdura + 250 g proteina + 250 g frutta) = 12.880 g.
La sovrapposizione bidirezionale è quindi almeno **10,8696%**. Identità più strette,
più tempo e rimozione dei vincoli di frequenza non possono portare tre alternative
al 10% con questo dominio. Per ottenere il 90% di diversità servirà ampliare
**i candidati della formulazione**, non soltanto il database o il budget.
Il backend ora espone questo limite e registra `certified:false` anche quando
il budget si esaurisce prima del tentativo successivo.

# Colazione e spuntini nel bilancio giornaliero

Nel profilo si abilita **Includi colazione e spuntini — variante personalizzata**. In questo caso il MILP pianifica colazione, metà mattina, pranzo, metà pomeriggio (se abilitato) e cena. I target giornalieri sostituiscono i target della somma pranzo+cena; i limiti locali dei pasti restano attivi. Le vecchie alternative conservano ambito e totali originali. I target giornalieri iniziali sono dimostrativi, non fabbisogni personali.

Le etichette e preferenze provengono esclusivamente dal profilo autenticato. Un nuovo profilo non eredita prodotti, abitudini o diete di Paolo; la funzione è inizialmente disattivata. La prima alternativa generica disponibile è una banana per ciascun pasto aggiuntivo pianificato, con grammi edibili minimi/massimi modificabili (default dimostrativo 100–220 g). CREA è la fonte generica, non una marca.

Per un prodotto confezionato la quantità è a unità intere. L’energia dichiarata per unità è mantenuta senza ricostruirla dai macro. Per ciascun macro si usa la sua base dichiarata (per 100 g o per porzione). Nel profilo di Paolo: una barretta da 35 g con energia 173 kcal, e crackers da 32 g con energia 131 kcal. Le varianti non sono identificate da barcode: sono dati di etichetta riferiti dall’utente, esplicitamente indicati nell’output. Fibre mancanti non vengono inventate; questa versione vincola solo energia e tre macro.

La seconda barretta da 35 g è disponibile solo se si abilita l’apposita opzione; non è obbligatoria e non viene scelta frazionata. I limiti nutrizionali e le porzioni sono rigidi. Fra le soluzioni fattibili, una prima ottimizzazione minimizza la sostituzione dei prodotti preferiti (costo 1 ciascuna) e l’uso dell’unità extra facoltativa (costo 0,1). Il secondo calcolo mantiene quel minimo entro tolleranza 1e-7 e minimizza gli scarti relativi dai target giornalieri. Non è Pareto o bandit. Se un prodotto preferito non permette di rispettare i vincoli, è disponibile la banana come alternativa. Le preferenze non allargano mai i limiti.

L’output conserva alimenti, fonti e quantità, subtotali per ciascun pasto e totali della giornata calcolati dai valori non arrotondati. Optees valida le soluzioni; il client ricontrolla integralità, quantità e vincoli. Le quantità mostrate sono arrotondate.

**Ambito:** colazione e spuntini sono una variante personalizzata. Non vengono dichiarati conformi alle colazioni originali delle diete; restano esclusi bevande caloriche, extra, frequenze settimanali e diario dei consumi effettivi. Pranzo e cena usano i sottoinsiemi già modellati; le ricette associate nella sezione Ricette non vengono ancora inserite nel piano. Un frutto pomeridiano disattivato è marcato “non pianificato”, non “consumato zero”.

## Verifica ripetibile

```sh
/home/paolo/anaconda3/envs/optees/bin/python scripts/check_full_day_preferences.py
```

L’audit usa target giornalieri dimostrativi e le etichette personali locali; non cambia i piani scelti. Output escluso da Git: `data/personal/full_day_preferences_audit.json`. Verifica del 4 ottobre 2026: 28/28 giorni con soluzione ottima e verificata; prodotti preferiti mantenuti insieme in 27/28. Nel giorno 11 palestra il modello sceglie banana al posto della barretta per rispettare i limiti giornalieri. Questo risultato dipende da target, porzioni e sottoinsieme, senza certificare la dieta completa.

87 test complessivi: comprendono somma dei subtotali, energia di etichetta, quantità discrete, seconda barretta facoltativa, sostituzione per un vincolo locale, separazione dei target giornalieri, infeasibilità senza rilassamenti e configurazioni isolate per utente.

## Alternative verificabili nell’interfaccia

Le nuove alternative conservano un rapporto dei vincoli usati per quel calcolo, indipendente dalle successive modifiche al profilo. La scheda mostra alimenti e fonte, grammi, confezioni intere quando applicabili, subtotali per pasto e totali giornalieri. Il dettaglio confronta ciascun risultato con minimo, massimo e bersaglio; include anche i limiti locali configurati. La verifica usa valori non arrotondati e il controllo indipendente di tutte le variabili e dei vincoli del problema. Il bersaglio è un obiettivo morbido, distinto dai limiti obbligatori.

Lo storico privo del rapporto non viene reinterpretato con i vincoli attuali: invita a generare nuove alternative. La verifica riguarda il sottoinsieme modellato, non le frequenze settimanali o gli extra non ancora integrati.

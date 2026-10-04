# Ricette e abbinamenti delle diete

La pagina Ricette contiene un controllo separato degli ingredienti per programma, giorno dei 14 e pasto. Il servizio legge il calendario verificato e valuta separatamente ogni lettera alternativa e ciascun ramo modellato. Non combina porzioni di rami differenti per far apparire una ricetta ammissibile.

Esiti:
- **Abbinamento modellato coperto**: tutti i gruppi richiesti sono presenti e tutti gli ingredienti sono assegnabili a un ruolo o condimento ammesso nel ramo.
- **Da completare**: nessun ingrediente vietato nel ramo, ma mancano uno o più gruppi. L’interfaccia indica quali; non aggiunge automaticamente contorni, frutta o secondi.
- **Nessun abbinamento verificato**: ingrediente/ruolo non verificato, alimento non ammesso nel ramo, più alimenti dove è prevista una sola scelta, oppure ramo non ancora rappresentato. Non dimostra incompatibilità con l’intera scheda originale.

La classificazione usa identità esplicite del catalogo, non calorie o macro. Ogni alternativa di marca di un ingrediente deve avere la stessa categoria verificata. Un prodotto non mappato o non revisionato impedisce di approvare quell’ingrediente. Le verdure possono essere multiple; le scelte singole non vengono estese a più formaggi, più legumi o proteine diverse. Il Parmigiano grattugiato è un condimento soltanto nei rami in cui è dichiarato; non rende ammissibili altri formaggi. Il tonno al naturale non è automaticamente equivalente al tonno sott’olio della scheda. Gli ingredienti non presenti nei rami conservativi, comprese alcune impanature e condimenti, restano da verificare.

Le classificazioni pubbliche sono in `config/recipe-diet-food-groups.json`. Regole personali e provenienza restano in `data/personal/recipe_diet_semantic_rules.json`, escluso da Git e dall’accesso statico. L’API `/api/recipe-diet-options` richiede autenticazione: solo un profilo con diete personali può chiedere le due modalità personali. Gli altri profili possono usare la modalità libera, che non legge calendario o regole di Paolo.

Le associazioni sono riferite ai rami attualmente modellati, senza certificare l’intera dieta originale. Non verificano nutrienti, quantità, colazione/spuntini, frequenze settimanali o eventuali esclusioni/allergie personali. La prova del solver del singolo piatto resta separata e non inserisce la ricetta nel piano pranzo/cena. Un pulsante “Prova questa ricetta” carica la composizione per la prova; non approva un pasto completo.

Audit ripetibile delle 25 ricette su 56 contesti (due programmi × 14 giorni × due pasti), con 1.400 valutazioni. Il report contiene hash dei template, delle regole, delle categorie e del calendario, e le ragioni per ciascun ramo:

```sh
/home/paolo/anaconda3/envs/optees/bin/python scripts/recipe_diet_compatibility.py
```

Output personale: `data/personal/recipe_diet_compatibility_audit.json`. I test coprono ingredienti non mappati, scelte multiple, rami alternativi, condimenti, complementi mancanti, modalità libera e isolamento delle regole personali. Non serve una risoluzione Optees per questo controllo strutturale; l’ottimizzazione delle quantità resta nel solver esistente.

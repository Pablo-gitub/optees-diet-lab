# Ottimizzazione degli abbinamenti e verifica delle due settimane

`scripts/plan_diet_day.py` formula un MILP e lo risolve tramite MCP Optees.
Legge il calendario personale controllato visivamente, con tutte le alternative
«oppure». Seleziona esattamente un ramo per pasto, un alimento per gruppo e
quantità continue legate alla selezione binaria. Non può mescolare gruppi di
rami alternativi o attribuire nutrienti a un alimento non selezionato.

## Copertura e interpretazione

Tutte le lettere presenti nei 28 giorni hanno almeno un sottoinsieme modellato:
A/B/C/D/E/F/G/M/O/Q ed E+pane. Non sono ancora rappresentati tutti gli alimenti,
le salse sostitutive e tutti i rami. F usa formaggio+verdura+pane oppure pizza;
G usa pane+verdura+secondo oppure pizza. M usa un passato dimostrativo di zucchine
bollite (50% CREA 005735) e acqua (50% del peso finale), contorno, pane e secondo.
Q usa il ramo pizza con acqua; non il pasto al ristorante o McDonald's.

Una soluzione verificata dimostra che esiste una combinazione nel sottoinsieme.
Un risultato infeasible non dimostra l'impossibilità della dieta completa:
restano scelte non modellate e nutrienti mancanti nel database. Le voci mancanti
non vengono convertite in zero. Il controllo visivo ha corretto l'OCR della
scheda D sedentaria: contiene anche pane/patate, come quella palestra (restano
non modellate le opzioni fritte/maionese specifiche della sedentaria).

## Vincoli e obiettivo

`config/demo-diet-day.json` definisce obiettivi globali **solo per pranzo+cena**.
`config/demo-diet-audit.json` definisce limiti locali dimostrativi per ciascun
pasto: 200–900 kcal e 5–80 g di proteine. Non sono fabbisogni personali o
prescrizioni. Le porzioni del codice sono ipotesi di prova, modificabili tramite
`portion_bounds_g`. I pesi si riferiscono allo stato CREA indicato nell'output:
pasta/riso secchi, legumi cotti, altri alimenti talvolta crudi.

I limiti sono rigidi e non vengono allargati per ottenere una soluzione.
L'obiettivo minimizza la somma degli scarti relativi assoluti dai bersagli;
con soli vincoli locali esegue una ricerca di fattibilità (obiettivo zero).
Pareto, min-max, max-min e bandit non sono ancora implementati.

## Audit ripetibile

```sh
python scripts/check_diet_fortnights.py
python scripts/diagnose_diet_audit.py
python -m unittest discover -s tests -v
```

L'audit usa una sessione MCP per 84 problemi: 28 giorni × solo locale, solo
globale, entrambi. Ricalcola indipendentemente vincoli, limiti delle variabili e
integralità delle soluzioni, oltre alla verifica Optees. Salva quantità, nutrienti
per pasto e complessivi, configurazione e hash di calendario/modello/CREA in
`data/personal/diet_fortnight_audit.json` e un report Markdown nella stessa
cartella, esclusa da Git. Diagnosi e test indipendenti richiedono numpy/scipy,
già presenti nell'ambiente Optees utilizzato.

Con gli input demo: tutti i 28 giorni ammettono i vincoli locali; 26 ammettono
anche quelli globali e simultanei. Il giorno 11 di entrambe le diete (C/C) non
raggiunge il minimo demo 90 g di carboidrati nella somma pranzo+cena. La diagnosi
massimizza i carboidrati nel sottoinsieme con i soli limiti locali: massimo
25,3 g sedentaria, 16,8 g palestra. Non cambia il requisito per nascondere il
fallimento. Il controllo non comprende colazione, spuntini, frequenze settimanali,
bevande caloriche o vincoli fra giorni: non certifica la giornata alimentare
completa né una singola ottimizzazione dell'intera settimana.

Prossimi passi: ampliare gli alimenti/rami e le ricette, aggiungere gli altri
pasti, definire gli obiettivi personali tramite interfaccia e introdurre
criteri Pareto e vincoli fra giorni. Una lettera sconosciuta blocca la giornata
anziché essere ignorata. La funzione `run` resta richiamabile dal futuro backend.

# Interfaccia locale

Avvio sul PC:

```sh
./scripts/start_web.sh
```

Aprire http://127.0.0.1:8765. Per accesso LAN:

```sh
DIET_WEB_HOST=0.0.0.0 ./scripts/start_web.sh
```

Gli amici aprono `http://IP-DEL-PC:8765` e creano il proprio profilo con nome
utente e password. HTTP locale non cifra traffico o password: usare questa
prima versione su una rete domestica fidata, senza pubblicarla su Internet.
Il server non viene installato come servizio: termina se viene fermato il
processo. Non è previsto avvio automatico al riavvio del PC.

Al primo avvio si crea il profilo Paolo, con password casuale salvata soltanto
in `data/personal/web_access.txt` (permessi 0600), escluso da Git. Il database
`data/personal/web.sqlite` contiene password con scrypt/salt, sessioni a scadenza,
configurazioni e piani distinti per utente. Cookie HttpOnly/SameSite, token CSRF,
controllo Origin e query vincolate all'utente proteggono le operazioni. Le cartelle
personali non sono servite dal web server. Configurazione e piano restituiti
agli utenti non contengono percorsi dei file o risultati grezzi MCP.

## Funzioni disponibili

- Ricette: catalogo offline di 834 record, ricerca, filtro cucina e paginazione.
- Profilo: cucine preferite personali, nome, obiettivi demo/configurati, limiti opzionali per pasto,
  esclusioni per codice CREA e note personali.
- Pianificazione: programma, 14 giornate, generazione fino a tre alternative,
  nutrienti e quantità, scelta persistente del piano.
- Paolo dispone dei due schemi originali; gli amici partono dalla modalità
  libera. Il motore riceve le regole dalla configurazione privata
  `data/personal/diet_combination_rules.json`, non da tabelle di dieta nel codice.
- Le preferenze alimentari di Paolo sono copiate nel suo profilo; gli altri
  utenti non le ereditano. Modificare la configurazione non modifica piani salvati.

Le alternative sono ottimi successivi dopo esclusione delle selezioni precedenti:
non sono necessariamente equivalenti nel punteggio né una frontiera Pareto.
Si possono generare meno di tre alternative. Sono salvati anche gli esiti senza
soluzione, che non possono essere scelti come piano.

## Copertura attuale

Il calcolo riguarda solo pranzo/cena e sottoinsiemi degli abbinamenti. Le note
sui gusti e i prodotti etichettati sono conservati, ma non entrano ancora nel
solver e non ordinano le alternative. Restano da implementare colazione/spuntini,
frequenze settimanali, Pareto, diario di quanto consumato, attività fisica,
importazione Apple Health e andamento corporeo. Gli amici non possono ancora
importare uno schema dietetico personale. Non sono ancora disponibili cambio
password, recupero accesso o gestione amministrativa dei profili nell'interfaccia.

Le preferenze di cucina filtrano il catalogo ma non orientano ancora il solver. I nutrienti delle ricette sono quelli dichiarati dalle fonti.

Verifica: 60 test (MILP, autenticazione, CSRF/Origin, isolamento piani/profili,
nessuna pubblicazione dei file personali), controllo sintassi JS, prova reale
login/generazione con Optees e controllo browser delle schermate.

## Ottimizzazione della singola ricetta

Nella pagina Ricette si possono adattare 25 composizioni con associazioni esplicite: pasta al pomodoro dimostrativa e un adattamento foodose del panino mozzarella/pomodoro/olive. Si scelgono prodotti disponibili, intervalli nutrizionali, limite della porzione e flessibilità delle proporzioni. Le prove sono salvate nello storico privato di ogni profilo, separato dai piani. Dettagli e limiti in [recipe-solver.md](recipe-solver.md). La conformità alle due diete personali non è ancora verificata.

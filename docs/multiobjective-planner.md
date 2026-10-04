# Strategie nutrizionali e feedback personale

La pagina Pianificazione offre Bilanciato, Pareto, Min-Max, Max-Min e Bandit. Tutte le strategie conservano i vincoli rigidi del MILP e la priorità delle preferenze personali. Le soluzioni sono controllate da Optees e da una verifica indipendente. Le alternative successive dei metodi singoli escludono le combinazioni già proposte: il loro ottimo riguarda quel problema ristretto.

## Criteri matematici

- **Bilanciato**: minimizza la somma degli scarti assoluti divisi per il bersaglio di ciascun nutriente.
- **Min-Max**: minimizza il massimo di questi scarti relativi. A parità del risultato primario, minimizza la somma degli scarti relativi.
- **Max-Min**: massimizza la soddisfazione minima. Per ogni nutriente la soddisfazione è `1 - |valore - bersaglio| / max(bersaglio - minimo, massimo - bersaglio)`. Un bersaglio fisso ha soddisfazione 1, essendo già un vincolo rigido. Risolve l'epigrafo dello scarto normalizzato peggiore, poi usa lo stesso criterio secondario del Min-Max. È una definizione esplicita di soddisfazione, non un punteggio sanitario.
- **Pareto**: cinque somme pesate positive (uniforme e una priorità 4× per ciascuno dei quattro nutrienti), sul medesimo insieme ammissibile senza esclusioni delle combinazioni. Ricalcola gli scarti reali, elimina duplicati e soluzioni dominate. È un campione non dominato fra le soluzioni calcolate; non enumera la frontiera completa, né tutti i punti non supportati di un problema intero. Non genera tre alternative artificiali quando esiste un unico compromesso.

Ogni scheda salva strategia, scarti dei nutrienti, scarto relativo peggiore e soddisfazione minima. Gli obiettivi demo e le limitazioni della dieta modellata restano espliciti.

## Bandit e prove effettive

Il bandit UCB1 sceglie fra le strategie Bilanciato, Min-Max e Max-Min. Il braccio è la strategia, non il singolo alimento. Pareto rimane un metodo di esplorazione manuale. Il feedback consiste nella dichiarazione di aver provato il piano e in un voto 1–5, trasformato in ricompensa `(voto - 1) / 4`.

Generazione e selezione di un piano non sono ricompense. Un piano riceve una sola osservazione, modificabile: un aggiornamento del voto non ne moltiplica il peso. Si esplorano prima i bracci privi di prove; poi si usa media + `sqrt(2 log(N) / n)`. Finché non arriva un voto, un braccio resta privo di osservazioni: generare continuamente piani non simula apprendimento.

Osservazioni e piani sono privati per utente. Il contesto separa programmi, obiettivi, porzioni degli spuntini, esclusioni e preferenze: cambiare questi parametri avvia un contesto nuovo. Le giornate dello stesso programma condividono le osservazioni; non è ancora un modello contestuale del singolo giorno o un apprendimento degli effetti corporei. Gli utenti non si scambiano feedback. Anche i voti di piani generati manualmente contribuiscono se strategia e contesto corrispondono.

## Verifica

`tests/test_multiobjective_day.py` usa un esempio con compromesso noto: Min-Max ha ottimo `20/3`, Max-Min `8`. Verifica dominanza, duplicati, priorità delle preferenze, immutabilità del problema e selezione UCB1. I test web controllano autenticazione, CSRF, isolamento, validazione e aggiornamento unico del voto.

`python scripts/check_multiobjective_day.py` esegue un controllo reale con Optees su quattro giornate rappresentative (entrambe le settimane e diete), con obiettivi demo. Il rapporto resta in `data/personal/multiobjective_audit.json`.

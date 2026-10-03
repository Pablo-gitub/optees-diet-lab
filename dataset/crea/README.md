# CREA — composizione degli alimenti

Fonte: CREA Centro di ricerca Alimenti e Nutrizione, Tabelle di composizione degli alimenti, aggiornamento 2019; website a cura di L. Marletta e E. Camilli.

- https://www.alimentinutrizione.it/tabelle-di-composizione-degli-alimenti
- https://www.alimentinutrizione.it/tabelle-nutrizionali/ricerca-per-ordine-alfabetico
- https://www.crea.gov.it/alimenti-e-nutrizione

Verifica fonte: 3 ottobre 2026. Le pagine ufficiali richiedono indicazione della fonte originale e rispetto della proprietà intellettuale. Non è stata identificata una licenza standard aperta: non etichettare questi dati come CC0/CC-BY. Questo archivio è predisposto per uso personale locale; un'eventuale pubblicazione richiederà una verifica specifica.

Non è un export ufficiale: gli output sono derivati dalle schede HTML pubblicamente consultabili. La cache HTML è esclusa da Git, mentre gli output e la provenienza sono versionabili localmente.

## File generati

- `foods.csv`: campi essenziali, nutrienti per 100 g di parte edibile, codici mantenuti come stringhe.
- `foods.json`: metadati e tutti i nutrienti tabulati, unità originali, valori per porzione, metodo e referenze.
- `manifest.json`: data acquisizione, conteggi, errori, hash degli output e copertura dei macro.
- `raw/`: indice, prefazione, legenda e schede originali.

Valori numerici mancanti o simbolici diventano null, mai zero. Il testo originale resta nel JSON: “tracce”, intervalli e altri simboli richiedono una politica esplicita prima dell'ottimizzazione. Le percentuali degli acidi grassi sono conservate nella loro unità e non reinterpretate come grammi per 100 g. Non si uniscono alimenti crudi e cotti. I nutrienti descrivono l'alimento, non un suo effetto individuale sul dimagrimento.

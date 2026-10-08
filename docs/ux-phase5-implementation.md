# Fase 5 · Cucina, energia e traguardi

8 ottobre 2026 · Implementazione locale, con prove su database sintetico isolato.

## Percorso realizzato

Cucina raggruppa catalogo, compatibilità e adattamento. Ogni ricetta dichiara se è consultabile, pronta per il piano o non utilizzabile con gli alimenti attuali. Una ricetta pronta può essere fissata direttamente in un pranzo/cena futuro: giorno, porzioni, conferma e ritorno alla settimana. Il blocco vale per una nuova generazione; non sostituisce il diario o applica un piano. Preferiti e accessi a gusti/Abbinamenti conservano i servizi esistenti.

Progressi apre con due grafici allineati: energia prevista e giorni registrati. Assunzione e dispendio hanno tratto e simboli diversi; gli intervalli restano visibili e le serie si interrompono quando mancano dati. La tabella e i pulsanti dei giorni consentono di leggere valori, ambito, copertura, saldo e aprire i pasti del giorno. La data del periodo è ripristinabile nell’hash `#progressi?data=YYYY-MM-DD`.

La settimana applicata offre un grafico compatto e accesso al confronto; ciascuna proposta alimentare ha un dettaglio energetico identificato come bozza. Il dispendio previsto deriva dagli scenari del piano applicato/congiunto, quando disponibili. Non viene inventato per una dieta che ne è priva.

Profilo → Traguardi in ordine contiene editor, aggiunta, modifica, rimozione dei traguardi aperti e spostamento verso l’alto. Progressi mostra valore misurato, distanza, data desiderata, finestra condizionale quando disponibile e conferme. Settimana dichiara il traguardo attivo.

## Energia e versioni

`progress_dashboard.py` riusa i servizi del diario e i contesti del piano, senza sommare nuovamente l’energia degli allenamenti al totale Salute. Il totale Salute è quello importato di riposo + attività; la completezza usa il flag del servizio di importazione, non la semplice presenza di un numero.

Un giorno futuro mostra solo il previsto. Registrazioni incompiute rimangono parziali; il saldo richiede tutti i cinque slot dichiarati, ambito di giornata intera e un giorno concluso con copertura Salute sufficiente. Pasti saltati esplicitamente sono registrazioni valide. I nutrienti stimati si sommano come intervalli, senza sostituire il risultato con un valore medio.

Gli snapshot energetici sono immutabili, per account e settimana, nelle transazioni di applicazione e decisione del rientro. Conservano assunzione, scenari, ambito, momento/base della previsione e milestone/versione. Il selettore permette di consultare il previsto precedente con il diario corrente. Non vengono ricostruite versioni perdute prima di questa implementazione.

## Milestone e motore

Sequenza persistente con revisione, eventi ed evidenze; migrazione non distruttiva degli obiettivi corporei già salvati. Il modello operativo supporta **un criterio per milestone**: peso, grasso corporeo o minimo di sessioni settimanali. La prima ancora da perseguire è l’unica attiva.

- Il minimo di sessioni dell’attiva entra nei nuovi piani di attività/congiunti. Un massimo incompatibile produce un errore comprensibile.
- Le milestone corporee guidano la proposta esplicita del bilancio tramite il servizio degli obiettivi personali. Il piano usa le calorie approvate; nessun target viene cambiato automaticamente dalla sequenza o dalle misure.
- Un cambiamento della sequenza invalida la revisione delle bozze precedenti; i piani applicati restano invariati.
- Per il raggiungimento corporeo si richiedono tre giorni distinti di misura entro 14 giorni. È una regola di prodotto provvisoria, non una soglia clinicamente validata. Le misure manuali hanno precedenza sulle misure Salute dello stesso giorno.
- Le sessioni devono soddisfare il minimo in ogni settimana completa della finestra scelta.
- Raggiungimento dell’attiva: conferma di completamento. Raggiungimento anticipato: riepilogo dei numeri delle milestone da saltare, poi “Salta e prosegui”, “Mantieni l’ordine” o “Decidi più tardi”. Senza conferma l’ordine non cambia.
- Rinvio e mantenimento sono persistenti per evidenza; la scelta rimane riapribile, una nuova evidenza può riproporla. Il salto conserva gli stati “saltata” e “completata”, oltre all’evidenza originale negli eventi.
- Le proposte caloriche pendenti della stessa milestone/revisione riappaiono dopo ricarica; l’approvazione verifica nuovamente lo stato.

Autenticazione, CSRF, isolamento per account e controllo della revisione nelle transazioni impediscono modifiche concorrenti silenziose.

## Proiezioni

Il grafico del peso conserva misure, filtro Kalman e atteso settimanale esistenti; aggiunge la linea della milestone attiva. L’atteso dal piano resta limitato alla settimana e ai requisiti già verificati dal servizio, senza essere estrapolato come data fisiologica.

La finestra “Se continui con questo andamento” usa una retta sui pesi filtrati degli ultimi 42 giorni: almeno sei giorni di pesata distribuiti su almeno 21 giorni, misura recente e nessuna lunga interruzione nel periodo. La variabilità della pendenza produce due date; andamento piatto/opposto/incerto, soglia già raggiunta o finestra troppo distante/ampia non producono una data. Metodo `filtered-weight-linear-v1`, non validato come modello fisiologico o intervallo clinico.

Le stime sono deduplicate e persistenti in base a dati e criterio; l’apertura della pagina con gli stessi dati non crea una nuova stima. Una nuova stima confrontabile indica di quanti giorni la fine della finestra si è avvicinata/allontanata. Nessuna stima modifica scadenze o calorie. Per altre metriche il progresso resta visibile con “Data non ancora stimabile”.

## Verifiche

Suite conclusa: **36 test** su dashboard, revisione dei piani, filtro del peso e API allenamenti. Due casi legacy di ricette/applicazione verificati separatamente nella suite da 18 test; corretta una regressione della fase 4 nei chiamanti interni privi di `mode`/`run_id`. Dopo le ultime modifiche ai metadati, ulteriori **18 test** dashboard/obiettivi personali superati. Complessivamente 43 test distinti nei gruppi citati, con sovrapposizioni fra le esecuzioni. Controlli sintattici JavaScript/Python e `git diff --check`.

Le nuove prove coprono revisione/CSRF, rinvio, salto anticipato, evidenza insufficiente/obsoleta, isolamento, snapshot immutabili, saldo completo/parziale, intervalli, giorni futuri, adapter ordinato, finestre favorevoli/piatte/opposte, avvicinamento/allontanamento e ripresa delle proposte pendenti.

Prove UI tramite browser: creazione e salvataggio della sequenza; grafici e finestra; selezione della versione; dettaglio completo con saldo e giorno parziale senza saldo; rinvio dopo ricarica; salto esplicito e nuova milestone attiva; ricetta pronta fissata a pranzo con ritorno alla settimana. Desktop 1280 px e telefono 360/390 px, tema chiaro/scuro e focus da tastiera sulle decisioni. Nessuna certificazione completa di accessibilità.

Demo `/tmp/optees-ux-phase5/demo.sqlite`, copia della precedente demo sintetica; pesate, giornate registrate e riepilogo Salute sintetici aggiunti per verificare copertura e grafici. La UI dichiara la natura dimostrativa. I piani futuri provengono dai calcoli Optees della fase 4; in questa fase non è stato eseguito un nuovo confronto end-to-end di generazione Optees per ogni metrica. Database personale non usato.

Screenshot: [desktop](screenshots/ux-phase5/progressi-desktop.png), [telefono](screenshots/ux-phase5/progressi-mobile.png), [raggiungimento anticipato](screenshots/ux-phase5/milestone-anticipata-mobile.png), [ricetta → pasto](screenshots/ux-phase5/cucina-pasto.png).

## Limiti e fase 6

Milestone con più criteri simultanei, archiviazione esplicita e modelli di previsione per altre metriche non sono disponibili in questa versione; la UI dichiara un criterio per traguardo. Le soglie di evidenza e le finestre richiedono valutazione di prodotto prima di considerarle validate. L’editor della sequenza salva esplicitamente; una bozza non salvata non è sincronizzata fra dispositivi.

La fase 6 deve verificare i percorsi trasversali, inclusi nuovo profilo, nuova generazione reale con milestone attiva, approvazione calorie, importazione Salute, zoom 200%, contrasto e contesti di ritorno fra tutte le schermate. Deve inoltre verificare con il proprietario se il modello a un criterio per milestone copre gli obiettivi desiderati.

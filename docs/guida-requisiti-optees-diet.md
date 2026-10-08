# Optees Diet Lab · Documento di Visione e Requisiti Guida (v2.1)

**Stato:** Proposta di visione integrata con lo stato dell'arte delle fasi 0–5  
**Data:** 9 Ottobre 2026  
**Ruoli:** Visione utente (/grill-me via Gemini) · Sanity check tecnico e interfaccia (Claude) · Motore e backend (Codex)  
**Obiettivo:** Valorizzare la **Ricerca Operativa (Optees / solver MILP via protocollo MCP)** unendo rigore matematico e usabilità quotidiana a zero attrito, preservando il codice già funzionante.

---

## 1. Stato dell'Arte: Integrazione con le Fasi 2–5 di Codex

Questo documento non azzera il lavoro esistente, ma si innesta sul perimetro consolidato da Codex e verificato in Git:
* **Fase 2**: Questionario iniziale facoltativo, impostazione gusti e profilo persistente.
* **Fase 3**: Distinzione rigorosa tra bozza (`draft`), pasti registrati (`logged`) e impostazioni permanenti; cruscotto base Oggi.
* **Fase 4**: Separazione tra generazione, confronto e applicazione della settimana nel calendario; conservazione elementi protetti.
* **Fase 5**: Grafici energetici, traguardi ordinati a un criterio (senza date arbitrarie prive di modello validato).

---

## 2. Principi Guida e Visione d'Uso

1. **Zero-Friction con Stato `presunto`**: Se l'utente non modifica il diario, a fine giornata i pasti previsti vengono salvati come **`presunti`**. L'utente non deve cliccare conferme burocratiche; il bilancio energetico e il check-in del lunedì tengono conto della differenza tra dati certi (`logged`) e stimati (`presunti`).
2. **Realismo Culinario nel Solver (Piatto Principale + Moduli Jolly)**: Formulazione per pasto composto ($\text{Pasto} = \text{Piatto Principale} + \text{Alimenti Jolly}$). Permette di inserire piatti graditi (es. porzione realistica di lasagne o pasta ripiena) e coprire i gap proteici/calorici con alimenti di complemento (pollo, patate, yogurt greco, verdure).
3. **Varietà come Obiettivo di Ottimizzazione (non vincolo rigido)**: La varietà al 90% tra alternative è un **termine della funzione multiobiettivo** di Optees con fallback garantito. Se i vincoli personali o il catalogo non permettono il 90%, il solver trova il massimo grado di diversità ammissibile senza fallire.
4. **Palestra Guidata (Audio Coach & Screen Wake Lock)**: Supporto a sessioni HIIT/circuiti veloci (20–45 min) e sala pesi. Durante la sessione, il browser usa la **Screen Wake Lock API** per non mandare in standby il display dell'iPhone e la **Web Audio API** per scandire tempi di lavoro, ripetizioni e pause.
5. **Trasparenza Biometrica con Limiti Dichiarati**:
   * Il filtro di Kalman scalare *attenua* le fluttuazioni idriche del peso, non le cancella per magia.
   * La percentuale di massa grassa da bilancia impedenziometrica è trattata come trend indicativo.
   * Nessuna data di arrivo stimata viene promessa senza un modello metabolico convalidato.
6. **Nutrient Timing Rispettoso**: Distribuzione differenziata dei macronutrienti attorno all'allenamento applicata **solo per sessioni che superano i 60 minuti**.

---

## 3. Architettura dell'Informazione e Navigazione UX

Accesso da browser (computer e iPhone via VPN Tailscale):

```
+-------------------------------------------------------------------------+
| [Diet Lab Logo]                                  [Avatar Utente / Menù] |
+-------------------------------------------------------------------------+
|                                CONTENUTO                                |
|                        DELLA SCHERMATA ATTIVA                           |
+-------------------------------------------------------------------------+
|    [Oggi]     |    [Settimana]    |    [Allenamento]    |    [Cucina]   |
+-------------------------------------------------------------------------+
```

### 3.1 Le 4 Voci in Basso (Bottom Bar)
1. **Oggi**: Diario del giorno, scheda allenamento odierna, cruscotto energetico.
2. **Settimana**: Calendario alternative, applicazione piano, rientro sgarri, spesa per reparto (3 o 7 giorni).
3. **Allenamento**: Catalogo protocolli, carichi attuali, player sessione con timer/audio.
4. **Cucina**: Solo ricette 100% utilizzabili dal solver, catalogo supermercato, gusti e preferiti.

### 3.2 Menù Dietro l'Avatar (Header)
* **Profilo**: Dati biometrici di Apple Salute (altezza, peso, consumo medio), questionario gusti, attrezzatura reale (manubri fissi/componibili, bilanciere, dischi con quantità).
* **Progressi & Andamenti**: Caricamento zip Apple Salute, confronto calorie assunte vs consumate, trend peso Kalman, traguardi ordinati (il solver persegue il primo; se ne raggiungi uno successivo, chiede se saltare i precedenti).
* **Gusti & Abbinamenti (Tinder Food)**: Schede pasto con swipe (destra/sinistra/alto/cuore) per nutrire il bandit UCB1.
* **Impostazioni**: Tema grafico (dark/light), gestione database.
* **Esci**: Logout / cambio profilo.

---

## 4. Dettaglio Schermate e Logiche Operative

### 4.1 Oggi (Home Dinamica)
* **Apertura intelligente**: Mette in primo piano il **prossimo pasto non ancora registrato**, tenendo conto dell'orario come contesto (non come blocco rigido).
* **Azioni veloci**: Un tap per *"Salta pasto"* (attiva il micro-dialogo di riequilibrio) o *"Modifica / Ho mangiato altro"* (editor pasti di Codex).
* **Scheda del giorno**: Se oggi c'è allenamento, card con pulsante **"Avvia Sessione"**.
* **Cruscotto energetico**: Assunte vs stimate vs consumate reali da Apple Salute.

### 4.2 Settimana, Spesa e Sgarri
* **Alternative e "Calcolane altre"**: Almeno 3 alternative generate con massimizzazione della diversità.
* **Spesa Intelligente**: Finestra a 3 o 7 giorni, aggregata per corsia/reparto (Ortofrutta, Macelleria, Latticini, Dispensa...). Spezie, erbe aromatiche, aglio e limone inseriti con apporto 0 kcal nei calcoli e flag "controlla in dispensa".
* **Sgarro a 3 Opzioni**:
  1. *Oggi*: Ribilanciamento sui pasti rimanenti o spuntino serale.
  2. *Attività*: Camminata veloce o cardio leggero equivalente (chiedendo conferma all'utente).
  3. *Spalmato*: Ripartizione sui 2–3 giorni successivi.

### 4.3 Allenamento: Attrezzatura e Player
* **Inventario reale**: Modellazione esatta di bilancieri e manubri componibili simmetrici con conteggio dei dischi disponibili.
* **Intervista sui carichi**: Massimale (1–3 RM) e carico da 12 ripetizioni pulite contestualizzati nel singolo esercizio, per ricavare la scala di carichi.
* **Session Player**:
  * Richiede **Screen Wake Lock API** attiva per prevenire lo standby dello schermo su iPhone.
  * Web Audio API per segnali sonori (bip inizio/fine serie, conto alla rovescia recupero, metronomo di cadenza).
  * Pulsante Pausa/Riprendi sempre visibile.

### 4.4 Cucina e Barcode
* **Filtro Assoluto**: Mostrare in Cucina solo ricette al 100% pronte per il solver (`ready`). Nessun piatto incompleto o `catalog_only`.
* **Prerequisiti Barcode Scanner**:
  * Abilitazione di **HTTPS tramite `tailscale serve`** (indispensabile per consentire a iOS Safari di accedere a `getUserMedia`).
  * Libreria di scansione (es. ZXing/Quagga) **vendorizzata localmente** nel repository per rispettare la Content Security Policy della webapp.

---

## 5. Piano di Lavoro Coordinato

1. **Fase 1 (Condivisa - Priorità Immediata)**:
   * Pulizia del catalogo Cucina (solo ricette utilizzabili dal solver).
   * Riorganizzazione della navigazione: 4 voci in basso (Oggi, Settimana, Allenamento, Cucina) + menù dietro l'avatar.
2. **Fase 2**:
   * Formulazione Optees pasto composto (Piatto principale + Jolly) e diversità multiobiettivo con pulsante "Calcolane altre".
   * Implementazione stato `presunto` per il diario a zero attrito.
3. **Fase 3**:
   * Attrezzatura reale (dischi e manubri componibili) e intervista carichi.
   * Predisposizione infrastruttura `tailscale serve` (HTTPS) e vendor libreria barcode.
4. **Fase 4**:
   * Workout Audio Player con Screen Wake Lock e Web Audio API.
   * Uploader web Apple Salute e dashboard progressi.

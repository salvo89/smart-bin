# Smart Bin

Indicatore luminoso per la raccolta differenziata: un ESP32 accende i LED dei cassonetti da portare fuori **la sera prima del ritiro**, in fascia oraria configurabile. Include web UI locale (SoftAP / LAN) e una pagina calendario pubblica su Netlify.

**Licenza:** [GNU GPL-3.0](LICENSE)

## Cosa vuole essere

Un promemoria **fisico e automatico** in casa: non un’app da aprire, ma luci sul muro (o sul pannello) che dicono “domani esce carta / organico / …”.

In pratica:

- legge un **calendario locale** (`docs/calendars/<zona>-<anno>.h`, fusi da `docs/calendar.h` → `bin/calendar.h`) dei giorni di ritiro;
- di sera, nella fascia oraria impostata, accende i LED corrispondenti ai rifiuti di **domani**;
- segnala anche i giorni di **strada vuota** (cassonetti ritirati) con un respiro luminoso su tutti i LED;
- si sincronizza via **Wi‑Fi + NTP** (ora locale / DST);
- espone una **web UI** per calendario, stato rete e controllo manuale LED;
- resta usabile anche senza internet di casa tramite **SoftAP** sulla ESP.

Non è un prodotto commerciale né un servizio cloud: è un progetto hardware/firmware da flashare e adattare alla propria zona.

## Hardware (default)

| Elemento         | Default nel progetto                                                          |
| ---------------- | ----------------------------------------------------------------------------- |
| MCU              | ESP32 DevKit / ESP32-WROOM-32                                                 |
| LED (6)          | GPIO `25, 26, 27, 14, 33, 32` → Carta, Organico, Indifferenziata, Plastica, Verde, Vetro |
| Pulsante manuale | GPIO `4` (INPUT_PULLUP, premuto = LOW → GND)                                  |

I pin si cambiano in `config.h` (vedi sotto).

### Schema elettrico (default)

Alimentazione: ESP32 via USB (o 5 V su `VIN` / 3.3 V regolato secondo la tua DevKit). I GPIO sono a **3.3 V**. Ogni LED va in serie con una resistenza limitatrice; il catodo va a `GND`.

Valori tipici per LED standard a 3.3 V: **R ≈ 220 Ω** (va bene anche 150–330 Ω; regola in base a Vf e luminosità desiderata).

```text
                    ESP32 DevKit
                 ┌─────────────────┐
                 │                 │
           3V3 ──┤ 3V3             │
                 │                 │
           GND ──┤ GND             │
                 │                 │
                 │            GPIO25├────[R]────(►| LED Carta          ──┐
                 │            GPIO26├────[R]────(►| LED Organico        ──┤
                 │            GPIO27├────[R]────(►| LED Indifferenziata ──┤
                 │            GPIO14├────[R]────(►| LED Plastica        ──┼── GND
                 │            GPIO33├────[R]────(►| LED Verde           ──┤
                 │            GPIO32├────[R]────(►| LED Vetro           ──┘
                 │                 │
                 │             GPIO4├────┬──── pulsante (NO)
                 │                 │    │
                 │                 │   [ ]  (chiuso = premuto)
                 │                 │    │
                 │             GND ┼────┘
                 └─────────────────┘

  (►|  = LED (anodo verso il GPIO + R, catodo verso GND)
  [R]  = resistenza in serie (~220 Ω)
```

| Segnale | GPIO | Collegamento |
| ------- | ---- | ------------ |
| Carta | 25 | `GPIO25` → R → anodo LED → catodo → `GND` |
| Organico | 26 | `GPIO26` → R → anodo LED → catodo → `GND` |
| Indifferenziata | 27 | `GPIO27` → R → anodo LED → catodo → `GND` |
| Plastica | 14 | `GPIO14` → R → anodo LED → catodo → `GND` |
| Verde | 33 | `GPIO33` → R → anodo LED → catodo → `GND` |
| Vetro | 32 | `GPIO32` → R → anodo LED → catodo → `GND` |
| Pulsante | 4 | un lato `GPIO4`, altro lato `GND` (pull-up interno; niente resistenza esterna obbligatoria) |

Note:

- Un solo `GND` comune per tutti i LED e il pulsante.
- Non collegare i LED direttamente al GPIO senza resistenza.
- Il firmware guida i LED in PWM (`analogWrite`); polarità come sopra (GPIO alto = LED acceso).
- Evita GPIO strapping critici per il boot se cambi i pin in `config.h`.

## Prerequisiti software

- [Arduino IDE](https://www.arduino.cc/en/software) (o Arduino CLI) con core **esp32**
- Scheda: **ESP32 Dev Module** (`Strumenti → Scheda → esp32 → ESP32 Dev Module`)
- Librerie Arduino usate dal firmware: **NTPClient**, **Time** (TimeLib)
- Python 3 (solo se modifichi la webapp e rigeneri l’embed)

## Configurazione (obbligatoria prima del flash)

I file con i tuoi valori reali **non vanno in Git**. Sono ignorati da `.gitignore`.

### 1. Credenziali Wi‑Fi di casa (`secrets.h`)

```bash
cp bin/secrets.h.example bin/secrets.h
```

Apri `bin/secrets.h` e inserisci SSID e password della rete **STA** (quella con internet, usata per NTP):

```cpp
char ssid[] = "NOME_RETE";
char pass[] = "PASSWORD_RETE";
```

### 2. Parametri dispositivo (`config.h`)

```bash
cp bin/config.h.example bin/config.h
```

Cose da sistemare subito in `bin/config.h`:

| Voce                                 | Significato                                                                 |
| ------------------------------------ | --------------------------------------------------------------------------- |
| `ORA_ACCENSIONE` / `ORA_SPEGNIMENTO` | Fascia in cui i LED possono accendersi (es. 18–23)                          |
| `ledPins[]` / `BUTTON_PIN`           | Mapping GPIO al tuo cablaggio                                               |
| `AP_SSID`                            | Nome della rete SoftAP creata dalla ESP                                     |
| `AP_PASSWORD`                        | Password SoftAP (**minimo 8 caratteri**). Sostituisci `CHANGE_ME_MIN8`      |
| `AP_HOSTNAME`                        | Hostname DNS captivo SoftAP (es. `smartbin.home` → `http://smartbin.home/`) |
| `HTTP_API_PORT`                      | Porta HTTP (default `80`)                                                   |
| `NTP_SERVER`                         | Server NTP (default `europe.pool.ntp.org`)                                  |

La SoftAP e la STA possono stare attive insieme: STA per internet/NTP, SoftAP per collegarti direttamente alla web UI dal telefono.

### 3. Calendario raccolta (`calendar.h`)

I calendari stanno in **`docs/calendars/`**, **un file = un anno** (es. `candiolo-z2-2026.h`).  
Ogni file contiene **solo le entry** `{anno, mese, giorno, binIndex}`; struct, helper e `#include` stanno in **`docs/calendar.h`**.  
In repo restano al massimo **due anni** attivi (`years` in `index.json`) per il passaggio di anno; lo storico non si conserva.

**`docs/calendar.h`** è l’alias firmware: include i file anno della zona da flashare. `bin/calendar.h` include quell’alias.

- Nuova zona/anno: `docs/calendars/<comune>-zN-YYYY.h` + vie in `index.json` (campo `calendar` = base senza anno, es. `calendars/candiolo-z2`).
- Provenienza fonti web: `docs/calendars/sources.json` (generato da `tools/build_sources_catalog.py`) per mostrare gestore, pagina sorgente e PDF verificati.
- Aggiorna `years` (max 2) e gli `#include` in `docs/calendar.h`.
- Indici LED: `0` Carta, `1` Organico, `2` Indifferenziata, `3` Plastica, `4` Verde; `-1` = nessun ritiro.
- `datedCalendar[]` ordinata per data (ricerca binaria).

La pagina pubblica (Netlify) chiede comune+via, carica i file anno attivi e unisce le date a runtime.

### 4. (Opzionale) Web UI sul dispositivo

Sorgente UI: `webapp/index.html` (+ `webapp/icon-192.png`).  
Firmware: `bin/web_ui_embed.h` (generato, non editare a mano).

Dopo modifiche alla webapp:

```bash
python tools/embed_webapp.py
```

Poi ricompila e flasha.

## Build e flash

1. Apri `bin/bin.ino` nell’Arduino IDE.
2. Seleziona scheda **ESP32 Dev Module** e la porta seriale corretta.
3. Verifica che esistano `bin/secrets.h` e `bin/config.h`.
4. Compila e carica.

Al boot, sulla seriale vedi diagnostica Wi‑Fi, IP STA e conferma SoftAP.

## Come usare la web UI

**Via SoftAP (senza passare dalla rete di casa):**

1. Connettiti al Wi‑Fi `AP_SSID` con `AP_PASSWORD`.
2. Apri `http://AP_HOSTNAME/` (default `http://smartbin.home/`) oppure l’IP SoftAP stampato in seriale.

**Via LAN (stessa rete della ESP):**

- Apri `http://<IP-STA-della-ESP>/` (IP in seriale dopo `WiFi GOT_IP`).

Dalla UI puoi consultare il calendario e forzare/spegnere i LED (controllo LED consentito dalla rete locale / SoftAP secondo le regole del firmware).

Il **pulsante fisico** alterna override manuale ↔ automatico (secondo click = ritorno all’automatico).

## Calendario pubblico (Netlify)

La cartella `docs/` è il sito statico pubblico (solo consultazione calendario, senza API sulla ESP). Deploy tramite `netlify.toml` in root (`publish = "docs"`).

1. Collega il repo a [Netlify](https://www.netlify.com/).
2. Build: `npm install`; publish directory: `docs` (già in `netlify.toml`).
3. URL tipica: `https://<sito>.netlify.app/` (o dominio custom).

HTTPS di Netlify soddisfa i requisiti PWA (manifest + service worker + “Installa app” su Android Chrome).

### Notifiche push (opzionale)

Web Push gratuito (VAPID + Netlify Functions + Blobs). Dopo il deploy:

1. Genera chiavi: `npx web-push generate-vapid-keys`
2. Su Netlify → Environment variables: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (`mailto:…`), `DISPATCH_SECRET`
3. Su GitHub → Actions secrets: `DISPATCH_SECRET` (stesso valore), `SITE_URL` (URL del sito)
4. Dalla Home, tocca **Ricordami sul telefono** (su iOS: prima Aggiungi a Home, poi opt-in)

Il workflow chiama `/api/push/dispatch` ogni ora (`cron: "5 * * * *"`). Invia solo all’ora scelta dall’utente (default 20:00 Europe/Rome), una volta al giorno, se domani c’è un ritiro.

## Struttura del repository

```
bin/           Firmware Arduino (ino + header)
  *.example    Template da copiare in secrets.h / config.h
webapp/        Sorgente UI embeddata nella ESP
docs/          Sito statico per Netlify (+ PWA / push client)
netlify/       Functions push (subscribe / dispatch)
.github/       Workflow cron dispatch push
netlify.toml   Publish dir + functions + header PWA / calendari
tools/         Script (embed webapp, icone, …)
```

## Licenza

Questo repository è rilasciato sotto **GNU General Public License v3.0** — vedi [LICENSE](LICENSE).

In sintesi (non sostituisce il testo legale): puoi usare, studiare, modificare e ridistribuire il progetto; se **distribuisci** una versione modificata o un binario basato su questo codice, devi rendere disponibile il sorgente corrispondente sotto GPL-3.0.

Librerie e componenti di terze parti (es. NTPClient, Time/TimeLib, core ESP32, font Google nella webapp) restano sotto le **loro** licenze. La GPL-3.0 di questo repo copre il codice originale qui presente.

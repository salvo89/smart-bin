/**
 * PROJECT: SMART BIN INDICATOR (V3 - Resilient Edition)
 * PURPOSE: Visual notification system for waste collection schedules.
 * ARCHITECTURAL NOTE: This script is designed for Arduino UNO R4 WiFi.
 * LOGIC PRIORITY: Network Integrity > DST Awareness > Time Windows > Bin Scheduling.
 */

#include <WiFiS3.h>   // Driver WiFi per Arduino UNO R4 WiFi (ESP32-S3 coprocessor)
#include <NTPClient.h> // Gestione pacchetti UDP per sincronizzazione oraria
#include <WiFiUdp.h>   // Layer di trasporto per NTP
#include <TimeLib.h>   // Manipolazione strutture dati temporali (Unix Epoch)
#include <ArduinoGraphics.h> // Necessario per API testo/disegno della matrice
#include <Arduino_LED_Matrix.h> // Matrice LED integrata Arduino UNO R4 WiFi

// secrets.h e config.h sono in .gitignore: copia da secrets.example.h / config.example.h
#include "secrets.h"
#include "config.h"
#include "calendar.h"
#include "web_api.h"

// --- NETWORK STATE OBJECTS ---
WiFiUDP ntpUDP;

NTPClient timeClient(ntpUDP, NTP_SERVER); 
ArduinoLEDMatrix matrix;
bool calendarOrderInvalid = false;
unsigned long lastWifiReconnectAttemptMs = 0;
unsigned long lastConnectivityDiagMs = 0;

// Toggle manuale:
// - false: logica automatica (fascia oraria + ritiri domani)
// - true : stato forzato opposto rispetto all'automatico
// Il secondo click torna sempre alla modalità automatica.
static bool userLedOverrideActive = false;

static int buttonLastRawReading = HIGH;
static int buttonStableState = HIGH;
static unsigned long buttonLastDebounceMs = 0;
static bool buttonToggleArmed = true;

const unsigned long WIFI_RECONNECT_INTERVAL_MS = 15000;
const unsigned long CONNECTIVITY_DIAG_INTERVAL_MS = 5000;

static unsigned long lastNetAndMainCycleMs = 0;
static bool lastInternetOK = false;
static bool hasSuccessfulTimeSync = false;
static unsigned long offlineSinceMs = 0;

WebApiNetStatus buildWebApiStatus(bool internetOK) {
  WebApiNetStatus s;
  s.calendarOrderInvalid = calendarOrderInvalid;
  s.wifiConnected = (WiFi.status() == WL_CONNECTED);
  s.ntpOk = internetOK;
  if (internetOK && s.wifiConnected) {
    unsigned long ep = timeClient.getEpochTime();
    timeClient.setTimeOffset(getItalianOffset(ep));
    s.epochUtc = (uint32_t)ep;
    s.hourLocal = timeClient.getHours();
  } else {
    s.epochUtc = 0;
    s.hourLocal = -1;
  }
  return s;
}

const char* wifiStatusToString(int status) {
  switch (status) {
    case WL_IDLE_STATUS: return "IDLE";
    case WL_NO_SSID_AVAIL: return "NO_SSID_AVAIL";
    case WL_SCAN_COMPLETED: return "SCAN_COMPLETED";
    case WL_CONNECTED: return "CONNECTED";
    case WL_CONNECT_FAILED: return "CONNECT_FAILED";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_DISCONNECTED: return "DISCONNECTED";
    default: return "UNKNOWN";
  }
}

void mostraWarningCalendarioSuMatrice() {
  static bool showIcon = false;
  if (showIcon) {
    matrix.loadFrame(LEDMATRIX_DANGER);
  } else {
    matrix.clear();
  }
  showIcon = !showIcon;
}

void mostraStatoOKSuMatrice() {
  static uint8_t OK_CORNERS_BITMAP[8][12] = {
    {1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1}
  };
  matrix.renderBitmap(OK_CORNERS_BITMAP, 8, 12);
}

char inizialeCassonetto(int binIndex) {
  switch (binIndex) {
    case 0: return 'C'; // Carta
    case 1: return 'O'; // Organico
    case 2: return 'I'; // Indifferenziata
    case 3: return 'P'; // Plastica
    case 4: return 'V'; // Verde (come calendar.h)
    default: return '?';
  }
}

void mostraInizialeSuMatrice(char initial) {
  matrix.beginDraw();
  matrix.stroke(0xFFFFFFFF);
  matrix.textFont(Font_5x7);
  matrix.beginText(3, 1, 0xFFFFFF);
  matrix.print(initial);
  matrix.endText();
  matrix.endDraw();
}

void mostraMessaggioRitiriSuMatrice(const char* message, bool scrollText) {
  matrix.beginDraw();
  matrix.stroke(0xFFFFFFFF);
  matrix.textFont(Font_5x7);
  if (scrollText) {
    matrix.textScrollSpeed(50);
    matrix.beginText(0, 1, 0xFFFFFF);
    matrix.print(" ");
    matrix.print(message);
    matrix.print(" ");
    matrix.endText(SCROLL_LEFT);
  } else {
    matrix.beginText(0, 1, 0xFFFFFF);
    matrix.print(message);
    matrix.endText();
  }
  matrix.endDraw();
}

static bool inEveningWindow(int hourLocal) {
  return hourLocal >= ORA_ACCENSIONE && hourLocal < ORA_SPEGNIMENTO;
}

/**
 * Carica in binsOut gli indici cassonetto con ritiro domani (stessa logica di calendar.h).
 * Restituisce il numero di elementi scritti (<= maxOut).
 */
int loadTomorrowBins(int* binsOut, int maxOut) {
  unsigned long tomorrowEpoch = timeClient.getEpochTime() + 86400UL;
  int y = year(tomorrowEpoch);
  int m = month(tomorrowEpoch);
  int d = day(tomorrowEpoch);
  uint32_t dateKey = calendarDateKey(y, m, d);

  int count = 0;
  int i = lowerBoundDated(dateKey);
  while (i < datedCalendarCount) {
    const CalendarEntry& entry = datedCalendar[i];
    if (calendarDateKey(entry.year, entry.month, entry.day) != dateKey) {
      break;
    }
    if (entry.binIndex >= 0 && entry.binIndex < numBins) {
      if (count < maxOut) {
        binsOut[count++] = entry.binIndex;
      }
    }
    i++;
  }
  return count;
}

void renderCalendarLedsAndMatrix(const int* binsForTomorrow, int binsForTomorrowCount) {
  spegniTutto();

  for (int j = 0; j < binsForTomorrowCount; j++) {
    int idx = binsForTomorrow[j];
    if (idx >= 0 && idx < numBins) {
      analogWrite(ledPins[idx], 255);
    }
  }

  if (binsForTomorrowCount > 0) {
    char initialsMessage[(numBins * 2)];
    int cursor = 0;
    for (int j = 0; j < binsForTomorrowCount && cursor < (int)sizeof(initialsMessage) - 1; j++) {
      if (j > 0 && cursor < (int)sizeof(initialsMessage) - 1) {
        initialsMessage[cursor++] = '.';
      }
      initialsMessage[cursor++] = inizialeCassonetto(binsForTomorrow[j]);
    }
    initialsMessage[cursor] = '\0';

    const int estimatedTextWidth = cursor * 6;
    const bool needsScroll = estimatedTextWidth > 12;
    mostraMessaggioRitiriSuMatrice(initialsMessage, needsScroll);
  }
}

bool getLedOutputState(bool* outAutoWouldLightAnyLed, bool* outOverrideActive) {
  unsigned long epoch = timeClient.getEpochTime();
  timeClient.setTimeOffset(getItalianOffset(epoch));
  int ora = timeClient.getHours();

  int binsForTomorrow[numBins];
  int binsForTomorrowCount = loadTomorrowBins(binsForTomorrow, numBins);

  const bool autoWouldLightAnyLed = inEveningWindow(ora) && (binsForTomorrowCount > 0);
  const bool showLeds =
      userLedOverrideActive ? !autoWouldLightAnyLed : autoWouldLightAnyLed;

  if (outAutoWouldLightAnyLed) {
    *outAutoWouldLightAnyLed = autoWouldLightAnyLed;
  }
  if (outOverrideActive) {
    *outOverrideActive = userLedOverrideActive;
  }
  return showLeds;
}

void applyBinScheduleDisplay() {
  mostraStatoOKSuMatrice();

  int binsForTomorrow[numBins];
  int binsForTomorrowCount = loadTomorrowBins(binsForTomorrow, numBins);

  const bool showLeds = getLedOutputState(nullptr, nullptr);

  if (showLeds) {
    renderCalendarLedsAndMatrix(binsForTomorrow, binsForTomorrowCount);
  } else {
    spegniTutto();
  }
}

bool toggleUserLedOverride() {
  userLedOverrideActive = !userLedOverrideActive;
  applyBinScheduleDisplay();
  return userLedOverrideActive;
}

void pollManualLedButton() {
  const int reading = digitalRead(BUTTON_PIN);

  if (reading != buttonLastRawReading) {
    buttonLastDebounceMs = millis();
    buttonLastRawReading = reading;
  }

  if ((millis() - buttonLastDebounceMs) < BUTTON_DEBOUNCE_MS) {
    return;
  }

  if (reading != buttonStableState) {
    buttonStableState = reading;
    if (buttonStableState == HIGH) {
      // Riarmo solo a bottone rilasciato: impedisce doppi toggle sullo stesso click.
      buttonToggleArmed = true;
    } else if (buttonToggleArmed) {
      buttonToggleArmed = false;
      toggleUserLedOverride();
    }
  }
}

void setup() {
  Serial.begin(9600);
  matrix.begin();
  
  // Inizializzazione IO: Configura i pin come uscite
  for(int i=0; i<numBins; i++) pinMode(ledPins[i], OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  buttonLastRawReading = digitalRead(BUTTON_PIN);
  buttonStableState = buttonLastRawReading;
  buttonLastDebounceMs = millis();
  buttonToggleArmed = (buttonStableState == HIGH);

  int unsortedIndex = firstUnsortedCalendarIndex();
  if (unsortedIndex >= 0) {
    calendarOrderInvalid = true;
    Serial.print("Warning: calendar non ordinato. Primo indice errato: ");
    Serial.println(unsortedIndex);
    mostraWarningCalendarioSuMatrice();
  }
  
  // Avvio non bloccante della connessione
  WiFi.begin(ssid, pass);
  timeClient.begin();
  webApiBegin();
  Serial.print("HTTP API on port ");
  Serial.println(HTTP_API_PORT);
}

/**
 * MAIN EXECUTION LOOP
 * Logic flow: 
 * 1. Health Check (Internet)
 * 2. Time Sync & Correction
 * 3. State Evaluation (Active Window vs Sleep)
 * 4. IO Execution
 */
void loop() {
  unsigned long now = millis();
  const bool cycleTick =
      (lastNetAndMainCycleMs == 0) || (now - lastNetAndMainCycleMs >= LOOP_DELAY_MS);
  if (cycleTick) {
    lastNetAndMainCycleMs = now;
    // Evita forceUpdate NTP ad ogni millisecondo: stesso ritmo del loop storico (~LOOP_DELAY_MS).
    lastInternetOK = checkInternet();
    if (lastInternetOK) {
      hasSuccessfulTimeSync = true;
      offlineSinceMs = 0;
    } else if (hasSuccessfulTimeSync && offlineSinceMs == 0) {
      offlineSinceMs = now;
    }
  }

  WebApiNetStatus apiSt = buildWebApiStatus(lastInternetOK);
  webApiPoll(apiSt);

  if (!calendarOrderInvalid && lastInternetOK && (WiFi.status() == WL_CONNECTED)) {
    pollManualLedButton();
  }

  if (calendarOrderInvalid) {
    static unsigned long lastWarnToggleMs = 0;
    if (millis() - lastWarnToggleMs >= 500) {
      lastWarnToggleMs = millis();
      mostraWarningCalendarioSuMatrice();
    }
    delay(1);
    return;
  }

  if (!cycleTick) {
    delay(1);
    return;
  }

  // Verifica connettività basata sul servizio NTP:
  // consideriamo "online" solo se l'aggiornamento orario riesce.
  // Tolleranza disconnessione: se avevamo già sincronizzato almeno una volta,
  // attendiamo alcuni minuti prima di mostrare la danza di errore.
  bool triggerOfflineAlarm = false;
  if (!lastInternetOK) {
    if (!hasSuccessfulTimeSync) {
      triggerOfflineAlarm = true;
    } else if (offlineSinceMs != 0 &&
               (now - offlineSinceMs) >= NETWORK_GRACE_BEFORE_LED_ALARM_MS) {
      triggerOfflineAlarm = true;
    }
  }

  if (triggerOfflineAlarm) {
    matrix.clear();
    eseguiDanzaErrore(apiSt);
  } else {
    /** * OPERATIONAL STATE: Sistema sincronizzato.
     * LED e matrice: finestra serale + calendario (domani), con inversione opzionale dal pulsante.
     */
    applyBinScheduleDisplay();
  }
}

/**
 * ANIMAZIONE DI ERRORE (Stadium Wave)
 * Ogni LED cresce e cala di intensita' (triangolare), sfalsato rispetto al successivo.
 * L'avvio sfalsato crea una "ola" continua con sovrapposizione tra i picchi.
 */
void eseguiDanzaErrore(const WebApiNetStatus& apiSt) {
  Serial.println("Warning: Network Unreachable. Executing stadium wave.");

  const int maxBrightness = 255;
  const int waveFrames = 72;           // Durata completa su-singolo LED (su + giu).
  const int phaseOffsetFrames = 18;    // Avvio del LED successivo prima che il precedente finisca.
  const int frameDelayMs = 14;
  const int halfWave = waveFrames / 2;
  const int totalFrames = waveFrames + (numBins - 1) * phaseOffsetFrames;

  for (int frame = 0; frame <= totalFrames; frame++) {
    for (int i = 0; i < numBins; i++) {
      int localFrame = frame - (i * phaseOffsetFrames);
      int brightness = 0;

      if (localFrame >= 0 && localFrame <= waveFrames) {
        if (localFrame <= halfWave) {
          brightness = map(localFrame, 0, halfWave, 0, maxBrightness);
        } else {
          brightness = map(localFrame, halfWave, waveFrames, maxBrightness, 0);
        }
      }

      analogWrite(ledPins[i], brightness);
    }

    webApiPoll(apiSt);
    delay(frameDelayMs);
  }
}

void spegniTutto() {
  for(int i=0; i<numBins; i++) analogWrite(ledPins[i], 0);
}

/**
 * LAYER DI VERIFICA CONNETTIVITÀ
 * Rete considerata valida solo se il servizio NTP risponde.
 */
bool checkInternet() {
  int status = WiFi.status();
  unsigned long now = millis();

  if (status != WL_CONNECTED) {
    if (now - lastConnectivityDiagMs >= CONNECTIVITY_DIAG_INTERVAL_MS) {
      Serial.print("WiFi status: ");
      Serial.print(wifiStatusToString(status));
      Serial.print(" (");
      Serial.print(status);
      Serial.println(")");
      lastConnectivityDiagMs = now;
    }

    // Evita di riavviare continuamente il join (puo' impedire la connessione stabile).
    if (now - lastWifiReconnectAttemptMs >= WIFI_RECONNECT_INTERVAL_MS) {
      Serial.println("WiFi reconnect attempt...");
      WiFi.begin(ssid, pass);
      lastWifiReconnectAttemptMs = now;
    }
    return false;
  }

  bool ntpOK = timeClient.forceUpdate();
  if (!ntpOK) {
    if (now - lastConnectivityDiagMs >= CONNECTIVITY_DIAG_INTERVAL_MS) {
      Serial.println("NTP update failed (UDP/123 blocked or NTP server unreachable).");
      lastConnectivityDiagMs = now;
    }
    return false;
  }

  if (now - lastConnectivityDiagMs >= CONNECTIVITY_DIAG_INTERVAL_MS) {
    Serial.print("Network OK. IP: ");
    Serial.println(WiFi.localIP());
    lastConnectivityDiagMs = now;
  }
  return true;
}

/**
 * CALCOLO DST (Daylight Saving Time) EUROPEO
 * Formula per l'automazione del cambio ora Legale/Solare.
 * Logica: Inizio ultima domenica di Marzo (02:00), Fine ultima domenica di Ottobre (03:00).
 */
long getItalianOffset(unsigned long epochTime) {
    int y = year(epochTime); int m = month(epochTime); int d = day(epochTime); int h = hour(epochTime);
    // Algoritmo per determinare le date mobili delle domeniche di switch
    int beginDST = (31 - (5 * y / 4 + 4) % 7); 
    int endDST = (31 - (5 * y / 4 + 1) % 7);
    
    // Comparazione temporale per determinare l'offset UTC
    if ((m > 3 && m < 10) || (m == 3 && d > beginDST) || (m == 3 && d == beginDST && h >= 2) || (m == 10 && d < endDST) || (m == 10 && d == endDST && h < 3)) {
        return 7200; // +2 ore (Legale)
    }
    return 3600; // +1 ora (Solare)
}
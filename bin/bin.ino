/**
 * PROJECT: SMART BIN INDICATOR (V3 - Resilient Edition)
 * PURPOSE: Visual notification system for waste collection schedules.
 * ARCHITECTURAL NOTE: Firmware per ESP32 (DevKit / ESP32-WROOM-32).
 * LOGIC PRIORITY: Network Integrity > DST Awareness > Time Windows > Bin Scheduling.
 */

#ifndef ESP32
#error "Seleziona una scheda ESP32: Strumenti > Scheda > esp32 > ESP32 Dev Module"
#endif

#include <WiFi.h>
#include <esp_wifi_types.h>
#include <NTPClient.h>
#include <WiFiUdp.h>
#include <TimeLib.h>

#include "secrets.h"
#include "config.h"
#include "calendar.h"
#include "web_api.h"

// --- NETWORK STATE OBJECTS ---
WiFiUDP ntpUDP;

NTPClient timeClient(ntpUDP, NTP_SERVER);
bool calendarOrderInvalid = false;
unsigned long lastWifiReconnectAttemptMs = 0;
unsigned long lastConnectivityDiagMs = 0;

// Toggle manuale:
// - false: logica automatica (fascia oraria + ritiri domani)
// - true : stato forzato opposto rispetto all'automatico
// Il secondo click torna sempre alla modalità automatica.
static bool userLedOverrideActive = false;
// >= 0: luminosità forzata da web; -1: segue calendario/fascia oraria
static int userLedBinOverride[numBins];

void applyBinScheduleDisplay();

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
static unsigned long bootStartMs = 0;
static int lastWifiDisconnectReason = -1;
static bool wifiStartupScanDone = false;

const char* wifiDisconnectReasonToString(int reason) {
  switch (reason) {
    case WIFI_REASON_UNSPECIFIED: return "UNSPECIFIED";
    case WIFI_REASON_AUTH_EXPIRE: return "AUTH_EXPIRE";
    case WIFI_REASON_AUTH_LEAVE: return "AUTH_LEAVE";
    case WIFI_REASON_ASSOC_EXPIRE: return "ASSOC_EXPIRE";
    case WIFI_REASON_ASSOC_TOOMANY: return "ASSOC_TOOMANY";
    case WIFI_REASON_NOT_AUTHED: return "NOT_AUTHED";
    case WIFI_REASON_NOT_ASSOCED: return "NOT_ASSOCED";
    case WIFI_REASON_ASSOC_LEAVE: return "ASSOC_LEAVE";
    case WIFI_REASON_ASSOC_NOT_AUTHED: return "ASSOC_NOT_AUTHED";
    case WIFI_REASON_DISASSOC_PWRCAP_BAD: return "DISASSOC_PWRCAP_BAD";
    case WIFI_REASON_DISASSOC_SUPCHAN_BAD: return "DISASSOC_SUPCHAN_BAD";
    case WIFI_REASON_IE_INVALID: return "IE_INVALID";
    case WIFI_REASON_MIC_FAILURE: return "MIC_FAILURE";
    case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT: return "4WAY_HANDSHAKE_TIMEOUT (password errata?)";
    case WIFI_REASON_GROUP_KEY_UPDATE_TIMEOUT: return "GROUP_KEY_UPDATE_TIMEOUT";
    case WIFI_REASON_IE_IN_4WAY_DIFFERS: return "IE_IN_4WAY_DIFFERS";
    case WIFI_REASON_GROUP_CIPHER_INVALID: return "GROUP_CIPHER_INVALID";
    case WIFI_REASON_PAIRWISE_CIPHER_INVALID: return "PAIRWISE_CIPHER_INVALID";
    case WIFI_REASON_AKMP_INVALID: return "AKMP_INVALID";
    case WIFI_REASON_UNSUPP_RSN_IE_VERSION: return "UNSUPP_RSN_IE_VERSION";
    case WIFI_REASON_INVALID_RSN_IE_CAP: return "INVALID_RSN_IE_CAP";
    case WIFI_REASON_802_1X_AUTH_FAILED: return "802_1X_AUTH_FAILED";
    case WIFI_REASON_CIPHER_SUITE_REJECTED: return "CIPHER_SUITE_REJECTED";
    case WIFI_REASON_BEACON_TIMEOUT: return "BEACON_TIMEOUT";
    case WIFI_REASON_NO_AP_FOUND: return "NO_AP_FOUND (SSID non trovato / fuori range)";
    case WIFI_REASON_AUTH_FAIL: return "AUTH_FAIL (password errata o WPA incompatibile)";
    case WIFI_REASON_ASSOC_FAIL: return "ASSOC_FAIL";
    case WIFI_REASON_HANDSHAKE_TIMEOUT: return "HANDSHAKE_TIMEOUT";
    case WIFI_REASON_CONNECTION_FAIL: return "CONNECTION_FAIL";
    default: return "UNKNOWN";
  }
}

void printStringHex(const __FlashStringHelper* label, const char* text) {
  Serial.print(label);
  if (!text) {
    Serial.println(F("(null)"));
    return;
  }
  for (size_t i = 0; text[i] != '\0'; i++) {
    if (i > 0) {
      Serial.print(' ');
    }
    uint8_t b = static_cast<uint8_t>(text[i]);
    if (b < 16) {
      Serial.print('0');
    }
    Serial.print(b, HEX);
  }
  Serial.println();
}

void onWifiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_START:
      Serial.println(F("[WiFi] STA avviato"));
      break;
    case ARDUINO_EVENT_WIFI_STA_CONNECTED:
      Serial.print(F("[WiFi] Associato all'AP, BSSID "));
      Serial.println(WiFi.BSSIDstr());
      break;
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.print(F("[WiFi] IP assegnato: "));
      Serial.println(WiFi.localIP());
      Serial.print(F("[WiFi] Gateway: "));
      Serial.println(WiFi.gatewayIP());
      Serial.print(F("[WiFi] DNS: "));
      Serial.println(WiFi.dnsIP());
      Serial.print(F("[WiFi] RSSI: "));
      Serial.print(WiFi.RSSI());
      Serial.println(F(" dBm"));
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      lastWifiDisconnectReason = info.wifi_sta_disconnected.reason;
      Serial.print(F("[WiFi] Disconnesso, reason="));
      Serial.print(lastWifiDisconnectReason);
      Serial.print(F(" ("));
      Serial.print(wifiDisconnectReasonToString(lastWifiDisconnectReason));
      Serial.println(F(")"));
      break;
    default:
      break;
  }
}

void logWifiStartupDiagnostics() {
  Serial.println(F("--- Diagnostica WiFi ---"));
  Serial.print(F("MAC STA: "));
  Serial.println(WiFi.macAddress());
  Serial.print(F("SSID configurato: \""));
  Serial.print(ssid);
  Serial.println(F("\""));
  Serial.print(F("Lunghezza SSID: "));
  Serial.println(strlen(ssid));
  Serial.print(F("Lunghezza password: "));
  Serial.println(strlen(pass));
  printStringHex(F("SSID hex: "), ssid);

  Serial.println(F("Scan reti (2.4 GHz)..."));
  int networkCount = WiFi.scanNetworks(/*async=*/false, /*show_hidden=*/true);
  if (networkCount <= 0) {
    Serial.println(F("Nessuna rete trovata (segnale debole o radio spenta)."));
    return;
  }

  Serial.print(F("Reti visibili: "));
  Serial.println(networkCount);

  bool targetFound = false;
  int targetRssi = -999;
  int targetChannel = 0;
  wifi_auth_mode_t targetAuth = WIFI_AUTH_OPEN;

  for (int i = 0; i < networkCount; i++) {
    Serial.print(F("  ["));
    Serial.print(i);
    Serial.print(F("] \""));
    Serial.print(WiFi.SSID(i));
    Serial.print(F("\" RSSI="));
    Serial.print(WiFi.RSSI(i));
    Serial.print(F(" dBm ch="));
    Serial.print(WiFi.channel(i));
    Serial.print(F(" auth="));
    Serial.print(WiFi.encryptionType(i));
    if (WiFi.SSID(i) == ssid) {
      Serial.print(F("  <-- TARGET"));
      targetFound = true;
      targetRssi = WiFi.RSSI(i);
      targetChannel = WiFi.channel(i);
      targetAuth = WiFi.encryptionType(i);
    }
    Serial.println();
  }

  if (targetFound) {
    Serial.print(F("TARGET trovato: RSSI="));
    Serial.print(targetRssi);
    Serial.print(F(" dBm, canale="));
    Serial.print(targetChannel);
    Serial.print(F(", auth="));
    Serial.println(targetAuth);
  } else {
    Serial.println(F("ATTENZIONE: SSID configurato NON compare nella scan."));
    Serial.println(F("Possibili cause: rete solo 5 GHz, SSID errato, caratteri nascosti, AP spento."));
  }
  Serial.println(F("--- Fine diagnostica ---"));
}

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

static void clearUserLedBinOverrides() {
  for (int i = 0; i < numBins; i++) {
    userLedBinOverride[i] = -1;
  }
}

void setUserLedBinOverride(int bin, int value) {
  if (bin < 0 || bin >= numBins || value < 0 || value > 255) {
    return;
  }
  userLedBinOverride[bin] = value;
  applyBinScheduleDisplay();
}

void resetLedsToCalendarSchedule() {
  userLedOverrideActive = false;
  clearUserLedBinOverrides();
  applyBinScheduleDisplay();
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

static void computeScheduledBinLevels(bool* scheduledOnOut) {
  for (int i = 0; i < numBins; i++) {
    scheduledOnOut[i] = false;
  }

  int binsForTomorrow[numBins];
  int binsForTomorrowCount = loadTomorrowBins(binsForTomorrow, numBins);
  const bool showLeds = getLedOutputState(nullptr, nullptr);

  if (!showLeds) {
    return;
  }

  for (int j = 0; j < binsForTomorrowCount; j++) {
    int idx = binsForTomorrow[j];
    if (idx >= 0 && idx < numBins) {
      scheduledOnOut[idx] = true;
    }
  }
}

void applyBinScheduleDisplay() {
  bool scheduledOn[numBins];
  computeScheduledBinLevels(scheduledOn);

  for (int i = 0; i < numBins; i++) {
    const int level =
        userLedBinOverride[i] >= 0 ? userLedBinOverride[i] : (scheduledOn[i] ? 255 : 0);
    analogWrite(ledPins[i], level);
  }
}

void getEffectiveLedLevels(int* levelsOut, int maxBins) {
  if (!levelsOut || maxBins <= 0) {
    return;
  }
  const int n = maxBins < numBins ? maxBins : numBins;
  bool scheduledOn[numBins];
  computeScheduledBinLevels(scheduledOn);
  for (int i = 0; i < n; i++) {
    levelsOut[i] =
        userLedBinOverride[i] >= 0 ? userLedBinOverride[i] : (scheduledOn[i] ? 255 : 0);
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
  Serial.begin(115200);
  delay(300);
  bootStartMs = millis();

  for (int i = 0; i < numBins; i++) {
    pinMode(ledPins[i], OUTPUT);
  }
  clearUserLedBinOverrides();
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  buttonLastRawReading = digitalRead(BUTTON_PIN);
  buttonStableState = buttonLastRawReading;
  buttonLastDebounceMs = millis();
  buttonToggleArmed = (buttonStableState == HIGH);

  int unsortedIndex = firstUnsortedCalendarIndex();
  if (unsortedIndex >= 0) {
    calendarOrderInvalid = true;
    Serial.print(F("Warning: calendar non ordinato. Primo indice errato: "));
    Serial.println(unsortedIndex);
  }

  WiFi.persistent(false);
  WiFi.onEvent(onWifiEvent);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(WIFI_PS_NONE);
  WiFi.setAutoReconnect(true);
  // Cancella credenziali WiFi salvate in flash (spesso diverse da secrets.h).
  WiFi.disconnect(true, true);
  delay(200);
  logWifiStartupDiagnostics();
  wifiStartupScanDone = true;
  WiFi.begin(ssid, pass);
  Serial.println(F("WiFi.begin() avviato (credenziali da secrets.h, flash pulita)..."));
  timeClient.begin();
  webApiBegin();
  Serial.print(F("HTTP API on port "));
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
    delay(1);
    return;
  }

  if (!cycleTick) {
    delay(1);
    return;
  }

  bool triggerOfflineAlarm = false;
  if (!lastInternetOK) {
    if (!hasSuccessfulTimeSync) {
      if ((now - bootStartMs) >= BOOT_WIFI_GRACE_MS) {
        triggerOfflineAlarm = true;
      }
    } else if (offlineSinceMs != 0 &&
               (now - offlineSinceMs) >= NETWORK_GRACE_BEFORE_LED_ALARM_MS) {
      triggerOfflineAlarm = true;
    }
  }

  if (triggerOfflineAlarm) {
    eseguiDanzaErrore(apiSt);
  } else if (!lastInternetOK && !hasSuccessfulTimeSync) {
    spegniTutto();
  } else {
    applyBinScheduleDisplay();
  }
}

/**
 * ANIMAZIONE DI ERRORE (Stadium Wave)
 * Ogni LED cresce e cala di intensita' (triangolare), sfalsato rispetto al successivo.
 */
void eseguiDanzaErrore(const WebApiNetStatus& apiSt) {
  Serial.println(F("Warning: Network Unreachable. Executing stadium wave."));

  const int maxBrightness = 255;
  const int waveFrames = 72;
  const int phaseOffsetFrames = 18;
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
  for (int i = 0; i < numBins; i++) {
    analogWrite(ledPins[i], 0);
  }
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
      Serial.print(F("WiFi status: "));
      Serial.print(wifiStatusToString(status));
      Serial.print(F(" ("));
      Serial.print(status);
      Serial.println(F(")"));
      if (lastWifiDisconnectReason >= 0) {
        Serial.print(F("Ultimo disconnect reason: "));
        Serial.print(lastWifiDisconnectReason);
        Serial.print(F(" ("));
        Serial.print(wifiDisconnectReasonToString(lastWifiDisconnectReason));
        Serial.println(F(")"));
      }
      if (!hasSuccessfulTimeSync && (now - bootStartMs) < BOOT_WIFI_GRACE_MS) {
        Serial.print(F("Attesa connessione WiFi: "));
        Serial.print((now - bootStartMs) / 1000UL);
        Serial.print(F("s / "));
        Serial.print(BOOT_WIFI_GRACE_MS / 1000UL);
        Serial.println(F("s (allarme LED disattivato)"));
      }
      Serial.print(F("MAC: "));
      Serial.println(WiFi.macAddress());
      lastConnectivityDiagMs = now;
    }

    if (now - lastWifiReconnectAttemptMs >= WIFI_RECONNECT_INTERVAL_MS) {
      Serial.println(F("WiFi reconnect attempt..."));
      if (!wifiStartupScanDone) {
        logWifiStartupDiagnostics();
        wifiStartupScanDone = true;
      }
      WiFi.disconnect(false);
      delay(100);
      WiFi.begin(ssid, pass);
      lastWifiReconnectAttemptMs = now;
    }
    return false;
  }

  bool ntpOK = timeClient.forceUpdate();
  if (!ntpOK) {
    if (now - lastConnectivityDiagMs >= CONNECTIVITY_DIAG_INTERVAL_MS) {
      Serial.println(F("NTP update failed (UDP/123 blocked or NTP server unreachable)."));
      lastConnectivityDiagMs = now;
    }
    return false;
  }

  if (now - lastConnectivityDiagMs >= CONNECTIVITY_DIAG_INTERVAL_MS) {
    Serial.print(F("Network OK. IP: "));
    Serial.println(WiFi.localIP());
    lastConnectivityDiagMs = now;
  }
  return true;
}

/**
 * CALCOLO DST (Daylight Saving Time) EUROPEO
 */
long getItalianOffset(unsigned long epochTime) {
  int y = year(epochTime);
  int m = month(epochTime);
  int d = day(epochTime);
  int h = hour(epochTime);
  int beginDST = (31 - (5 * y / 4 + 4) % 7);
  int endDST = (31 - (5 * y / 4 + 1) % 7);

  if ((m > 3 && m < 10) || (m == 3 && d > beginDST) || (m == 3 && d == beginDST && h >= 2) ||
      (m == 10 && d < endDST) || (m == 10 && d == endDST && h < 3)) {
    return 7200;
  }
  return 3600;
}

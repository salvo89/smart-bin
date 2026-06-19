#ifndef SMART_BIN_WEB_API_H
#define SMART_BIN_WEB_API_H

#include <Arduino.h>
#include <WiFi.h>
#include <TimeLib.h>
#include <string.h>
#include <stdio.h>
#include "config.h"
#include "calendar.h"
#include "web_ui_embed.h"

struct WebApiNetStatus {
  bool wifiConnected;
  bool ntpOk;
  uint32_t epochUtc;
  int hourLocal;
  bool calendarOrderInvalid;
};

void spegniTutto();
void turnOffAllLedsFromUser();
bool toggleUserLedOverride();
bool getLedOutputState(bool* outAutoWouldLightAnyLed, bool* outOverrideActive);
void setUserLedBinOverride(int bin, int value);
void resetLedsToCalendarSchedule();
void getEffectiveLedLevels(int* levelsOut, int maxBins);

static int formatLedStateJson(char* body, size_t bodySize) {
  bool autoWouldLightAnyLed = false;
  bool overrideActive = false;
  const bool on = getLedOutputState(&autoWouldLightAnyLed, &overrideActive);
  int levels[numBins];
  getEffectiveLedLevels(levels, numBins);

  int L = snprintf(body, bodySize,
                   "{\"ok\":true,\"override\":%s,\"auto\":%s,\"on\":%s,\"bins\":[",
                   overrideActive ? "true" : "false",
                   autoWouldLightAnyLed ? "true" : "false",
                   on ? "true" : "false");
  for (int i = 0; i < numBins && L + 12 < (int)bodySize; i++) {
    if (i) {
      body[L++] = ',';
    }
    L += snprintf(body + L, bodySize - L, "%d", levels[i]);
  }
  if (L + 4 < (int)bodySize) {
    snprintf(body + L, bodySize - L, "]}");
  }
  return L;
}

static WiFiServer g_httpServer(HTTP_API_PORT);

static int collectBinsForYmd(int y, int m, int d, int* outBins, int maxBins) {
  uint32_t key = calendarDateKey(y, m, d);
  int i = lowerBoundDated(key);
  int n = 0;
  while (i < datedCalendarCount && n < maxBins) {
    const CalendarEntry& e = datedCalendar[i];
    if (calendarDateKey(e.year, e.month, e.day) != key) {
      break;
    }
    if (e.binIndex >= 0 && e.binIndex < numBins) {
      outBins[n++] = e.binIndex;
    }
    i++;
  }
  return n;
}

static char binInitialFromIndex(int binIndex) {
  switch (binIndex) {
    case 0: return 'C';
    case 1: return 'O';
    case 2: return 'I';
    case 3: return 'P';
    case 4: return 'V'; // Verde
    default: return '?';
  }
}

static void sendHttp(WiFiClient& client, int code, const char* contentType, const char* body) {
  client.print(F("HTTP/1.1 "));
  client.print(code);
  client.print(' ');
  switch (code) {
    case 200:
      client.print(F("OK"));
      break;
    case 204:
      client.print(F("No Content"));
      break;
    case 400:
      client.print(F("Bad Request"));
      break;
    case 404:
      client.print(F("Not Found"));
      break;
    case 503:
      client.print(F("Service Unavailable"));
      break;
    default:
      client.print(F("OK"));
      break;
  }
  client.print(F("\r\nConnection: close\r\n"));
  if (code != 204) {
    client.print(F("Content-Type: "));
    client.print(contentType);
    client.print(F("\r\n"));
  }
  // CORS + Private Network Access (Chrome: pagina pubblica/https → API su LAN)
  client.print(F("Access-Control-Allow-Origin: *\r\n"));
  client.print(F("Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"));
  client.print(
      F("Access-Control-Allow-Headers: Content-Type, Accept, Cache-Control, Pragma\r\n"));
  client.print(F("Access-Control-Allow-Private-Network: true\r\n"));
  client.print(F("Access-Control-Max-Age: 86400\r\n"));
  client.print(F("\r\n"));
  if (body) {
    client.print(body);
  }
}

static int parseIntParam(const char* query, const char* key, int defaultValue) {
  const char* p = strstr(query, key);
  if (!p) {
    return defaultValue;
  }
  if (p != query && p[-1] != '&' && p[-1] != '?') {
    return defaultValue;
  }
  p += strlen(key);
  if (*p != '=') {
    return defaultValue;
  }
  return atoi(p + 1);
}

static int daysInMonthCal(int y, int m) {
  static const uint8_t md[12] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  if (m < 1 || m > 12) {
    return 31;
  }
  int d = md[m - 1];
  if (m == 2) {
    const bool leap = (y % 4 == 0 && y % 100 != 0) || (y % 400 == 0);
    if (leap) {
      d = 29;
    }
  }
  return d;
}

static bool parseYearMonthOnly(const char* query, int* y, int* m) {
  int yy = parseIntParam(query, "y", -1);
  int mm = parseIntParam(query, "m", -1);
  if (yy < 2000 || yy > 2100 || mm < 1 || mm > 12) {
    return false;
  }
  *y = yy;
  *m = mm;
  return true;
}

static bool parseDateParam(const char* query, int* y, int* m, int* d) {
  const char* p = strstr(query, "date=");
  if (p && (p == query || p[-1] == '&' || p[-1] == '?')) {
    p += 5;
    *y = atoi(p);
    const char* dash1 = strchr(p, '-');
    if (!dash1) {
      return false;
    }
    *m = atoi(dash1 + 1);
    const char* dash2 = strchr(dash1 + 1, '-');
    if (!dash2) {
      return false;
    }
    *d = atoi(dash2 + 1);
    return (*y > 2000 && *m >= 1 && *m <= 12 && *d >= 1 && *d <= 31);
  }
  int yy = parseIntParam(query, "y", -1);
  int mm = parseIntParam(query, "m", -1);
  int dd = parseIntParam(query, "d", -1);
  if (yy < 0 || mm < 0 || dd < 0) {
    return false;
  }
  *y = yy;
  *m = mm;
  *d = dd;
  return (*y > 2000 && *m >= 1 && *m <= 12 && *d >= 1 && *d <= 31);
}

static void sendDashboardHtml(WiFiClient& client) {
  const size_t totalLen = SMART_BIN_WEB_UI_GZ_LEN;
  client.print(F("HTTP/1.1 200 OK\r\nConnection: close\r\n"));
  client.print(F("Content-Type: text/html; charset=utf-8\r\n"));
  client.print(F("Content-Encoding: gzip\r\n"));
  client.print(F("Content-Length: "));
  client.print((unsigned long)totalLen);
  client.print(F("\r\n"));
  client.print(F("Access-Control-Allow-Origin: *\r\n"));
  client.print(F("Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"));
  client.print(
      F("Access-Control-Allow-Headers: Content-Type, Accept, Cache-Control, Pragma\r\n"));
  client.print(F("Access-Control-Allow-Private-Network: true\r\n"));
  client.print(F("Access-Control-Max-Age: 86400\r\n"));
  client.print(F("\r\n"));

  const size_t chunkSz = 512;
  uint8_t buf[512];
  size_t off = 0;
  while (off < SMART_BIN_WEB_UI_GZ_LEN) {
    size_t n = SMART_BIN_WEB_UI_GZ_LEN - off;
    if (n > chunkSz) {
      n = chunkSz;
    }
    memcpy(buf, SMART_BIN_WEB_UI_GZ + off, n);
    const size_t w = client.write(buf, n);
    if (w != n) {
      break;
    }
    off += n;
  }
}

static void handleHttpRequest(WiFiClient& client, const WebApiNetStatus& st) {
  String line = client.readStringUntil('\n');
  line.trim();
  while (client.connected() && client.available()) {
    String h = client.readStringUntil('\n');
    if (h.length() <= 1) {
      break;
    }
  }

  char raw[180];
  line.toCharArray(raw, sizeof(raw));
  char method[8] = {0};
  char uri[140] = {0};
  if (sscanf(raw, "%7s %139s", method, uri) != 2) {
    sendHttp(client, 400, "application/json", "{\"error\":\"bad_request\"}");
    return;
  }

  char path[96] = {0};
  char query[128] = {0};
  const char* qmark = strchr(uri, '?');
  if (qmark) {
    size_t plen = (size_t)(qmark - uri);
    if (plen >= sizeof(path)) {
      plen = sizeof(path) - 1;
    }
    if (plen == 0) {
      path[0] = '/';
      path[1] = '\0';
    } else {
      memcpy(path, uri, plen);
      path[plen] = '\0';
    }
    strncpy(query, qmark + 1, sizeof(query) - 1);
    query[sizeof(query) - 1] = '\0';
  } else {
    strncpy(path, uri, sizeof(path) - 1);
    path[sizeof(path) - 1] = '\0';
  }

  if (strcmp(method, "OPTIONS") == 0) {
    sendHttp(client, 204, "text/plain", "");
    return;
  }

  if (strcmp(method, "GET") == 0 &&
      (strcmp(path, "/") == 0 || strcmp(path, "/index.html") == 0)) {
    sendDashboardHtml(client);
    return;
  }

  if (strcmp(path, "/api/status") == 0 && strcmp(method, "GET") == 0) {
    char buf[192];
    snprintf(buf, sizeof(buf),
             "{\"wifi\":%s,\"ntp\":%s,\"epoch\":%lu,\"hourLocal\":%d,"
             "\"calendarOrderInvalid\":%s}",
             st.wifiConnected ? "true" : "false",
             st.ntpOk ? "true" : "false",
             (unsigned long)st.epochUtc,
             st.hourLocal,
             st.calendarOrderInvalid ? "true" : "false");
    sendHttp(client, 200, "application/json", buf);
    return;
  }

  if (strcmp(path, "/api") == 0 && strcmp(method, "GET") == 0) {
    sendHttp(client, 200, "application/json",
              "{\"endpoints\":[\"/api/status\",\"/api/calendar/date\","
              "\"/api/calendar/month\",\"/api/calendar/tomorrow\","
              "\"/api/action/led?bin=&value=\",\"/api/action/leds/off\","
              "\"/api/action/leds/toggle\",\"/api/action/leds/state\"]}");
    return;
  }

  if (strcmp(path, "/api/calendar/month") == 0 && strcmp(method, "GET") == 0) {
    int y = 0, m = 0;
    if (!parseYearMonthOnly(query, &y, &m)) {
      sendHttp(client, 400, "application/json", "{\"error\":\"use y=&m=\"}");
      return;
    }
    const int D = daysInMonthCal(y, m);
    // JSON compatto: i[k] = iniziali giorno k+1 (stesso formato "C.O" di /date), ~≤1 KiB.
    static char monthJson[1400];
    int L = snprintf(monthJson, sizeof(monthJson), "{\"y\":%d,\"m\":%d,\"n\":%d,\"i\":[", y, m, D);
    if (L < 0 || L >= (int)sizeof(monthJson) - 8) {
      sendHttp(client, 500, "application/json", "{\"error\":\"month_buffer\"}");
      return;
    }
    for (int d = 1; d <= D; d++) {
      // ~24 byte/giorno nel caso peggiore → 31*24 < 800; margine su 1400.
      if (L >= (int)sizeof(monthJson) - 48) {
        sendHttp(client, 500, "application/json", "{\"error\":\"month_overflow\"}");
        return;
      }
      if (d > 1) {
        monthJson[L++] = ',';
      }
      monthJson[L++] = '"';
      int bins[8];
      const int n = collectBinsForYmd(y, m, d, bins, 8);
      for (int i = 0; i < n && L < (int)sizeof(monthJson) - 4; i++) {
        if (i) {
          monthJson[L++] = '.';
        }
        monthJson[L++] = binInitialFromIndex(bins[i]);
      }
      monthJson[L++] = '"';
    }
    if (L + 4 >= (int)sizeof(monthJson)) {
      sendHttp(client, 500, "application/json", "{\"error\":\"month_overflow\"}");
      return;
    }
    snprintf(monthJson + L, sizeof(monthJson) - (size_t)L, "]}");
    sendHttp(client, 200, "application/json", monthJson);
    return;
  }

  if (strcmp(path, "/api/calendar/date") == 0 && strcmp(method, "GET") == 0) {
    int y = 0, m = 0, d = 0;
    if (!parseDateParam(query, &y, &m, &d)) {
      sendHttp(client, 400, "application/json",
                "{\"error\":\"use date=YYYY-MM-DD or y=&m=&d=\"}");
      return;
    }
    int bins[8];
    int n = collectBinsForYmd(y, m, d, bins, 8);
    char body[320];
    int L = snprintf(body, sizeof(body), "{\"year\":%d,\"month\":%d,\"day\":%d,\"bins\":[", y, m, d);
    for (int i = 0; i < n && L + 8 < (int)sizeof(body); i++) {
      if (i) {
        body[L++] = ',';
      }
      L += snprintf(body + L, sizeof(body) - L, "%d", bins[i]);
    }
    L += snprintf(body + L, sizeof(body) - L, "],\"initials\":\"");
    for (int i = 0; i < n && L + 4 < (int)sizeof(body); i++) {
      if (i) {
        body[L++] = '.';
      }
      body[L++] = binInitialFromIndex(bins[i]);
    }
    if (L + 8 < (int)sizeof(body)) {
      snprintf(body + L, sizeof(body) - L, "\"}");
    }
    sendHttp(client, 200, "application/json", body);
    return;
  }

  if (strcmp(path, "/api/calendar/tomorrow") == 0 && strcmp(method, "GET") == 0) {
    if (!st.ntpOk || st.epochUtc == 0) {
      sendHttp(client, 503, "application/json", "{\"error\":\"time_not_ready\"}");
      return;
    }
    time_t t = (time_t)st.epochUtc + 86400L;
    int y = year(t);
    int m = month(t);
    int d = day(t);
    int bins[8];
    int n = collectBinsForYmd(y, m, d, bins, 8);
    char body[320];
    int L = snprintf(body, sizeof(body), "{\"year\":%d,\"month\":%d,\"day\":%d,\"bins\":[", y, m, d);
    for (int i = 0; i < n && L + 8 < (int)sizeof(body); i++) {
      if (i) {
        body[L++] = ',';
      }
      L += snprintf(body + L, sizeof(body) - L, "%d", bins[i]);
    }
    L += snprintf(body + L, sizeof(body) - L, "],\"initials\":\"");
    for (int i = 0; i < n && L + 4 < (int)sizeof(body); i++) {
      if (i) {
        body[L++] = '.';
      }
      body[L++] = binInitialFromIndex(bins[i]);
    }
    if (L + 8 < (int)sizeof(body)) {
      snprintf(body + L, sizeof(body) - L, "\"}");
    }
    sendHttp(client, 200, "application/json", body);
    return;
  }

  if (strcmp(path, "/api/action/led") == 0 && (strcmp(method, "POST") == 0 || strcmp(method, "GET") == 0)) {
    int bin = parseIntParam(query, "bin", -1);
    int value = parseIntParam(query, "value", -1);
    if (bin < 0 || bin >= numBins || value < 0 || value > 255) {
      sendHttp(client, 400, "application/json", "{\"error\":\"bin_or_value_invalid\"}");
      return;
    }
    setUserLedBinOverride(bin, value);
    char body[160];
    formatLedStateJson(body, sizeof(body));
    sendHttp(client, 200, "application/json", body);
    return;
  }

  if (strcmp(path, "/api/action/leds/off") == 0 && (strcmp(method, "POST") == 0 || strcmp(method, "GET") == 0)) {
    turnOffAllLedsFromUser();
    char body[160];
    formatLedStateJson(body, sizeof(body));
    sendHttp(client, 200, "application/json", body);
    return;
  }

  if (strcmp(path, "/api/action/leds/reset") == 0 &&
      (strcmp(method, "POST") == 0 || strcmp(method, "GET") == 0)) {
    resetLedsToCalendarSchedule();
    char body[160];
    formatLedStateJson(body, sizeof(body));
    sendHttp(client, 200, "application/json", body);
    return;
  }

  if (strcmp(path, "/api/action/leds/toggle") == 0 &&
      (strcmp(method, "POST") == 0 || strcmp(method, "GET") == 0)) {
    toggleUserLedOverride();
    char body[160];
    formatLedStateJson(body, sizeof(body));
    sendHttp(client, 200, "application/json", body);
    return;
  }

  if (strcmp(path, "/api/action/leds/state") == 0 && strcmp(method, "GET") == 0) {
    char body[160];
    formatLedStateJson(body, sizeof(body));
    sendHttp(client, 200, "application/json", body);
    return;
  }

  if (strcmp(path, "/favicon.ico") == 0) {
    sendHttp(client, 204, "text/plain", "");
    return;
  }

  sendHttp(client, 404, "application/json", "{\"error\":\"not_found\"}");
}

inline void webApiBegin() {
  g_httpServer.begin();
}

inline void webApiPoll(const WebApiNetStatus& st) {
  WiFiClient client = g_httpServer.available();
  if (!client) {
    return;
  }
  unsigned long start = millis();
  while (!client.available() && client.connected() && millis() - start < 3000UL) {
    delay(1);
  }
  if (client.connected()) {
    handleHttpRequest(client, st);
  }
  client.stop();
}

#endif

#ifndef ESCILO_CALENDAR_H
#define ESCILO_CALENDAR_H

#include <stdint.h>

// Alias firmware: cambia zona (e anni attivi) prima del flash.
// I file in calendars/ contengono solo le entry; struct e helper stanno qui.
// Anno singolo per file; qui si fondono al massimo due anni per il passaggio di anno.

struct CalendarEntry {
  uint16_t year;   // Anno specifico
  uint8_t month;   // 1..12
  uint8_t day;     // 1..31
  int8_t binIndex; // -1 = nessun ritiro, 0..(numBins-1) = LED da accendere
};

const CalendarEntry datedCalendar[] = {
#include "calendars/candiolo-z2-2026.h"
#include "calendars/candiolo-z2-2027.h"
};

const int datedCalendarCount = sizeof(datedCalendar) / sizeof(datedCalendar[0]);

inline uint32_t calendarDateKey(int year, int month, int day) {
  return ((uint32_t)year * 10000UL) + ((uint32_t)month * 100UL) + (uint32_t)day;
}

inline int lowerBoundDated(uint32_t key) {
  int left = 0;
  int right = datedCalendarCount;
  while (left < right) {
    int mid = left + (right - left) / 2;
    const CalendarEntry &entry = datedCalendar[mid];
    uint32_t entryKey = calendarDateKey(entry.year, entry.month, entry.day);
    if (entryKey < key) {
      left = mid + 1;
    } else {
      right = mid;
    }
  }
  return left;
}

/** 0=dom … 6=sab (stesso schema di Sakamoto / TimeLib con offset). */
inline int calendarWeekdaySun0(int year, int month, int day) {
  static const int monthShift[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
  int y = year;
  if (month < 3) {
    y -= 1;
  }
  return (y + y / 4 - y / 100 + y / 400 + monthShift[month - 1] + day) % 7;
}

/** Primo lunedì di mesi dispari, gennaio escluso: strada senza cassonetti. */
inline bool isStradaVuotaDay(int year, int month, int day) {
  if (month == 1 || (month % 2) == 0) {
    return false;
  }
  if (day > 7) {
    return false;
  }
  return calendarWeekdaySun0(year, month, day) == 1;
}

inline int firstUnsortedCalendarIndex() {
  if (datedCalendarCount < 2) {
    return -1;
  }

  uint32_t previousKey = calendarDateKey(
    datedCalendar[0].year,
    datedCalendar[0].month,
    datedCalendar[0].day
  );

  for (int i = 1; i < datedCalendarCount; i++) {
    const CalendarEntry &entry = datedCalendar[i];
    uint32_t currentKey = calendarDateKey(entry.year, entry.month, entry.day);
    if (currentKey < previousKey) {
      return i;
    }
    previousKey = currentKey;
  }

  return -1;
}

#endif

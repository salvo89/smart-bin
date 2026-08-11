export const LS_COMUNE = "escilo.comune";
export const LS_COMUNE_NAME = "escilo.comuneName";
export const LS_VIA = "escilo.via";
export const LS_CALENDAR = "escilo.calendar";
export const LS_ACCESS_MODE = "escilo.accessMode";
export const LS_ISTAT = "escilo.istat";
export const LS_PUSH_HOUR = "escilo.pushHour";
export const LS_PUSH_HOUR_USER = "escilo.pushHourUserSet";
export const LS_PUSH_REGISTERED = "escilo.pushRegistered";

export const ACCESS_CALENDAR = "calendar";
export const ACCESS_STATS = "stats";

export const CONTACT_EMAIL = "salvatore.bonventre.ai@gmail.com";
export const CONTACT_MAILTO =
  "mailto:" + CONTACT_EMAIL + "?subject=" + encodeURIComponent("Escilo — calendario");

export function contactMailto(subject) {
  return (
    "mailto:" +
    CONTACT_EMAIL +
    "?subject=" +
    encodeURIComponent(subject || "Escilo — calendario")
  );
}

export const PUSH_API = {
  vapid: "/api/push/vapid-public",
  subscribe: "/api/push/subscribe",
  unsubscribe: "/api/push/unsubscribe",
};

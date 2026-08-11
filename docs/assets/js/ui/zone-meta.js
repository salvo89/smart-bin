import { refreshFooterSources, updateFooterSources } from "../data/zones.js";
import { $ } from "../shared/dom.js";
import { state } from "../state.js";

export function updateZoneMeta() {
  const meta = $("zoneMeta");
  const label = $("zoneLabel");
  if (!state.zoneChoice) {
    meta.hidden = true;
    updateFooterSources(null);
    return;
  }
  label.textContent = state.zoneChoice.comuneName + " · " + state.zoneChoice.via;
  meta.hidden = false;
  refreshFooterSources();
}

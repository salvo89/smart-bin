import { refreshFooterSources, updateFooterSources } from "../data/zones.js";
import { $ } from "../shared/dom.js";
import { state } from "../state.js";

function syncHeroShareBtn() {
  const btn = $("btnShareHero");
  if (btn) btn.hidden = !state.zoneChoice;
}

export function updateZoneMeta() {
  const meta = $("zoneMeta");
  const label = $("zoneLabel");
  if (!state.zoneChoice) {
    meta.hidden = true;
    syncHeroShareBtn();
    updateFooterSources(null);
    return;
  }
  label.textContent = state.zoneChoice.comuneName + " · " + state.zoneChoice.via;
  meta.hidden = false;
  syncHeroShareBtn();
  refreshFooterSources();
}

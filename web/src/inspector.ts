/**
 * The record for the selected instrument, editable.
 *
 * Fields that change the light — type, trim, focus, color, lamp, mode — trigger
 * a recompute. Fields that are only paperwork — purpose, notes — do not, because
 * a round trip per keystroke while typing a purpose is noise.
 */
import { isVertical, type Instrument } from "./plot.js";
import { confirmDelete, describeUnit } from "./confirm.js";
import { parseFeet } from "./feet.js";
import { fmtFt, fmtFc } from "./geometry.js";
import type { Store } from "./store.js";
import type { Computed } from "./render.js";
import type { DmxTable } from "./api.js";

export interface Field {
  key: keyof Instrument;
  label: string;
  kind: "number" | "text" | "select" | "list" | "combo";
  /** Does changing it change the light? */
  photometric?: boolean;
  /** 🔴 Does the SERVER have to work the row out again? Photometric fields do.
   *  So do the patch fields — the address RANGE is computed in Python, so
   *  changing a personality from HSI to Direct without this repainted the old
   *  range and looked like the dropdown did nothing. A field whose value the
   *  server turns into text belongs here. */
  recompute?: boolean;
  options?: string[];
  step?: number;
  hint?: string;
  /** A LENGTH. Shown as feet and inches, and typed the same way — see feet.ts.
   *  The rest of the numbers (unit, channel, dimmer, address, lens angle) are
   *  counts and degrees, and stay plain. */
  kind2?: "feet";
}

export const FIELDS: Field[] = [
  { key: "unit", label: "Unit", kind: "number", step: 1 },
  { key: "channel", label: "Channel", kind: "number", step: 1 },
  { key: "circuit", label: "Circuit", kind: "text",
    hint: "The HOUSE circuit. Never generated — circuits depend on the house and have no set order" },
  { key: "dimmer", label: "Dimmer", kind: "number", step: 1, recompute: true },
  // 🔴 TEXT, not number. A universe address is "2/21" and type="number"
  // silently discards it — exactly as it discards 1'6" in a feet field, which
  // this file already warns about below. The field went empty and the handler
  // read that as "clear this field", so a perfectly good address unset itself.
  { key: "address", label: "Address", kind: "text", recompute: true,
    hint: "45, or 2/21 for a universe. The START address" },
  // ⭐ The specific fixture, and the personality it is set to (Jerry,
  // 2026.09.26). Type above is the photometric key, which a Series 1 and a
  // Series 2 share; these two decide how many addresses the unit occupies.
  { key: "model", label: "Model", kind: "select", recompute: true,
    hint: "The specific fixture. Personalities differ between models, so the "
        + "address range depends on this" },
  { key: "profile", label: "DMX personality", kind: "select", recompute: true,
    hint: "What the fixture is set to at its own display. The same instrument "
        + "can be on a different personality from the one beside it" },
  { key: "type", label: "Type", kind: "select", photometric: true },
  { key: "position", label: "Position", kind: "select" },
  { key: "purpose", label: "Purpose", kind: "text" },
  { kind2: "feet", key: "x", label: "X (ft)", kind: "number", step: 0.0833, photometric: true },
  { kind2: "feet", key: "y", label: "Y (ft)", kind: "number", step: 0.0833, photometric: true },
  { kind2: "feet", key: "trim", label: "Trim (ft)", kind: "number", step: 0.5, photometric: true,
    hint: "Hang height above the deck. On a BOOM this is the height on the "
        + "boom, and it is written to both fields — the elevation reads one, "
        + "the photometrics read the other." },
  { kind2: "feet", key: "focusX", label: "Focus X", kind: "number", step: 0.5, photometric: true },
  { kind2: "feet", key: "focusY", label: "Focus Y", kind: "number", step: 0.5, photometric: true },
  { kind2: "feet", key: "focusH", label: "Focus height", kind: "number", step: 0.5, photometric: true,
    hint: "Head height, 5'-6\" unless the light lands somewhere else" },
  // ⭐ A COMBO, NOT A SELECT. The value is often a COMBINATION — "R52+R119" is
  // stacked and "R52/R119" is a split frame — and neither is an entry in any
  // list. A fixed dropdown would make Jerry's own most-used colour, on 105
  // units of the archive, impossible to choose. So: suggestions you can ignore.
  { key: "color", label: "Color", kind: "combo", photometric: true,
    hint: "R52+R119 stacks · R52/R119 is a split frame" },
  { key: "gobo", label: "Gobo", kind: "text" },
  { key: "lamp", label: "Lamp", kind: "select", photometric: true },
  { key: "mode", label: "LED mode", kind: "select", photometric: true,
    hint: "The PHOTOMETRIC output mode — how bright. Not the DMX personality" },
  { key: "lensRotation", label: "Lens angle", kind: "number", step: 15,
    hint: "Oval-beam units (PARNel): degrees the lens is turned" },
  { key: "accessories", label: "Accessories", kind: "list",
    hint: "Separate with + — \"top hat + gobo\". Barn doors, hats, gobo, iris, rotator" },
  { key: "notes", label: "Notes", kind: "text" },
];

/** The specific models this unit's fixture type could be. */
function modelsFor(inst: Instrument, deps: InspectorDeps): string[] {
  const fam = deps.familyOf?.(inst.type);
  return (fam && deps.dmx?.family_models[fam]) || [];
}

/** The personalities this unit can be set to.
 *
 *  ⚠ A personality whose channel count nobody published is still OFFERED — the
 *  fixture has it, and a designer who is on RGB Plus 7 must be able to record
 *  that. It is marked so, and the range is simply not drawn for it. Leaving it
 *  out of the list would make the plot unable to describe a real rig. */
function profilesFor(inst: Instrument, deps: InspectorDeps): string[] {
  const model = inst.model || modelsFor(inst, deps)[0];
  if (!model || !deps.dmx) return [];
  // ⚠ PLAIN NAMES. The select builder uses each string as BOTH the option value
  // and its label, so decorating a name here would store the decoration — and
  // "RGB Plus 7 (channels not published)" matches nothing in the table. The
  // cell's hover already says when a count is unpublished.
  return [...(deps.dmx.profiles[model] ?? []),
          ...(deps.dmx.unpublished[model] ?? [])].sort();
}

/** Is this unit hung on a boom, box boom, ladder or tormentor? */
function onVerticalPosition(store: Store, inst: Instrument): boolean {
  const name = (inst.position ?? "").trim().toLowerCase();
  if (!name) return false;
  const pos = store.plot.positions.find(p => p.name.trim().toLowerCase() === name);
  return pos ? isVertical(pos) : false;
}

export interface InspectorDeps {
  fixtures: string[];
  /** Gel numbers with their names, for the colour suggestions. Undefined until
   *  `/gels` has answered, in which case the field is a plain text box — which
   *  is what it was before, so nothing is lost by the wait. */
  gels?: { gel: string; name: string }[];
  /** The DMX table, once it has arrived. Undefined until then — the two
   *  personality dropdowns simply offer nothing rather than guessing. */
  dmx?: DmxTable;
  /** The photometric family of a fixture type, for choosing which models to
   *  offer. Undefined for a type the server does not know. */
  familyOf?: (type: string) => string | undefined;
  /** Say why an entry was refused. Optional so other callers still compile. */
  onStatus?: (msg: string, bad?: boolean) => void;
  lamps: string[];
  modes: string[];
  onPhotometricChange: () => void;
  onPaperworkChange: () => void;
}

export function renderInspector(
  host: HTMLElement, store: Store, computed: Computed[], deps: InspectorDeps,
): void {
  host.replaceChildren();
  const i = store.selected;
  const inst = store.selectedInstrument;
  if (i === null || !inst) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Click an instrument to edit it. Drag the body to move it, the ring to re-aim it. Alt-drag to place it off a pipe.";
    host.appendChild(p);
    return;
  }

  const c = computed[i];
  if (c) {
    const box = document.createElement("div");
    box.className = "computed";
    if (c.computed) {
      box.innerHTML =
        `<b>${c.throw_ft}</b> throw · <b>${c.elevation?.toFixed(0)}°</b> · ` +
        `pool <b>${c.field_ft ?? "—"}</b><br>` +
        // 🔴 Not `${c.footcandles} fc`. The throws and pools beside it already
        // read in metres on a metric plot, and a level hardcoded to "fc" put a
        // number and a contradicting unit on the same line — the exact failure
        // the metric work existed to prevent. The PDF had it right and the
        // screen did not, which is the harder way round to notice.
        (c.footcandles != null ? `<b>${fmtFc(c.footcandles)}</b> ` : "") +
        `<span class="muted">${escape(c.footcandles_note ?? "")}</span>`;
    } else {
      box.innerHTML = `<span class="warn">Not computed — ${escape(c.note ?? "")}</span>`;
    }
    if (c.gel_warning) {
      box.innerHTML += `<br><span class="warn">${escape(c.gel_warning)}</span>`;
    }
    host.appendChild(box);
  }

  const grid = document.createElement("div");
  grid.className = "fields";
  for (const f of FIELDS) {
    const id = `f-${String(f.key)}`;
    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = f.label;
    if (f.hint) label.title = f.hint;
    // ⭐ Jerry, 2026.09.26: "if we say 2/1 it should expand to 2/1-X". It
    // expands HERE, beside the label, and NOT in the box.
    //
    // ⚠ The input keeps the START address. Putting "2/1-2/15" in the box would
    // make the next edit store that string as the address, and nothing matches
    // it — the unit would quietly stop being patched. A range is something the
    // program worked out; the address is what the designer typed, and the two
    // must not share an editable field.
    if (f.key === "address" && c?.patch && c.patch !== String(inst.address ?? "")
        && c.patch.includes("-")) {
      const span = document.createElement("span");
      span.className = "muted";
      span.textContent = ` ${c.patch}`;
      span.title = c.patch_note ?? "";
      label.appendChild(span);
    }

    let input: HTMLInputElement | HTMLSelectElement;
    if (f.kind === "select") {
      input = document.createElement("select");
      const opts = f.key === "type" ? deps.fixtures
        : f.key === "lamp" ? deps.lamps
        : f.key === "mode" ? deps.modes
        : f.key === "model" ? modelsFor(inst, deps)
        : f.key === "profile" ? profilesFor(inst, deps)
        : store.plot.positions.map(p => p.name);
      const blank = document.createElement("option");
      blank.value = ""; blank.textContent = "—";
      input.appendChild(blank);
      for (const o of opts) {
        const el = document.createElement("option");
        el.value = o; el.textContent = o;
        input.appendChild(el);
      }
      input.value = String(inst[f.key] ?? "");
    } else if (f.kind === "combo") {
      // A text box with a datalist: 498 suggestions, and anything typed is
      // still accepted. ⚠ The browser stops matching once you type "R52+",
      // because no single entry starts with that — normal combobox behaviour,
      // and the reason this must never become a <select>.
      input = document.createElement("input");
      input.type = "text";
      input.value = String(inst[f.key] ?? "");
      const listId = `datalist-${f.key}`;
      input.setAttribute("list", listId);
      let dl = document.getElementById(listId) as HTMLDataListElement | null;
      if (!dl) {
        dl = document.createElement("datalist");
        dl.id = listId;
        document.body.appendChild(dl);
      }
      // ⭐ THE NAME FINALLY EARNS ITS PLACE. gels.csv has carried a name column
      // all along and nothing read it. Here the VALUE stays the bare number —
      // what the table is keyed on — and the name rides along as the label, so
      // the dropdown reads "R52  Light Lavender" instead of a wall of numbers.
      // Whether typing "lav" FILTERS on the name is the browser's business, not
      // ours: Chrome matches the label, others match the value only. Either way
      // the number is what gets stored.
      if (f.key === "color" && deps.gels && dl.childElementCount !== deps.gels.length) {
        dl.replaceChildren();
        for (const g of deps.gels) {
          const o = document.createElement("option");
          o.value = g.gel;
          o.label = g.name;
          dl.appendChild(o);
        }
      }
    } else {
      input = document.createElement("input");
      // ⚠ A length is a TEXT box. type="number" silently discards 1'6" — the
      // field goes empty and the handler reads that as "clear this field", so
      // typing a perfectly good height unset it. inputmode keeps a phone
      // keyboard sensible without bringing the strictness back.
      input.type = f.kind === "number" && !f.kind2 ? "number" : "text";
      if (f.kind2 === "feet") input.inputMode = "decimal";
      if (f.step && input.type === "number") input.step = String(f.step);
      const cur = inst[f.key];
      input.value = f.kind === "list"
        // " + " matches the schedule export and the gel notation, where + means
        // "and this as well". A comma would be ambiguous inside a CSV cell.
        ? (Array.isArray(cur) ? cur.join(" + ") : "")
        : f.kind2 === "feet" && typeof cur === "number" ? fmtFt(cur)
        : cur === undefined || cur === null ? "" : String(cur);
    }
    input.id = id;
    if (f.hint) input.title = f.hint;

    const apply = () => {
      const raw = input.value.trim();
      let value: string | number | undefined;
      if (raw === "") value = undefined;
      else if (f.kind === "list") {
        const parts = raw.split(/\s*[+,]\s*/).map(t => t.trim()).filter(Boolean);
        store.begin(null);
        store.update(i, { [f.key]: parts.length ? parts : undefined } as Partial<Instrument>);
        (f.photometric || f.recompute) ? deps.onPhotometricChange() : deps.onPaperworkChange();
        return;
      }
      else if (f.kind2 === "feet") {
        const n = parseFeet(raw);
        if (n === null) {
          // ⚠ Refuse LOUDLY and put back what was there. Silently keeping the
          // old value is how "1'6" doesn't work" happens; silently clearing it
          // is worse.
          deps.onStatus?.(`"${raw}" is not a length — try 1'6", 18" or 1.5`, true);
          input.value = typeof inst[f.key] === "number" ? fmtFt(inst[f.key] as number) : "";
          return;
        }
        value = n;
      }
      else if (f.kind === "number") {
        const n = Number(raw);
        if (!isFinite(n)) return;
        value = n;
      } else value = raw;
      store.begin(null);
      // 🔴 On a VERTICAL position the trim and the height are the same fact, and
      // they were two fields with only one of them reachable: the inspector had
      // no Height box at all, so a boom unit's height could be set by hand
      // editing the .plot.json and nowhere else. Typing a trim now writes both,
      // rather than leaving a unit whose elevation says one thing and whose
      // throw is computed from another.
      const patch: Record<string, unknown> = { [f.key]: value };
      if (f.key === "trim" && onVerticalPosition(store, inst)) patch.height = value;
      store.update(i, patch as Partial<Instrument>);
      (f.photometric || f.recompute) ? deps.onPhotometricChange() : deps.onPaperworkChange();
    };
    // change, not input — committing on blur or Enter, so half-typed values
    // never reach the server
    input.addEventListener("change", apply);

    grid.appendChild(label);
    grid.appendChild(input);
  }
  host.appendChild(grid);

  const del = document.createElement("button");
  del.className = "danger";
  del.textContent = "Delete instrument";
  del.addEventListener("click", () => {
    if (!confirmDelete(describeUnit(inst))) return;
    store.remove(i);
    deps.onPhotometricChange();
  });
  host.appendChild(del);
}

function escape(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

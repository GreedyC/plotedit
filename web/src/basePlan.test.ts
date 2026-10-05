/** Run: cd web && npm run test:base
 *
 * The two bugs a beta tester reported on 2026.10.05, both about the imported
 * ground plan, and both of a kind that a type checker cannot see.
 *
 * 🔴 ONE. IT WAS DRAWN TOO FAINT TO FIND. #c9c9c9 on the white the drawing sits
 * on measures 1.66:1, where the floor for a line on a page is 3:1. He imported
 * a DXF, saw nothing, and got to his own drawing by switching Chrome to forced
 * dark — he did not find a setting, he found a workaround. So this MEASURES the
 * colour rather than matching the string, and it reads the background out of
 * index.html, because the ratio depends on both and either one can drift.
 *
 * 🔴 TWO. IT FOLLOWED HIM INTO THE NEXT PLOT. The import is not in the file —
 * `basePlan`, `baseImage` and `baseXf` are module state — so opening a
 * different show left the previous venue underneath it. Every Open, New and
 * sample load goes through `adoptPlot()`, which is why the reset belongs there
 * and nowhere else. Checked by reading the source, which is a weak test of a
 * strong invariant: the fix is one forgotten line away at all times, and that
 * line going missing is exactly what the bug was.
 */
import * as fs from "node:fs";

let fails = 0;
function check(label: string, got: unknown, want: unknown) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label.padEnd(52)} ${JSON.stringify(got)}`);
  if (!ok) { fails++; console.log(`       wanted ${JSON.stringify(want)}`); }
}

const src = (f: string) => fs.readFileSync(new URL(f, import.meta.url), "utf8");
const render = src("./render.ts");
const main = src("./main.ts");
const html = src("../index.html");

// ---- WCAG 2.1 relative luminance and contrast, straight off the spec.
function luminance(hex: string): number {
  let h = hex.replace("#", "");
  if (h.length === 3) h = [...h].map(c => c + c).join("");
  const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}
function contrast(a: string, b: string): number {
  const la = luminance(a), lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}
const round2 = (n: number) => Math.round(n * 100) / 100;

console.log("the measuring tool agrees with the spec's own examples");
// If these drift the rest of the file is worthless, so they go first.
check("black on white is 21:1", round2(contrast("#000", "#fff")), 21);
check("white on white is 1:1", round2(contrast("#fff", "#fff")), 1);
check("#767676 on white is the 4.5:1 borderline",
      round2(contrast("#767676", "#fff")), 4.54);

console.log("\n🔴 the base plan is dark enough to see");
// Read, not assumed: the drawing is on the svg, and the svg sets its own
// background. Measuring against the page surface would flatter the number.
function capture(label: string, re: RegExp, text: string): string {
  const m = re.exec(text);
  const got = m?.[1];
  check(label, got !== undefined, true);
  if (got === undefined) { console.log("\nnothing left to measure"); process.exit(1); }
  return got;
}

const paper = capture("index.html still gives the svg a background",
                      /svg\s*\{[^}]*background:\s*(#[0-9a-f]{3,6})/i, html);
check("...and it is white", paper.toLowerCase(), "#fff");

const ink = capture("render.ts strokes the base plan with a flat hex",
                    /gBase\.appendChild\([\s\S]*?stroke:\s*"(#[0-9a-f]{3,6})"/i, render);
const ratio = contrast(ink, paper);
console.log(`       ${ink} on ${paper} measures ${round2(ratio)}:1`);
// 3:1 is the WCAG 1.4.11 floor for a graphic that carries meaning. A plan you
// cannot see carries all of it.
check("it clears the 3:1 floor for non-text graphics", ratio >= 3, true);
check("...and #c9c9c9, which did not, is gone", ink.toLowerCase() === "#c9c9c9", false);

// ⚠ The other half of the bug report is the reason this is not simply black.
// The venue's drawing is their claim, not Jerry's measurement, and it has to
// stay underneath the rig rather than compete with it.
const pipe = /stroke:\s*"(#2{3}|#222222)"/i.exec(render)?.[1];
check("the rig is still drawn darker than the plan under it",
      pipe === undefined || luminance(ink) > luminance(pipe), true);
check("...and the plan is still the lighter of the two by a clear margin",
      pipe === undefined || contrast(ink, pipe) >= 2, true);

console.log("\n🔴 opening a plot forgets the imported plan");
// The three pieces of module state. All three, because resetting two of them
// is the same bug with a smaller footprint.
const body = capture("clearBase() exists",
                     /function clearBase\(\): void \{([\s\S]*?)\n\}/, main);
check("it drops the raster image", /baseImage = undefined/.test(body), true);
check("it drops the vector plan", /basePlan = null/.test(body), true);
check("it resets the transform", /baseXf = \{/.test(body), true);
// ⚠ Without this, a session of trying plans holds every one of them until the
// tab closes. It was right in the off button before this existed; the point of
// a single function is that the open path cannot forget it.
check("it revokes the object URL", /revokeObjectURL/.test(body), true);

// Brace-match the one function every Open, New and sample load comes through.
const at = main.indexOf("async function adoptPlot(");
check("adoptPlot() exists", at >= 0, true);
let depth = 0, end = at;
for (let i = main.indexOf("{", at); i < main.length; i++) {
  if (main[i] === "{") depth++;
  else if (main[i] === "}" && --depth === 0) { end = i; break; }
}
const adopt = main.slice(at, end);
check("...and it clears the base", /\bclearBase\(\)/.test(adopt), true);
// ⚠ paint() calls syncLayers, draw, fillTable and drawInspector — not this. So
// clearing the state without it leaves the bar offering to move and remove a
// plan that is already gone.
check("...and refreshes the bar, which paint() does not",
      /\bsyncBackdropBar\(\)/.test(adopt), true);

// 🔴 And it has to happen BEFORE the new plot is in place, or the first draw of
// the new show is the one that still has the old venue under it.
check("it clears before the store is replaced",
      adopt.indexOf("clearBase()") < adopt.indexOf("new Store("), true);

console.log();
if (fails) { console.log(`${fails} FAILED`); process.exit(1); }
console.log("all passed");

#!/usr/bin/env python3
"""Render the legend / instrument key on its own sheet — RP-2 §5.

    cd server && python3 plot_to_key.py testdata/bluver.plot.json ../out/key.pdf

§5.0 allows the key anywhere "that does not conflict with other information".
A sheet of its own always satisfies that, and it is what to hand an electrician
who is reading somebody else's plot. `key.draw()` is the same function, so the
key can be dropped onto the plot instead once there is room for it.
"""
import json
import sys

from plotedit.scaled_pdf import Sheet, ft
from plotedit import key as K


def render(plot_path, pdf_path, scale="1/2", page="ARCH_C", landscape=False):
    plot = json.load(open(plot_path))
    s = Sheet(pdf_path, page=page, scale=scale, landscape=landscape,
              show=plot["show"], venue=plot.get("venue", ""),
              sheet="Instrument Key", rev=str(plot.get("revision", "0"))[:3],
              designer=f"Design: {plot.get('designer', '')}")
    s.origin(ft(2), ft(2))
    top = 30.0
    K.draw(s, plot, 1.0, top)
    s.finish()
    return s


if __name__ == "__main__":
    a = sys.argv[1:]
    s = render(a[0] if a else "testdata/bluver.plot.json",
               a[1] if len(a) > 1 else "../out/key.pdf")
    for w in s.warnings:
        print("⚠", w)
    print("wrote the key")

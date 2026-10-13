# Sample files

**Everything in this folder is served by the app and ships inside the download.**
Vite uses it as its public dir (`web/vite.config.ts`), and the release copies it
whole. So a file belongs here only if a stranger who unzips plotedit should see
it.

`demo.plot.json` is that file: the plot the app opens when there is nothing else
to open.

`Sample Big House.plot.json` is the other end of the scale: a large proscenium
house, 201 units on electrics, pro slots, ceiling catwalks and a balcony rail
(Jerry, 2026.10.09). It was built from a real house's repertory plot with the
name taken off — "Big House" is invented — and `test_api.py` checks the real
name stays off. Every unit is focused straight down as a stand-in, **at head
height**. At 1/4" it needs ARCH E; on ARCH D it prints at 1/8".

🔴 **It shipped for four days focused at the DECK**, not at head height —
`focusH: 0` on all 201 units, which is not the same as blank. Blank means head
height (`focusH ?? 5.5`); zero is a number, so it travels, and every pool and
every footcandle computed at the floor: a 30-foot throw off the electrics where
the truth is 24'-6". It looked entirely finished. It also carried three
duplicate unit numbers. Both fixed 2026.10.13 (#125), and
`python3 -m plotedit.qc` now runs over both files in CI so it cannot come back.

⚠ **Test fixtures do NOT belong here.** They live in `server/testdata/`, which is
not served. The renderer's fixture sat here until 2026.09.28 and went out in
every download — and it described a real room, which is a second reason it does
not belong in front of a stranger. It is now `server/testdata/blackbox.plot.json`
and the room it describes is invented.

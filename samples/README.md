# Sample files

**Everything in this folder is served by the app and ships inside the download.**
Vite uses it as its public dir (`web/vite.config.ts`), and the release copies it
whole. So a file belongs here only if a stranger who unzips plotedit should see
it.

`demo.plot.json` is that file: the plot the app opens when there is nothing else
to open.

⚠ **Test fixtures do NOT belong here.** They live in `server/testdata/`, which is
not served. `bluver.plot.json` sat here until 2026.09.28 and went out in every
download, naming a real venue and a show that had not been designed yet.

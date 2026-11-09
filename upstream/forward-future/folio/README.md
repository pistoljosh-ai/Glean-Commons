# Upstream: Forward-Future/folio (PDF reader)

Pointer and license record. No Folio source, installer, or dependency is stored in Glean Commons.

**Folio** is the open-source PDF reader and editor at [Forward-Future/folio](https://github.com/Forward-Future/folio). It reads, highlights, annotates, and signs PDFs on Windows, macOS, and Linux, and can optionally ask an outside AI model about a document. Matthew Berman announced this repository on 30 Oct 2026. It is the Folio in the Forward Future GitHub organization, the same organization as [loopy](https://github.com/Forward-Future/loopy). It is not a copy of another product that happens to use the name Folio.

This folder follows [INTAKE.md](../../../INTAKE.md): a first import is a pointer. A local adaptation is the child cell [`folio-document-desk`](../../../cells/folio-document-desk/), which does not vendor Folio either.

## What was verified on 2026-11-09

| Fact | Source |
|------|--------|
| Repository | https://github.com/Forward-Future/folio (GitHub API: not a fork, default branch `main`) |
| Sibling downloads repo | https://github.com/Forward-Future/folio-releases (binaries and updates only; nothing from it is stored here) |
| No other `folio` repo under user `mberman84` | GitHub user repos API, 2026-11-09 |
| Pinned revision | `0590fac31d915810c881ca6144fc7e8bb32e82c0` |
| Pin date | 2026-11-07T20:16:56Z |
| Pin subject | Protect ChatGPT sign-in and isolate Claude Code processes (#76) |
| Committer on the pin | GitHub user `mberman84` |
| Tag `v1.16.1` | `c98788049dabd8dfb24a3c271ad551c26be5e895` (2026-11-07T03:45:52Z). The pin is 5 commits after that tag and 0 behind it. `package.json` at the pin still says `1.16.1`. |
| SPDX | MIT |
| Copyright line | `Copyright (c) 2026 mberman84` |
| `package.json` author | `Forward Future` |
| `package.json` license | `MIT` |
| Stars observed | 402 on 2026-11-09. This is a GitHub counter, not Proof of Use. Ledger `uses` stays 0. |

The pin does not move when upstream `main` moves. Machine-readable copy: [`PIN.json`](PIN.json).

## Attribution

- **Copyright holder on the license file:** `mberman84`.
- **Package author field:** Forward Future.
- **Primary committer:** GitHub user [mberman84](https://github.com/mberman84). Other people have commits on the repository; see the contributors graph. `dependabot` also has commits.
- **Matthew Berman:** the YouTube channel [youtube.com/user/mberman84](https://www.youtube.com/user/mberman84) is Matthew Berman, and his public video descriptions link `gist.github.com/mberman84` and Forward Future. On 30 Oct 2026 the account @MatthewBerman posted “Introducing Folio” and linked `https://github.com/Forward-Future/folio`. Later posts from the same account linked the same repository for Folio updates, including v1.16.0.
- The GitHub profile `mberman84` did not publish a display name, blog, or Twitter field on 2026-11-09. This record does not treat that profile page as a legal-name field. The license copyright line is the name to keep with any future copy: `mberman84`.

## License

MIT. The file [`UPSTREAM-LICENSE`](UPSTREAM-LICENSE) is a byte-for-byte copy of upstream `LICENSE` at the pin (SHA-256 `b9aa7207030821abe7108283c617565010cad4d1edee7ea881a0d07bd6d7a876`).

That MIT text governs Folio. It does not relicense Folio as Apache-2.0, and it does not relicense Glean Commons code as MIT. Glean Commons code is Apache-2.0 ([LICENSE](../../../LICENSE)). Docs stay CC BY-SA 4.0 ([LICENSE-docs](../../../LICENSE-docs)). Folio’s MIT grant is the upstream authors’ grant. Apache-2.0’s patent grant covers Glean Commons code only.

Folio bundles other programs under their own licenses (pdf.js is Apache-2.0, PDFium and font components include BSD and a Liberation font under GPLv2 with a font exception, Electron and React are MIT, and others). The list is upstream [`THIRD_PARTY_NOTICES.md`](https://github.com/Forward-Future/folio/blob/0590fac31d915810c881ca6144fc7e8bb32e82c0/THIRD_PARTY_NOTICES.md). None of those components are copied here. A later vendor of Folio must keep the MIT notice and those third-party notices with the copy.

## What is in this folder

| File | Role |
|------|------|
| `README.md` | This pointer. Commons documentation. |
| `PIN.json` | Pinned revision and license facts. Commons data, not Folio source. |
| `UPSTREAM-LICENSE` | Verbatim upstream MIT license. |

No TypeScript, Electron, pdf.js, sample document, screenshot, or installer from Folio is in this repository.

## What is not integrated

- Folio is not a Python dependency and not a Node dependency of this repo.
- The Glean tool server does not load Folio. The child cell exposes only Commons code that reads a local PDF header and git metadata.
- Nothing here renders, edits, signs, OCRs, or converts a PDF.
- Ask AI (ChatGPT sign-in, Claude Code, or an OpenRouter key) is Folio’s own feature. This pointer does not enable it. Upstream’s security note says document text goes to the chosen provider only when a person asks a question inside Folio.
- Upstream builds were not signed with paid developer certificates at the time of this pin. Upstream [SECURITY.md](https://github.com/Forward-Future/folio/blob/0590fac31d915810c881ca6144fc7e8bb32e82c0/SECURITY.md) says Windows builds are unsigned and macOS builds are ad-hoc signed. This import does not audit Folio.

## How to use Folio itself

Folio stays outside this repo. Prefer the pinned revision over a floating branch.

```sh
git clone https://github.com/Forward-Future/folio.git
cd folio
git checkout 0590fac31d915810c881ca6144fc7e8bb32e82c0
```

Upstream’s README says building needs Node.js 22 or newer, then `npm install` and `npm run app`. Those commands run upstream code. This Commons import did not run them. Read upstream `SECURITY.md` and `THIRD_PARTY_NOTICES.md` at the pin before you build or install.

Installers published from [Forward-Future/folio-releases](https://github.com/Forward-Future/folio-releases) are also external. They are not vendored here. An installer may be newer or older than the pin; compare a source checkout with the child cell before you treat it as this pin.

After a local clone exists, the child cell can compare its git HEAD to the pin. It does not clone, download, or start Folio:

```sh
python3 cells/folio-document-desk/desk.py compare-checkout /path/to/your/folio
python3 cells/folio-document-desk/desk.py slip /path/to/a-file.pdf
```

The bundled file under `cells/folio-document-desk/examples/` is a synthetic fixture, not a customer document and not Folio’s sample PDF.

## Ancestry

- Ledger id: `upstream-forward-future-folio`
- Child cell: `folio-document-desk` (parent is this pointer)
- Registry fragment: `registry/pending/upstream-forward-future-folio.json` until the fold on `main`
- Import steps: [INTAKE.md](../../../INTAKE.md)

Do not mark this pointer canonical. A human decides any later promotion.

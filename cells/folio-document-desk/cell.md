# Cell: Folio document desk

## Purpose

Identifies a PDF already on this machine (header plus SHA-256) and compares a local git clone of Folio to the pinned upstream revision. A person then opens the file in Folio. This cell does not install, launch, parse, or vendor Folio.

## Who it helps

Someone reviewing a document before they highlight, annotate, or sign it in Folio. The small-business books stay CSV. This desk does not turn a PDF into an invoice row and does not draft a reminder.

## How to use

Folio is external. Install or build it yourself from the pin in [`upstream/forward-future/folio/README.md`](../../upstream/forward-future/folio/README.md). This cell will not do that for you.

```bash
python3 cells/folio-document-desk/desk.py provenance
python3 cells/folio-document-desk/desk.py slip cells/folio-document-desk/examples/SYNTHETIC-not-a-real-invoice.pdf
python3 cells/folio-document-desk/desk.py compare-checkout /path/to/your/folio-clone
python3 cells/folio-document-desk/test_desk.py
```

`slip` accepts a regular file that starts with `%PDF-`, up to 300 MiB. It refuses symlinks and anything else, and it prints a hash so you can see which bytes you are about to open. `compare-checkout` reads `.git` metadata only.

The file in `examples/` is synthetic. It is not a customer invoice and not Folio’s sample PDF. Do not point the desk at client financial files, keys, or bank exports and then commit the output.

## What is integrated

- The upstream pointer: URL, MIT license text, copyright line, and pinned revision `0590fac31d915810c881ca6144fc7e8bb32e82c0`.
- This stdlib desk, including the local tool `folio_pdf_desk`.

The local tool server discovers `tools.json` the same way it discovers every other cell. The tool is Commons code. It is not marked `stateless`, so the public endpoint does not expose it. Calling it locally can still create an empty books folder, because that is how the server treats every non-stateless tool. The desk never reads those books.

## What is not integrated

- Folio source, Electron, pdf.js, installers, and Folio’s third-party components.
- Rendering, editing, signing, OCR, Word conversion, and printing.
- Folio’s Ask AI (ChatGPT, Claude Code, or OpenRouter). Document text is not sent anywhere by this cell.
- A dependency install. Nothing in this repo runs `npm` or downloads Folio.
- A security audit or a signature check of upstream binaries. Upstream builds at this pin are not signed with paid developer certificates. Read upstream `SECURITY.md` before you install.

## Link

- Upstream: https://github.com/Forward-Future/folio
- Pinned revision: `0590fac31d915810c881ca6144fc7e8bb32e82c0`
- Source path in this repo: `cells/folio-document-desk/`
- Grok Bot template URL (when published): not published

## Parents (contribution chain)

- Ledger parent id: `upstream-forward-future-folio`
- Inherited: the verified pointer, MIT notice, and pin. No Folio code.
- Started from the cell template (`cells/_template/`, registered under `glean-commons-repo`). On 2026-11-09 `python3 router/route.py` returned BUILD for a Folio PDF-reader request. Loopy is a different Forward Future project and is not a parent of this cell.

## AI assistance

- Grok 4.7 (Cursor cloud agent): license check, pin, desk, and tests. No upstream code copied.

## PoU metrics to track

| Signal | How we will measure it |
|--------|------------------------|
| Reach (R) | Unique people other than the creator who ran the desk, per two weeks |
| Depth (D) | Median runs per active person |
| Benefit (B) | Minutes saved identifying a document and confirming the Folio revision before review |
| Durability (L) | Share still used after 4 weeks |
| AI uplift (A) | Change in B after an AI revision |

No usage recorded yet (`uses: 0`). GitHub stars on Folio are not Proof of Use.

## Variants / experiments

- Canonical version: 0.1.0 draft. This does not promote Folio, and it does not change any other cell’s canonical version.
- Active variants: none
- Experiments: none

## Notes

- Keep Folio external until a human asks to vendor it. A vendor must keep `UPSTREAM-LICENSE` and upstream `THIRD_PARTY_NOTICES.md` with the copy. Do not relicense that code as Apache-2.0.
- The desk is a reference workflow. Folio is not an installed dependency.

# Cell: Folio edit-mode erase

## Purpose

Makes Backspace and Delete in Folio's Edit mode behave like typing: one character at a time, with a real way to remove a line of baked-in PDF text. This is a downstream patch for a pinned Folio revision. Folio is not vendored here, and this is not an installed app.

## What Edit mode already did at the pin

Checked out https://github.com/Forward-Future/folio at `0590fac31d915810c881ca6144fc7e8bb32e82c0` (also the tip of `main` on 2026-11-09). License: MIT. Copyright line: `Copyright (c) 2026 mberman84`. `package.json` author: Forward Future. Timmy's installed build was not available, so this is that source tree, not his binary.

Edit mode (`src/ContentEditor.tsx` plus `src/contentEditor.worker.ts`) is for text and images already inside the page, not for every kind of mark:

| Kind of text | What the pin does |
| --- | --- |
| Text baked into the page | Click the line. An input opens. Enter, or a click outside, asks PDFium to replace that text run. An empty string removes those text objects (`replaceText` in the worker). Escape cancels. |
| Text you type with the Text tool | A pdf.js text box. Backspace works in that box. It is not Edit mode. |
| Fillable form fields | A form widget. Edit mode does not list it as a line. Backspace works in the widget. |
| Highlights | Delete or Backspace removes the highlight only while its menu is open. |
| Signatures | A separate Sign tool. This patch does not change it. |
| Scanned or outlined letters | Not editable as text. The upstream README already says so. |

The worker removal is real. It calls `FPDFPage_RemoveObject`. It does not paint a white box over the words. The blue editor draws a paper-colored patch only while you are typing, so the old glyphs do not show through the caret. After Enter, the page is the new PDF.

## What was awkward, and what this changes

On that revision the input ran `select()` as soon as a line opened. The first Backspace or Delete therefore erased the whole line in the field instead of the previous character. A second click could select the whole line again. Delete with the caret at the end of a normal field does nothing, so if the selection was lost, Delete felt dead. Backspace outside a text field can also step through browser history.

The patch, `edit-mode-erase.patch`:

- Puts the caret at the end of the line.
- Leaves that caret alone if you click the same line again.
- Lets Backspace delete the previous character and Delete delete the next one.
- Stops Backspace from leaving the page while Edit mode is open and focus is not in a field.
- Adds **Remove line**, which commits an empty string and deletes those text objects.
- Does not delete a different line, an image, a form field, or a text box when you edit one line.
- Keeps Escape as cancel, and Enter or a click outside as the way a shortened line is written into the PDF.

Ctrl+Z still undoes typing inside the field. After Enter, Folio's existing version history is the record of the change. This patch does not add a second undo stack.

## How to try it

From a clean machine, in this repo:

```bash
python3 cells/folio-edit-erase/apply_and_test.py
```

That clones the pinned revision, applies the patch, installs Folio's own dependencies, and runs the UI test. The checkout path is printed at the end. Then:

```bash
cd /that/checkout
npm run dev
```

Open a PDF you can throw away. Choose **Edit mode**, click a line of real text, and press Backspace. Press Enter to keep a shorter line. Clear the line and press Enter, or choose **Remove line**, to delete it. Save a copy from Folio if you want a file. This is the dev server, not a packaged Folio installer.

```bash
python3 cells/folio-edit-erase/test_patch.py
```

That checks the patch text. It does not download Folio.

## What the UI test covers

`scripts/test-edit-erase.mjs` in the patched tree builds a synthetic page with Helvetica text (`BakedHello`, `DropMe`, `KeepMe`), one form field (`FormHello`), and a one-pixel image. It then drives the real Electron reader:

- Backspace and Delete with no line focused leave the page in place.
- The caret starts at the end. Backspace and Delete each remove one character. Enter saves `BakedHel`. `KeepMe`, `DropMe`, the form, and the image stay.
- Clearing the line and pressing Enter removes `BakedHel` from the page text.
- **Remove line** removes `DropMe` the same way.
- The form field's own Backspace changes `FormHello` to `FormHell`.
- A Text-tool box `BoxHi` becomes `BoxH` with Backspace.

## Parents

- Ledger parent: `glean-commons-repo`. The Folio pointer from the other open PR is not on `main` yet, so it cannot be a ledger parent. The pin, URL, and MIT copyright are recorded here anyway.
- Upstream: Forward-Future/folio at the pin above. Matthew Berman announced that repository. Primary commits are GitHub user `mberman84`.

## AI assistance

Grok 4.7 (Cursor cloud agent) reproduced the keys and wrote the patch and the test. No Folio source is copied into this folder except the patch.

## PoU

No use is recorded (`uses: 0`).

## Not claimed

- This is not Timmy's installed build.
- Removing a text run is not secure redaction. The words are dropped from the page content this editor rewrites. A prior copy, version history, or an unreferenced stream could still hold them. Do not use it for secrets.
- Scanned pages, outlined letters, and grouped art are still not editable as text.
- No installer was built. No upstream pull request was opened.

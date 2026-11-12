# Your own version of any tool

> If you can think it, you can build it. — The Glean System, Draft 1.0, sec 7.4
> AI auto-improves tools for usefulness. — sec 4.4

Software usually comes one way: the maker's way. Here, every tool can be yours.

```
  you say how it should differ
            │
            ▼
   YOUR VERSION ──────────► SHARED ──────────► ADOPTED ──────────► THE ORIGINAL
   private, versioned,      one file in        by others,          a person approves;
   runs only for you        the commons,       one voice per       everyone gets it,
                            credited to you    account             credit flows up
```

## 1. Make it yours

Connect the [tool server](../mcp/) and say what you want changed:

> "When you draft the final notice, offer a payment plan instead of hinting at further steps."

Your AI opens a private working copy of the tool, makes the change, runs the tool's own tests, and saves it. If the tests fail, nothing is saved. From then on *your* tool server runs *your* version. The original, and everyone else, are untouched.

Your versions live in a folder you own (next to your books, `<books>-versions`). It is a git repository, so every save and switch is a timestamped entry you can go back to:

> "Switch back to the original." · "Go back to my previous version." · "What versions do I have?"

## 2. We do not lose ground

The original keeps improving. Each time your tool server starts, your version is re-fitted onto the current original:

- The original changed somewhere else → your change is carried over. You get both.
- The original changed the same lines → the copy you already had keeps running, and you are told to have your AI redo the change.
- The original now contains your change → you are quietly moved back to the original. Nothing left to maintain.
- Your version fails to load → the original runs instead, with a note.

## 3. Share it

> "Share that."

You get one file: the change, your wish in your own words, your name, and the AI that helped. It never contains your business data. Send it to a friend, or offer it to everyone with a pull request that adds:

- `variants/shared/<tool>/<id>.json` — the file
- `ledger/pending/variant-<id>.json` — your credit (a draft is written for you)

CI checks the file is unaltered (its id is a fingerprint of its contents), that it fits the original, and that the tool's tests pass with it applied. A person reviews and merges.

## 4. Adopt someone else's

> "What versions of the reminder tool have people shared?" · "Try the plan-before-pressure one."

Your AI shows you exactly what the change does before anything runs. It is someone else's code, so read it. On your OK it is checked against the original, tested, and switched on. Switch back any time.

If it serves you, say so. Add `variants/adoptions/<id>/<your-github-login>.json`:

```json
{"variant": "<id>", "since": "2026-11-12"}
```

One file per GitHub account, added by that account. CI refuses a pull request that adds a voice for anyone but its author. The version's own author never counts.

## 5. It becomes the original

The dashboard shows every shared version and its count. At **30 independent adopters** (the bar in [ANALYST.md](../ANALYST.md)) it is ready for a decision:

```bash
python3 scripts/promote_variant.py <id> --approved-by "Your Name"
```

That applies it to the cell, runs the tests, and writes a ledger entry crediting both the original and the version's author, so value flows up the tree (whitepaper sec 4.3). It never merges. A person opens and merges the pull request. After that, everyone running the version is simply on the original.

Not every good version should win. If it suits some people and not others, it stays a shared version forever, and that is fine (ANALYST.md calls this *coexist*).

## Programs outside the commons

A variant can also be a patch on a pinned outside project (an `upstream/` pointer). Have your AI change your local git copy of the program, then save with `folder` set to that copy. The change is stored as a patch on the exact commit it started from; others apply it to their own copy at that commit. Building and running the program stays with that project's own instructions.

## Honest limits

- A count of GitHub accounts is a signal, not proof of use. It can be gamed with fake accounts, which is why a person reviews every promotion and why sudden spikes should be questioned.
- Adopting runs someone else's code on your machine. Shared versions are reviewed before they merge, and you are shown the change, but read it.
- Versions change text files only. Re-fitting uses `git` when it is installed.
- The public hosted endpoint can only browse shared versions. Making and adopting happen on your own machine.

## Files

| File | What it is |
|------|------------|
| `engine.py` | Make, test, save, switch, re-fit, share, adopt; standing |
| `shared/<tool>/<id>.json` | A version offered to everyone |
| `adoptions/<id>/<login>.json` | One person saying "I use this" |
| `../scripts/check_variants.py` | The CI check |
| `../scripts/promote_variant.py` | Prepares a promotion for a person to approve |

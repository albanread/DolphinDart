# DD12 — Dialogs & polish (= milestone UI-5) `M` — **THE GOAL GATE**

**Objective:** modality, common dialogs, clipboard, keyboard navigation —
and with them the project's acceptance test: **the Dolphin MVP GUI running.**
Prior-art G7 transfers as scope + gate.

**Read first:** prior-art G7 + the design §3.3 (IsDialogMessage quirks — 25
years of Dolphin hardening, the reason we port instead of rewrite); the DD7
door's nesting machinery (modal loops are its second customer, after
synchronous creates).

> **Dependency (recorded 2026-08-16):** stacked modals hard-require
> PER-WINDOW routing — the funnel carrying the HWND and `UiSession`
> dispatching via `viewFor:` rather than `LastWindow`. That lands in DD10's
> view side (see the DD10 status block); this sprint should find it done, and
> its first gate item should re-assert it under two live windows.

## The wave

`DialogView` modality on a nested `run_modal_loop` (native, in the DD7 host:
a nested pump with owner-disable, LIFO), `AspectBuffer` ok/cancel semantics,
MessageBox (blocking `MessageBoxW`; `TaskDialogIndirect` if cheap),
`GetOpenFileNameW`/`GetSaveFileNameW`, Prompter family via transpiled
resources (**first use of the translator's `--resources` path** — the
view-resource `become:` site is designed around by resource transpilation,
prior-art §5.9/decision A8), clipboard text (`CF_UNICODETEXT` only, v1),
keyboard-navigation audit (`IsDialogMessage` in the pump; tab order; Esc/
Enter defaults).

## Work

1. Translate the wave; nested-pump support in the DD7 host (modal loops are
   LIFO — the accepted divergence from Dolphin's forked-main out-of-order
   dismissal stands, prior-art G-d).
2. Resource transpilation: the prompter's view resources → source-built
   equivalents (the `--resources` subcommand emits a builder doit; no STL
   binary reader in v1 — backlog).
3. Clipboard natives (open/get/set/close, Unicode).
4. The keyboard audit: a written pass over the §3.3 quirk list against our
   pump, each quirk either handled or logged as a known-divergence.

## Gate — the project's acceptance test

All prior gates still green, plus, driven end-to-end via TCL with snapshots:

1. From the DD11 browser: a menu command opens a **modal prompter** editing a
   value with buffered OK/Cancel — cancel reverts, OK commits (model
   asserted both ways).
2. **Two stacked modals** open and dismiss in LIFO order; the outer shell is
   provably disabled while they're up (a click on it does nothing —
   event-count assert).
3. File-open dialog round trip: pick a file, the path lands in the image,
   the dialog's directory state persists across two openings.
4. Clipboard: copy from a `TextEdit`, paste into another, content asserted.
5. Esc closes the top modal; Enter fires the default button; Tab cycles the
   prompter's controls in resource order.

**When this gate is green, the commitment is met: the Dolphin MVP GUI is
running on the Dart VM, natively, on Windows ARM64 and x64.** Record the
closing numbers (translated class count, suite counts, both arches, and a
gallery of the gate snapshots) in `dd12_NOTES.md` — this is the project's
"race completed" entry.

## Traps

- A nested pump re-enters the wndproc door by construction — the DD7 depth
  gates are the safety net; re-run them as part of this gate, under a live
  modal.
- `GetOpenFileNameW` runs its own dialog pump and calls hooks on our thread —
  the door must tolerate foreign-window messages it never registered
  (generation map answers DefWindowProc — prove with a test, prior-art G-j's
  fallback logic).
- `AspectBuffer` is where ok/cancel *semantics* live — port its tests, not
  just its class; a prompter that "works" by writing through on every
  keystroke passes a naive gate and is wrong.

# DolphinDart

**Status: 0% complete.**

A port of **Dolphin Smalltalk 8** — its language layer, the Windows primitives it
needs, and above all its **Model-View-Presenter GUI framework** — onto the
**Dart 1.24.3 VM**. Smalltalk is compiled straight to Dart flow-graph IR and run
by the Dart JIT; there is no bytecode interpreter anywhere in the path. One
source tree targets Windows **x64** and **ARM64**.

"Done" means Dolphin's own MVP framework and its class browsers running as real
windows — nothing less. Measured against that goal, the work has barely begun.

## Design overview

A high-level diagram of the architecture — the compile pipeline, the way the
Smalltalk object model is fused with Dart's (core classes *are* Dart classes; a
send resolves four ways), and what the running image stands on:

- **In this repo:** [docs/design-overview.html](docs/design-overview.html)
  (open locally in a browser)
- **Hosted:** https://claude.ai/code/artifact/7899da8b-468a-4c5f-a5dc-34b10c0f269c

## History

The original project README — the full mission statement plus the WINDART
substrate's build and layout documentation — is preserved at
[README.origin.md](README.origin.md).

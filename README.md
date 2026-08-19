# DolphinDart

**Status: 0% complete.**

A port of **Dolphin Smalltalk 8** — its language layer, the Windows primitives it
needs, and above all its **Model-View-Presenter GUI framework** — onto the
**Dart 1.24.3 VM**. Smalltalk is compiled straight to Dart flow-graph IR and run
by the Dart JIT; there is no bytecode interpreter anywhere in the path. One
source tree targets Windows **x64** and **ARM64**.

**"Done" is not "it runs."** It is every ported class proven behaviorally
equivalent to Dolphin — method by method, against a live Dolphin 8.2.3 oracle
for semantics, and winkb plus a real 64-bit run for layout. Translating the
corpus, building the compiler, and getting the first real view on screen were
all prerequisites to *beginning* that proof. Against the conformance bar, ~99%
of the work remains — hence 0%.

## Design

Three views of the architecture: how Dolphin source becomes native code, how the
object model fuses with Dart's, and what the running image stands on. The full
version — with the scope doctrine, status ledger and the traps that shaped it —
is in [docs/design-overview.html](docs/design-overview.html) (open in a browser).

### 1. Source to machine code

Dolphin's chunk files are translated to the house dialect ahead of time, then a
C++ front end inside the VM compiles them to Dart IR. Dolphin's own 32-bit VM is
nowhere on this path — it is reading material, not a dependency.

```mermaid
flowchart LR
  corpus["dsfork corpus<br/>3,164 .cls · 394 .pax"]
  oracle["dolphin-oracle<br/>booted 8.2.3"]
  winkb["winkb<br/>types.size_bits"]
  trans["tools/dolphin2mst<br/>translator (Python)"]
  mst["st/**/*.mst<br/>696 files — the image, in Smalltalk"]
  audit["tools/audit_*.py"]

  subgraph fe["Our compiler — C++ inside the Dart VM"]
    direction LR
    lex["st_lexer"] --> par["st_parser"] --> fg["st_flow_graph_builder<br/>on:do: to try/catch"] --> ld["st_loader"]
    cocoa["cocoa.dart<br/>51 call-site helpers"]
  end

  ir["Dart flow-graph IR<br/>no bytecode, no dispatch loop"]
  jit["Dart 1.24.3 JIT"]
  native["native arm64 · x64"]

  corpus --> trans
  oracle -. semantics .-> trans
  winkb -. real sizes .-> trans
  trans --> mst
  audit -. audits .-> mst
  mst --> lex
  fg -. rewrites .-> cocoa
  ld --> ir --> jit --> native
```

### 2. The object model is fused

The core classes are not ported — they *are* Dart's own: a `SmallInteger` is a
Dart `int`, an `Array` is a Dart `List`, a `String` literal is a Dart `String`.
Nothing is boxed. The price of that fusion is dispatch: a single Smalltalk send
can be answered in four places, and only two of them are Smalltalk.

```mermaid
flowchart TB
  recv["a Smalltalk send — rcvr sel: arg<br/>the receiver is already a Dart object:<br/>integer to int · array to List · string to String"]
  p1["1 · compile-time · answered by Dart<br/>call-site helper rewrite to dart:cocoa<br/>at: size do: value printString (~51 selectors)"]
  p2["2 · compile-time · answered by Dart<br/>dart:core alias to the object's own method<br/>equals to ==, printString to toString, bitAnd: to &amp;"]
  p3["3 · runtime · answered by Smalltalk<br/>class-chain lookup to compiled IR to JIT<br/>user and MVP methods — Figure 1's path"]
  p4["4 · runtime · answered by Smalltalk<br/>noSuchMethod to extension-holder probe<br/>3 factorial · gcd: · MVP protocol on core types"]
  out["all four miss:<br/>native error reified (ZeroDivide),<br/>else doesNotUnderstand: to MessageNotUnderstood"]

  recv --> p1
  recv --> p2
  recv --> p3
  recv --> p4
  p1 -.->|miss| out
  p2 -.->|miss| out
  p3 -.->|miss| out
  p4 -.->|miss| out

  classDef dart fill:#e6ecee,stroke:#7f95a0,color:#0d1b24;
  classDef st fill:#14708f,stroke:#0d4a5e,color:#ffffff;
  class p1,p2 dart;
  class p3,p4 st;
```

The core types are **sealed** Dart classes, so Smalltalk's extra protocol lives
on a parallel `"<Name> ext"` holder, reached only when the first three paths miss:

| Smalltalk class | Is, at runtime | ST-only protocol reached via |
|---|---|---|
| SmallInteger / LargeInteger | one Dart `int` — arbitrary precision | path 4, on `Integer ext` |
| Float | Dart `double` | path 4, on `Float ext` |
| String | Dart `String`, immutable | path 4; mutation falls back to a char buffer (a `List`) |
| Symbol | interned Dart `String` | path 4, on `Symbol ext` |
| Array | Dart `List` — `#(…)`, `Array new:`, every `collect:` | path 4, on `Array ext` |
| Character | one of 256 canonical `StChar` | path 4, on `Character ext` |

Exceptions ride the same fusion: `on:do:`/`ensure:` lower onto Dart
`try`/`catch`/`finally`, `signal` becomes a Dart `throw`, and `become:` is the
VM's own primitive — the machinery is Dart's, the hierarchy is Smalltalk's.

### 3. What the running image stands on

Above the seam is Smalltalk; below it is C++ or Dart, whichever fits. The seam is
a real wndproc that re-enters the image synchronously, to any depth.

```mermaid
flowchart TB
  subgraph IMG["The image — Smalltalk"]
    direction LR
    world["st/world<br/>house kernel · 85 files"]
    prims["st/prims<br/>35 FFI libs · 387 structs"]
    dcompat["st/dolphin_compat"]
    mvp["st/mvp<br/>Dolphin's own MVP<br/>137 classes · 5,331 methods"]
    mvpc["st/mvp_compat<br/>scaffolding — retires as views land"]
    ext["st/ext/gamepane<br/>games + sound"]
  end
  subgraph SEAM["The seam — C++"]
    direction LR
    door["win_mvp.cpp — the wndproc door<br/>messages reflect up, handlers re-enter down"]
    pump["win_host.cpp — pump + posted-action queue"]
  end
  subgraph FLOOR["The Windows floor — C++"]
    direction LR
    ffi["FFI + marshalling"]
    views["win_view · win_canvas (Direct2D)"]
    workers["Workers on Dart isolates"]
    game["Direct3D 11 + XAudio2"]
  end
  subgraph REUSE["Reused, not rewritten"]
    direction LR
    scint["Scintilla + Lexilla<br/>rebuilt ARM64"]
    res["DolphinDR8.dll<br/>ARM64 · 295 icons"]
  end

  IMG <--> SEAM
  SEAM --> FLOOR
  FLOOR --> REUSE

  classDef st fill:#14708f,stroke:#0d4a5e,color:#ffffff;
  classDef scaf fill:#f2ead6,stroke:#8d6a24,color:#3a2c0a;
  class mvp st;
  class mvpc scaf;
```

## History

The original project README — the full mission statement plus the WINDART
substrate's build and layout documentation — is preserved at
[README.origin.md](README.origin.md).

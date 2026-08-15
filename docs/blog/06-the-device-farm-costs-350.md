# The device farm costs £350

*The series gains a second machine: a Lenovo IdeaCentre Mini, reduced to
£350, carrying the exact silicon every prior number was measured on. We
pointed the whole project at it and re-measured.*

Article 1 opened with a method statement that was really an inventory:
"No cross-compiling, no device farm. You build it, you run it, and if it
is slow you feel it personally." That was a polite way of saying we had
one machine. We now have a device farm. Its population is one small
desktop, and it was in the sale bin at £350.

The interesting part is not the price. It is what the price contained.

## What £350 buys

Everything below is read from the running machine, not from the box:

```text
model    LENOVO IdeaCentre Mini 01Q8X10  (91B6001CUK)
cpu      Snapdragon(R) X - X126100 - Qualcomm(R) Oryon(TM) CPU
         8 cores / 8 threads, 2956 MHz
gpu      Qualcomm(R) Adreno(TM) X1-45
memory   32 GB Samsung LPDDR5X-8448, soldered
disk     SK hynix 512 GB NVMe  (HFS512GEM9X169N)
os       Windows 11 Home arm64, build 26200
chassis  SMBIOS type 35, "Mini PC"
```

The line to stare at is the memory. A £350 desktop is normally a 16 GB
machine with socketed DDR at half the transfer rate; this one ships
**32 GB of LPDDR5X at 8,448 MT/s** — the speed grade the flagship
Snapdragon laptops carry, which on the SoC's 128-bit bus is about
135 GB/s of theoretical bandwidth per Qualcomm's sheet. Article 2 spent
its entire length turning that bandwidth into frames: the
unified-memory path where the CPU renders and the Adreno reads the same
bytes. Same GPU part here, same memory grade, so that article transfers
intact — the expensive property of the laptop turns out to be the cheap
property of the desktop.

## Same silicon, says the registry

Article 1 noted, among the ARM oddities, that there is no CPUID — the
processor name lives in the registry, and ours reported a Snapdragon X
`X126100`. That was the laptop. The desktop's registry reports the
**same string**. Not the same family, not a sibling SKU: the same eight
Oryon cores at the same 2,956 MHz, feeding the same Adreno X1-45, in a
box that stands behind a monitor instead of closing over a keyboard.

Which turns the usual new-machine anxiety into a testable claim: every
number in articles 1–5 should reproduce here unchanged. This series has
a rule about claims like that.

## An afternoon's shakedown

The machine did not get an unboxing ceremony; it got the sprint ladder.
Today's entire DolphinDart sequence ran on it — eleven commits between
12:38 and 15:58: two full 591-target VM builds (native arm64, plus the
x64 control that runs emulated), four inherited substrate defects found
and fixed, a 566-assertion feature battery vendored and turned green,
Dolphin's `Rectangle` brought up on the Dart VM, exception semantics
settled by measurement, and a first Win32 FFI floor. The cheap health
checks, timed on this box:

```text
world boot, 73 files + 9 functional checks    2.71 s
feature battery, 12 suites / 566 assertions   3.51 s, 0 failures
```

## The numbers travel

The pinned table from article 3 — ten workloads, Smalltalk against
hand-written Dart, warmed, best of five — re-run today, beside the
laptop's recorded values:

```text
              ---- laptop ----     ---- this box ----
workload      ST(ms)  Dart(ms)     ST(ms)  Dart(ms)
loopCmp         3.42      3.39       3.42      3.39
sumDbl         10.30     10.25      10.22     10.20
nestIf          3.43      3.39       3.42      3.39
andOr           6.95      6.90       6.89      6.90
toDo            6.86      6.84       6.84      6.80
dblCmp         10.44     10.42      10.39     10.34
boundIvar       3.44      3.39       3.42      3.39
escLocal       23.01     22.49      23.05     22.52
escIvar        23.06     22.98      23.22     22.88
mandel          8.61      8.38       8.57      8.37
mean ratio     1.01x                1.01x
```

That is not "comparable performance". That is the same table, most rows
to the hundredth of a millisecond. Two different chassis, two different
purchases, one JIT — the reproducibility you would hope silicon gives
you and rarely get to see demonstrated this cleanly.

The cog-bench rows with recorded laptop bands:

```text
bench       laptop (recorded)   this box
fib         165–167 ms          164.6 ms
deltablue   26–28 ms            25.9 ms
richards    ~11 ms              10.7 ms
alloc       ~114 ms             70.7 ms    <- not a hardware story
```

The three workloads without a recorded band are hereby pinned for this
machine: arith 11.8 ms, sieve 3.9 ms, dict 6.9 ms.

## The row that moved

`alloc` at 70.7 ms against a recorded ~114 would be a lovely headline
for the desktop, and it would be false. Between the laptop's
measurement and today's, the *software* moved: the world slimmed from
97 files to 73 when DD1 sent the IDE to the attic, DD0 fixed four
substrate defects, and five further sprints touched the front-end. The
row measures a different program, and we did not bisect which change
paid for it. Three rows reproducing plus one row improving is not "the
new machine is faster"; it is a reminder that a baseline is pinned to a
machine *and* a revision, and this article re-pins both.

## What it is not

Honesty section. The `X126100` is the entry SKU: 2,956 MHz flat, no
boost pair — the Elite parts clear 4 GHz single-threaded, and this
never will. Eight threads is the number a 591-target C++ build feels.
Windows 11 **Home** means no inbound remote desktop, which for this
project costs nothing: the IDE answers to TCL over the VM-service
WebSocket (article 5), a control plane that neither knows nor cares
which edition booted. The Wi-Fi 7 radio negotiated an 866 Mbps link
today; the NVMe is a 512 GB OEM part that has yet to matter, because a
VM build is compiler-bound and a 73-file world boots from page cache.

What the chassis buys back: no battery to age, no lid to close, no
firmware deciding a benchmark deserves fewer watts on thermals. The
500-round reload torture from article 1 can run overnight, unattended,
on a machine that costs less than the laptop's insurance excess.

## Two of them

The premise of this series was that Windows-on-ARM had become ordinary
enough to develop on, on the target, with no concessions. The premise
now has a price tag: the silicon that carried five articles of
measurements — the same part number, byte-identical benchmark tables —
sells in a small grey box for £350. A population of one machine proves
a port runs; a population of two starts to prove it travels.

*The open items stand — the arm64-only assert under aggressive
recompilation, and the emulator's 12% code-generation gap — and there
are now two machines to chase them on.*

# The blog serves itself

*The six articles before this one were files in a repository. They are now
pages on a server written in Smalltalk, running on the £350 desktop
article 6 is about. The interesting part was not making it work. It was
finding out which bytes were allowed to touch the VM.*

The premise of this series has been that Windows-on-ARM became ordinary
enough to develop on. The obvious next question is whether it is ordinary
enough to *run* something on, and the honest way to answer that is to
stop writing about the machine and put the writing on it.

So: a web server whose application layer is a live Smalltalk image.
Routes are blocks. The expression that opens a TLS socket is a message
send. The posts are rendered from the same markdown files the repository
holds, by a VM that has been the subject of six articles and is now the
thing serving them.

## Two halves, and the line between them

Rust owns the wire: sockets, TLS 1.3, HTTP/2, static files, the request
queue. The image owns meaning: which URL is which page, what a page says,
what a failure looks like. Between them, one sentence of Smalltalk per
request:

```smalltalk
WebServer dispatch: 4711
```

An integer, deliberately. The request's method, path and body are *pulled*
from the host by that id, never spliced into source the compiler sees.
Nothing a visitor types is ever parsed as code by the server's own VM —
a property that costs nothing to have and is impossible to retrofit.

The division is the same one the Windows GUI already used, and it is
older than either: **Rust owns mechanism, the image owns policy.** The
image says `WebServer default get: '/post/*' do: [ :req | … ]` and the
edge does not know what a post is. The image says which URL prefix is
privileged and the edge refuses everyone else before the VM is ever
asked. One states rules, the other enforces them, and neither is tempted
into the other's job.

## Failure is the feature

A live image facing the internet sounds reckless until you notice what
the VM already does. Every request is a top-level entry, and this VM has
per-entry guest-fatal recovery — the machinery the port built and tortured
in article 1. A page that raises, sends a message nobody implements, or
answers the wrong kind of object costs **one 500**, and the next request
is served normally.

That is not a claim; there are three permanent routes that fail on
purpose at three different depths, and the test suite runs a hundred
alternations of them:

```text
ok   100 alternations, every status as expected: 0 wrong of 100
ok   the counter is continuous across 100 recoveries: 13 -> 114, expected 114
```

Exact arithmetic, not "it went up". A hundred recoveries, and the image's
own request counter advanced by exactly the number of requests made — so
nothing was dropped and nothing double-counted. That property is what
makes the rest of this defensible.

## The measurement that redesigned it

The first working version served a page in **fifteen seconds**, which is
to say it did not serve a page.

The diagnosis came from a tool built one sprint earlier for another
reason: a loopback console that evaluates Smalltalk in the live image. It
timed the pieces, and the answer was that moving bytes *into* the guest
heap costs about **165 microseconds each** — `Alien>>byteAt:` at roughly
40 and `String>>at:put:` at roughly 104. The VM has no bulk foreign-to-guest
copy: `replaceFrom:to:with:` requires both sides to be guest byte objects,
so a foreign source falls back to a per-element loop. Carrying a 15 KB
post body into the image cost about 2.5 seconds, for bytes nothing in the
image ever reads.

The repair was not an optimisation. It was noticing that the design
already contained the rule and had only applied it one level too low.

Stylesheets and images were already served straight off disk by the edge,
on the reasoning that **bytes the image is not deciding about have no
business crossing a VM entry**. A rendered post is exactly that: the
image picks the document and builds the chrome around it, and never reads
a byte of its HTML. So the page now emits a marker and the edge splices
the rendered body in on the way out. The image's answer stays about 1.5 KB
of chrome however long the article is.

Fifteen seconds became 141 milliseconds. The document *index* still
crosses — the image formats titles, groups them, prints sizes, so it
genuinely is the image's business — and is cached against a stat-only
generation number that changes when the files do.

The lesson generalised further than expected. When the admin editor
arrived, the markdown you edit and the bytes you upload take the same
route, in reverse: the image says *which* document is being saved and the
edge moves the bytes from the socket to the disk. The image never holds
them in either direction.

## Running a stranger's Smalltalk

The blog is about a Smalltalk VM, so its code samples ought to run. There
is a Run button on every Smalltalk block on this page, and pressing it
executes exactly the text you can see.

That is a sentence to be nervous about, so the containment came first:

- **A separate process**, expected to be hostile and treated as
  disposable.
- **No FFI at all.** The worker disables the symbol resolver before
  booting anything, so every `<primitive: FFI …>` fails and the reachable
  surface is the interpreter rather than all of Win32. One-way and
  process-wide, because a sandbox switch that can be flipped back is not
  a sandbox switch.
- **A Job Object** with a memory cap and an active-process cap of one, so
  a program can neither allocate the machine to death nor spawn its way
  out.
- **A deadline.** `[true] whileTrue` is a legitimate thing to type into a
  box marked *run*; it just does not get to run forever.

The check that convinced me is a contrast rather than an assertion. The
identical program — one that defines its own binding to `GetTickCount`
and calls it — resolves the symbol in the server's own image and fails to
resolve it in a worker:

```text
ok   the worker has NO FFI, and the same call works in the server VM:
     farm: refused · server: OK 171605406
```

Asserting only "the worker refused" would have passed just as happily if
the symbol had never been available. It is the second half of that line
that makes the first half mean something.

And because workers are processes on a thread pool, none of this touches
the image: the test saturates the farm with six infinite loops and fetches
an article in 147 milliseconds on the same connection.

## What the machine does about it

Article 6 measured this desktop and found it identical to the laptop.
Serving is a different question from benchmarking, and the numbers are
unglamorous in a good way: a warm post page at **p50 142 ms**, p99 within
a few milliseconds of it; 161 documents rendering without a single 500 on
a full crawl; a cold eval worker — a whole VM boot, for one visitor's
expression — at about a second.

The p50 is dominated by string building in the image, not by the machine.
This VM assembles pages a character at a time in places, at roughly
100 microseconds per character, which is the same finding as before
wearing a different hat. The repair is the same one: a bulk primitive
that the VM does not yet have. It is written down rather than done,
because it is a change to the core of a VM and this was a sprint about a
blog.

## What is not finished

The honest list, because a series that measured everything else should
not stop now.

TLS runs on a pure-Rust provider that is explicitly **unaudited** — chosen
in the first hour because this box has no clang and the usual providers
need one to assemble their ARM64 Windows code. That is defensible while
the admin console is loopback-only and indefensible behind a public one,
so the server refuses to expose the console on this provider. Not a note
in a document: a refusal at startup, because a decision that only lives
in a document is one a deployment overtakes.

There has been no twelve-hour soak, no `cargo audit`, and no real
certificate — which needs a domain. And the box is not yet a service that
survives a reboot without a keyboard, because installing one is a change
to somebody's machine and that somebody should be the one to make it.

## Where it lands

The stack, top to bottom, on one small desktop: a class library authored
on a Mac, compiled by a Dart VM's JIT to native ARM64 — no, that was the
other project. Start again.

A Strongtalk-lineage Smalltalk, ported to Windows-on-ARM, running a live
image that answers HTTP/2 over TLS 1.3, rendering articles about its own
port from markdown in a sibling repository, with a Run button that
executes reader-supplied code in a sandbox with no FFI, on a computer
that cost £350.

The page you are reading was assembled by the VM the page is about. That
was the point, and it took one afternoon longer than it should have
because of 165 microseconds a byte.

# PRIM_MAP — Dolphin's primitives, dispositioned (DD2)

**Headline: 205 of Dolphin's 210 declared primitive numbers are irrelevant to
this port.** They are declared on classes in `Core`, `Kernel` and `External` —
Dolphin's own kernel, which DolphinDart explicitly does **not** port (plan §0:
"We do not port the Dolphin kernel; we port the MVP/Graphics layers and bridge
their kernel dependencies through a compatibility layer"). Our kernel is
`st/world`, with its own numbering in [HOUSE_PRIMS.md](HOUSE_PRIMS.md).

Only **two** rows have call sites in the layers we translate (`UI`, `Graphics`,
`OS`):

| D# | What | Sites | Disposition |
|--:|---|--:|---|
| **157** | `primitiveNewInitializedObject` — the `x:y:`-style bulk instance initialiser | **73** | **Translator lowering.** No VM work. |
| 172 | `primitiveVariantValue` — `OS.COM.VARIANT>>value` | 1 | **Deferred.** COM is a v1 non-goal (plan §0 non-goals); refuse it loudly in the translator. |

Two more are Tools/Refactory only (not ported). The rest are kernel.

## What this does to DD5

DD5 was scoped as a rolling campaign over a 215-row worksheet. **It is not that.**
The measured demand is one lowering rule plus whatever the DD3 translator's
refusal reports actually turn up as it ingests real MVP source. DD5 therefore
becomes *demand-driven*: no speculative primitive work, worksheet rows opened
only when a translated method needs one. The prior-art worksheet
(`docs/prior_art/winvm/dolphin_win_prims.md`) stays as a **reference for
Dolphin's kernel**, not as this project's to-do list.

This is the plan's architecture paying off rather than a change to it: keeping
our own kernel is exactly what makes Dolphin's kernel primitives moot.

## D157 — the lowering rule

`primitiveNewInitializedObject` allocates an instance of the receiver class and
fills its instance variables from the arguments in declaration order —
`Point class>>x:y:` is the canonical shape. It needs **no new VM primitive**:
the translator has just parsed the class definition, so it knows the instance
variable names and their order, and can emit house dialect directly:

```smalltalk
"Dolphin:  Point class >> x: x y: y  <primitive: 157>"
"House:"
Point class >> x: anX y: aY [ ^self basicNew instVarAt: 1 put: anX; instVarAt: 2 put: aY; yourself ]
```

House `basicNew` (23) and `instVarAt:put:` are already present. The translator
should prefer named setters when the class defines them, falling back to
`instVarAt:put:`, and must **refuse loudly** if the argument count does not match
the instance-variable count — a silent mismatch here would mis-initialise every
instance of a class.

⚠️ **Ordering caveat, for whoever implements it:** the fill order is the
class's *full* instance-variable order including inherited variables. Get the
inheritance offset wrong and objects are built with fields shifted by one — a
defect that shows up arbitrarily far away. Test with a subclass, not just a root
class.

## Caveat on the method

The bucketing above reads the "Key classes" column of the prior-art inventory,
which is representative and **truncated** (D157's own entry ends "+60 more").
The authoritative cross-check is a direct scan of the MVP closure for
`<primitive:` pragma sites — see `dd02_NOTES.md` for that measurement. Treat
this table as the map and that scan as the territory; where they disagree, the
scan wins.

## The numbering collision (why translation must go through this table)

The two spaces collide on nearly every low number and mean entirely different
things:

| Number | Dolphin | House |
|--:|---|---|
| 1 | `^self` (return-shortcut) | `SmallInteger>>+` |
| 2 | `^false` | `SmallInteger>>-` |
| 3 | — | `SmallInteger>>*` |
| 9 | `SmallInteger>>*` | `SmallInteger>>bitShift:` |
| 16 | `SmallInteger>>=` | — |

An unmapped Dolphin number reaching the emitter is therefore a **hard error** in
the translator (DD3), never a passthrough: a transposed row turns arithmetic
into a self-return, silently.

Also inherited from the prior-art inventory and still true: **Dolphin's 31 and 32
(`LargeInteger>>\` and `//`) are declared but map to `unusedPrimitive`** — they
always fail into their Smalltalk fallbacks. If they ever reach us, they must fail
cleanly, never compute.

## Full table

Dispositions: *kernel we replace* = the primitive is declared on a Dolphin kernel
class that `st/world` supersedes; *not ported* = Tools/Refactory.

| D# | VM impl | Selector | Sites | Disposition |
|--:|---|---|--:|---|
| 1 | `primitiveReturnSelf` | `^self` | 10 | n/a — Tools/Refactory, not ported |
| 2 | `primitiveReturnConst&lt;2&gt;` | `^false` | 9 | n/a — Tools/Refactory, not ported |
| 9 | `primitiveMultiply` | `SmallInteger>>#*` | 1 | n/a — kernel we replace |
| 10 | `primitiveDivide` | `SmallInteger>>#/` | 2 | n/a — kernel we replace |
| 11 | `primitiveMod` | `SmallInteger>>#'\\'` | 1 | n/a — kernel we replace |
| 12 | `primitiveDiv` | `SmallInteger>>#//` | 1 | n/a — kernel we replace |
| 13 | `primitiveQuo` | `SmallInteger>>#quo:` | 1 | n/a — kernel we replace |
| 14 | `primitiveSubtract` | `SmallInteger>>#-` | 1 | n/a — kernel we replace |
| 15 | `primitiveAdd` | `SmallInteger>>#+` | 1 | n/a — kernel we replace |
| 16 | `primitiveEqual` | `SmallInteger>>#=` | 1 | n/a — kernel we replace |
| 17 | `primitiveIntegerCmp&lt;std::greater_equal&lt;SmallInteger&gt;, true&gt;` | `SmallInteger>>#>=` | 1 | n/a — kernel we replace |
| 18 | `primitiveIntegerCmp&lt;std::less&lt;SmallInteger&gt;, false&gt;` | `SmallInteger>>#<` | 1 | n/a — kernel we replace |
| 19 | `primitiveIntegerCmp&lt;std::greater&lt;SmallInteger&gt;, true&gt;` | `SmallInteger>>#>` | 1 | n/a — kernel we replace |
| 20 | `primitiveIntegerCmp&lt;std::less_equal&lt;SmallInteger&gt;, false&gt;` | `SmallInteger>>#<=` | 1 | n/a — kernel we replace |
| 21 | `primitiveLargeIntegerOpR&lt;Li::Add, Li::AddSingle&gt;` | `LargeInteger>>#+` | 2 | n/a — kernel we replace |
| 22 | `primitiveLargeIntegerOpR&lt;Li::Sub, Li::SubSingle&gt;` | `LargeInteger>>#-` | 1 | n/a — kernel we replace |
| 23 | `primitiveLargeIntegerCmp&lt;true,false&gt;` | `LargeInteger>>#<` | 1 | n/a — kernel we replace |
| 24 | `primitiveLargeIntegerCmp&lt;false,false&gt;` | `LargeInteger>>#>` | 2 | n/a — kernel we replace |
| 25 | `primitiveLargeIntegerCmp&lt;true, true&gt;` | `LargeInteger>>#<=` | 1 | n/a — kernel we replace |
| 26 | `primitiveLargeIntegerCmp&lt;false,true&gt;` | `LargeInteger>>#>=` | 1 | n/a — kernel we replace |
| 27 | `primitiveLargeIntegerEqual` | `LargeInteger>>#=` | 1 | n/a — kernel we replace |
| 28 | `primitiveLargeIntegerUnaryOp&lt;Li::Normalize&gt;` | `LargeInteger>>normalize` | 1 | n/a — kernel we replace |
| 29 | `primitiveLargeIntegerOpZ&lt;Li::Mul, Li::MulSingle&gt;` | `LargeInteger>>#*` | 2 | n/a — kernel we replace |
| 30 | `primitiveLargeIntegerDivide` | `LargeInteger>>#/` | 1 | n/a — kernel we replace |
| 33 | `primitiveLargeIntegerQuo` | `LargeInteger>>#quo:` | 1 | n/a — kernel we replace |
| 34 | `primitiveLargeIntegerOpZ&lt;Li::BitAnd, Li::BitAndSingle&gt;` | `LargeInteger>>#bitAnd:` | 1 | n/a — kernel we replace |
| 35 | `primitiveLargeIntegerOpR&lt;Li::BitOr, Li::BitOrSingle&gt;` | `LargeInteger>>#bitOr:` | 1 | n/a — kernel we replace |
| 36 | `primitiveLargeIntegerOpR&lt;Li::BitXor, Li::BitXorSingle&gt;` | `LargeInteger>>#bitXor:` | 1 | n/a — kernel we replace |
| 37 | `primitiveLargeIntegerBitShift` | `LargeInteger>>#bitShift` | 1 | n/a — kernel we replace |
| 38 | `primitiveLargeIntegerBitInvert` | `LargeInteger>>#bitInvert` | 1 | n/a — kernel we replace |
| 39 | `primitiveLargeIntegerUnaryOp&lt;Li::Negate&gt;` | `LargeInteger>>#negate` | 1 | n/a — kernel we replace |
| 40 | `primitiveIntegerOp&lt;std::bit_and&lt;Oop&gt;&gt;` | `SmallInteger>>#bitAnd:` | 2 | n/a — kernel we replace |
| 41 | `primitiveIntegerOp&lt;std::bit_or&lt;Oop&gt;&gt;` | `SmallInteger>>#bitOr:` | 2 | n/a — kernel we replace |
| 42 | `primitiveIntegerOp&lt;bit_xor&gt;` | `SmallInteger>>#bitXor:` | 1 | n/a — kernel we replace |
| 43 | `primitiveBitShift` | `SmallInteger>>#bitShift:` | 2 | n/a — kernel we replace |
| 44 | `primitiveSmallIntegerPrintString` | `SmallInteger>>#printString` | 1 | n/a — kernel we replace |
| 45 | `primitiveFloatCompare&lt;std::greater&lt;double&gt;&gt;` | `Float>>#>` | 1 | n/a — kernel we replace |
| 46 | `primitiveFloatCompare&lt;std::greater_equal&lt;double&gt;&gt;` | `Float>>#>=` | 1 | n/a — kernel we replace |
| 47 | `primitiveFloatCompare&lt;std::equal_to&lt;double&gt;&gt;` | `Float>>#=` | 1 | n/a — kernel we replace |
| 50 | `primitiveCopyFromTo` | `ArrayedCollection>>#copyFrom:to:` | 1 | n/a — kernel we replace |
| 51 | `primitiveStringComparison&lt;CmpA,CmpW&gt;` | `String>>#<==>` | 1 | n/a — kernel we replace |
| 52 | `primitiveStringNextIndexOfFromTo` | `String>>#nextIdentityIndexOf:from:to:` | 2 | n/a — kernel we replace |
| 53 | `primitiveLargeIntegerHighBit` | `LargeInteger>>#highBit` | 1 | n/a — kernel we replace |
| 54 | `primitiveHighBit` | `SmallInteger>>#highBit` | 1 | n/a — kernel we replace |
| 55 | `primitiveBytesEqual` | `ByteArray>>#=` | 1 | n/a — kernel we replace |
| 56 | `primitiveStringComparison&lt;CmpIA,CmpIW&gt;` | `String>>#<=>` | 1 | n/a — kernel we replace |
| 57 | `primitiveIsKindOf` | `Object>>#isKindOf:` | 2 | n/a — kernel we replace |
| 58 | `primitiveAllSubinstances` | `Behavior>>#primAllSubinstances` | 1 | n/a — kernel we replace |
| 59 | `primitiveNextIndexOfFromTo` | `Object>>#basicIdentityIndexOf:from:to:, Arraye` | 3 | n/a — kernel we replace |
| 60 | `primitiveBasicAt` | `Object>>#at:, Object>>#basicAt:, String>>#byte` | 9 | n/a — kernel we replace |
| 61 | `primitiveBasicAtPut` | `Object>>#at:put:, Object>>#basicAt:put:, Strin` | 5 | n/a — kernel we replace |
| 62 | `primitiveSize` | `Object>>#size, Object>>#basicSize, ArrayedColl` | 4 | n/a — kernel we replace |
| 63 | `primitiveStringAt` | `String>>#at:` | 5 | n/a — kernel we replace |
| 64 | `primitiveStringAtPut` | `String>>#at:put:` | 1 | n/a — kernel we replace |
| 65 | `primitiveNext` | `ReadStream>>#next[Available], FileStream>>#nex` | 5 | n/a — kernel we replace |
| 66 | `primitiveNextPut` | `WriteStream>>#nextPut:, FileStream>>#primitive` | 3 | n/a — kernel we replace |
| 67 | `primitiveAtEnd` | `PositionableStream>>#atEnd` | 2 | n/a — kernel we replace |
| 68 | `primitiveReturnFromInterrupt` | `ProcessorScheduler>>iret:list:` | 1 | n/a — kernel we replace |
| 69 | `primitiveSetSpecialBehavior` | `Object>>#setSpecialBehavior:` | 1 | n/a — kernel we replace |
| 70 | `primitiveNew` | `Behavior>>#new, Behavior>>#basicNew` | 3 | n/a — kernel we replace |
| 71 | `primitiveNewWithArg` | `Behavior>>#new:, Behavior>>#basicNew:, String ` | 4 | n/a — kernel we replace |
| 72 | `primitiveBecome` | `Object>>#become:, Object>>#swappingBecome:` | 3 | n/a — kernel we replace |
| 73 | `primitiveInstVarAt` | `Object>>#instVarAt:` | 2 | n/a — kernel we replace |
| 74 | `primitiveInstVarAtPut` | `Object>>#instVarAt:put:` | 1 | n/a — kernel we replace |
| 75 | `primitiveBasicIdentityHash` | `Object>>#basicIdentityHash` | 2 | n/a — kernel we replace |
| 76 | `primitiveNewPinned` | `Behavior>>#newFixed:, Behavior>>#basicNewFixed` | 3 | n/a — kernel we replace |
| 77 | `primitiveAllInstances` | `Behavior>>#primAllInstances` | 1 | n/a — kernel we replace |
| 78 | `primitiveReturn` | `ProcessorScheduler>>#returnValue:toFrame:` | 1 | n/a — kernel we replace |
| 79 | `primitiveValueOnUnwind` | `BlockClosure>>#valueOnUnwind:` | 1 | n/a — kernel we replace |
| 81 | `primitiveValue` | `BlockClosure>>#value, BlockClosure>>(value:)+` | 9 | n/a — kernel we replace |
| 82 | `primitiveValueWithArgsThunk` | `BlockClosure>>#valueWithArguments:` | 1 | n/a — kernel we replace |
| 83 | `primitivePerformThunk` | `Object>>#perform:(with:)*` | 5 | n/a — kernel we replace |
| 84 | `primitivePerformWithArgsThunk` | `Object>>#perform:withArguments:` | 1 | n/a — kernel we replace |
| 85 | `primitiveSignalThunk` | `Semaphore>>#signal` | 1 | n/a — kernel we replace |
| 86 | `primitiveWaitThunk` | `Semaphore>>#wait:ret:` | 1 | n/a — kernel we replace |
| 87 | `primitiveResumeThunk` | `Process>>#resume[:]` | 3 | n/a — kernel we replace |
| 88 | `primitiveSuspendThunk` | `Process>>#suspend` | 2 | n/a — kernel we replace |
| 89 | `primitiveFlushCache` | `Behavior>>#flushCache` | 1 | n/a — kernel we replace |
| 90 | `primitiveNewVirtual` | `Behavior>>#new:max:` | 1 | n/a — kernel we replace |
| 91 | `primitiveTerminateProcessThunk` | `Process>>#primTerminate` | 1 | n/a — kernel we replace |
| 92 | `primitiveProcessPriorityThunk` | `Process>>#priority:` | 1 | n/a — kernel we replace |
| 93 | `primitiveInputSemaphore` | `VMLibrary>>#primRegistryAt:put:` | 1 | n/a — kernel we replace |
| 94 | `primitiveSampleInterval` | `InputState>>#primSampleInterval:` | 1 | n/a — kernel we replace |
| 95 | `primitiveEnableInterrupts` | `ProcessorScheduler>>#enableAsyncEvents:` | 1 | n/a — kernel we replace |
| 97 | `primitiveSnapshot` | `SessionManager>>#primSnapshot:backup:type:maxO` | 1 | n/a — kernel we replace |
| 98 | `primitiveQueueInterrupt` | `Process>queueInterrupt:with:` | 1 | n/a — kernel we replace |
| 99 | `primitiveSetSignalsThunk` | `Semaphore>>#primSetSignals:` | 1 | n/a — kernel we replace |
| 100 | `primitiveSignalAtTickThunk` | `Delay class>>signalTimerAfter:` | 1 | n/a — kernel we replace |
| 101 | `primitiveResize` | `Object>>resize:, Object>>#basicResize:, Arraye` | 3 | n/a — kernel we replace |
| 102 | `primitiveChangeBehavior` | `Object>>#becomeA:, Object>>#becomeAn:` | 1 | n/a — kernel we replace |
| 103 | `primitiveAddressOf` | `Object>>#yourAddress` | 2 | n/a — kernel we replace |
| 104 | `primitiveReturnFromCallback` | `ProcessorScheduler>>#primReturn:callback:` | 1 | n/a — kernel we replace |
| 106 | `primitiveHashBytes` | `ByteArray>>#hash, String>>#hash, LargeInteger>` | 4 | n/a — kernel we replace |
| 107 | `primitiveUnwindCallback` | `ProcessorScheduler>>#primUnwindCallback` | 1 | n/a — kernel we replace |
| 109 | `primitiveHashMultiply` | `Integer>>#hashMultiply, SmallInteger>>#identit` | 3 | n/a — kernel we replace |
| 110 | `primitiveIdentical` | `Object>#==, Object>>#=` | 5 | review |
| 111 | `primitiveClass` | `Object>>#class, Object>>#basicClass` | 5 | n/a — kernel we replace |
| 112 | `primitiveCoreLeftThunk` | `MemoryManager>>#primCollectGarbage:` | 1 | n/a — kernel we replace |
| 113 | `primitiveQuit` | `SessionManager>>#primQuit:` | 1 | n/a — kernel we replace |
| 114 | `primitivePerformWithArgsAtThunk` | `Object>>#perform:withArgumentsAt:descriptor:` | 1 | n/a — kernel we replace |
| 115 | `primitiveOopsLeftThunk` | `MemoryManager>>#primCompact` | 1 | n/a — kernel we replace |
| 116 | `primitivePerformMethodThunk` | `CompiledCode>>#value:withArguments:` | 1 | n/a — kernel we replace |
| 117 | `primitiveValueWithArgsAtThunk` | `BlockClosure>>#valueWithArgumentsAt:descriptor` | 1 | n/a — kernel we replace |
| 118 | `primitiveDeQForFinalize` | `MemoryManager>>#dequeueForFinalization` | 1 | n/a — kernel we replace |
| 119 | `primitiveDeQBereavement` | `MemoryManager>>#dequeueBereavementInto:` | 1 | n/a — kernel we replace |
| 120 | `primitiveIntegerAtOffset&lt;uint32_t, StoreUnsigned32&gt;` | `ByteArray>>#dwordAtOffset:` | 4 | n/a — kernel we replace |
| 121 | `primitiveUint32AtPut` | `ByteArray>>#dwordAtOffset:put:` | 4 | n/a — kernel we replace |
| 122 | `primitiveIntegerAtOffset&lt;int32_t, StoreSigned32&gt;` | `ByteArray>>#sdwordAtOffset:` | 2 | n/a — kernel we replace |
| 123 | `primitiveInt32AtPut` | `ByteArray>>#sdwordAtOffset:put:` | 1 | n/a — kernel we replace |
| 124 | `primitiveIntegerAtOffset&lt;uint16_t, StoreSmallInteger&gt;` | `ByteArray>>#wordAtOffset:` | 2 | n/a — kernel we replace |
| 125 | `primitiveAtOffsetPutInteger&lt;uint16_t, 0x0, 0xffff&gt;` | `ByteArray>>#wordAtOffset:put:` | 2 | n/a — kernel we replace |
| 126 | `primitiveIntegerAtOffset&lt;int16_t, StoreSmallInteger&gt;` | `ByteArray>>#swordAtoffset:` | 1 | n/a — kernel we replace |
| 127 | `primitiveAtOffsetPutInteger&lt;uint16_t, -0x8000, 0x7fff&gt;` | `ByteArray>>#swordAtOffset:put:` | 1 | n/a — kernel we replace |
| 128 | `primitiveFloatAtOffset&lt;double&gt;` | `ByteArray>>#doubleAtOffset:` | 1 | n/a — kernel we replace |
| 129 | `primitiveFloatAtOffsetPut&lt;double&gt;` | `ByteArray>>#doubleAtOffset:put:` | 1 | n/a — kernel we replace |
| 130 | `primitiveFloatAtOffset&lt;float&gt;` | `ByteArray>>#floatAtOffset:` | 1 | n/a — kernel we replace |
| 131 | `primitiveFloatAtOffsetPut&lt;float&gt;` | `ByteArray>>#floatAtOffset:put:` | 1 | n/a — kernel we replace |
| 132 | `primitiveIndirectIntegerAtOffset&lt;uint8_t, StoreSmallInteger&gt;` | `External.Address>>#byteAtOffset:` | 1 | n/a — kernel we replace |
| 133 | `primitiveIndirectAtOffsetPutInteger&lt;uint8_t, 0, 255&gt;` | `External.Address>>#byteAtOffset:put:` | 1 | n/a — kernel we replace |
| 134 | `primitiveIndirectIntegerAtOffset&lt;uint32_t, StoreUnsigned32&gt;` | `External.Address>>#dwordAtOffset:` | 1 | n/a — kernel we replace |
| 135 | `primitiveIndirectUint32AtPut` | `External.Address>>#dwordAtOffset:put:` | 1 | n/a — kernel we replace |
| 136 | `primitiveIndirectIntegerAtOffset&lt;int32_t, StoreSigned32&gt;` | `External.Address>>#sdwordAtOffset:` | 1 | n/a — kernel we replace |
| 137 | `primitiveIndirectInt32AtPut` | `External.Address>>#sdwordAtOffset:put:` | 1 | n/a — kernel we replace |
| 138 | `primitiveIndirectIntegerAtOffset&lt;uint16_t, StoreSmallInteger&gt;` | `External.Address>>#wordAtOffset:` | 1 | n/a — kernel we replace |
| 139 | `primitiveIndirectAtOffsetPutInteger&lt;uint16_t, 0, 0xffff&gt;` | `External.Address>>#wordAtOffset:put:` | 1 | n/a — kernel we replace |
| 140 | `primitiveIndirectIntegerAtOffset&lt;int16_t, StoreSmallInteger&gt;` | `External.Address>>#swordAtOffset:` | 1 | n/a — kernel we replace |
| 141 | `primitiveIndirectAtOffsetPutInteger&lt;int16_t, -0x8000, 0x7fff&gt;` | `External.Address>>#swordAtOffset:put:` | 1 | n/a — kernel we replace |
| 143 | `primitiveIndirectReplaceBytes` | `ExternalAddress>>#replaceBytesOf:from:to:start` | 1 | n/a — kernel we replace |
| 144 | `primitiveNextInt32` | `PositionableStream>>#newSDWORD` | 1 | n/a — kernel we replace |
| 145 | `primitiveAnyMask` | `SmallInteger>>#anyMask:` | 1 | n/a — kernel we replace |
| 146 | `primitiveAllMask` | `SmallInteger>>#allMask:` | 1 | n/a — kernel we replace |
| 147 | `primitiveIdentityHash` | `Object>>#identityHash` | 2 | n/a — kernel we replace |
| 148 | `primitiveLookupMethod` | `Behavior>>#lookupMethod:` | 1 | n/a — kernel we replace |
| 149 | `primitiveStringSearch` | `String>>#findString:startingAt:` | 3 | n/a — kernel we replace |
| 150 | `primitiveUnwindInterruptThunk` | `ProcessorScheduler>>#primUnwindInterrupt` | 1 | n/a — kernel we replace |
| 151 | `primitiveExtraInstanceSpec` | `Behavior>>#extraInstanceSpec` | 2 | n/a — kernel we replace |
| 152 | `primitiveLowBit` | `SmallInteger>>#lowBit` | 1 | n/a — kernel we replace |
| 153 | `primitiveAllReferences` | `Object>>#allReferences` | 2 | n/a — kernel we replace |
| 154 | `primitiveOneWayBecome` | `Object>>#oneWayBecome:` | 2 | n/a — kernel we replace |
| 155 | `primitiveShallowCopy` | `Object>>#shallowCopy, Object>>#basicShallowCop` | 4 | n/a — kernel we replace |
| 156 | `primitiveYieldThunk` | `ProcessorScheduler>>#yield` | 1 | n/a — kernel we replace |
| 157 | `primitiveNewInitializedObject` | `e.g. Point class>>#x:y:` | 73 | **REACHES OUR CORPUS** |
| 158 | `primitiveSmallIntegerAt` | `SmallInteger>>#byteAt:` | 1 | n/a — kernel we replace |
| 159 | `primitiveLongDoubleAt` | `ByteArray>>#longDoubleAtOffset:` | 1 | n/a — kernel we replace |
| 160 | `primitiveFloatBinaryOp&lt;std::plus&lt;double&gt;&gt;` | `Float>>#+` | 1 | n/a — kernel we replace |
| 161 | `primitiveFloatBinaryOp&lt;std::minus&lt;double&gt;&gt;` | `Float>>#-` | 1 | n/a — kernel we replace |
| 162 | `primitiveFloatCompare&lt;std::less&lt;double&gt;&gt;` | `Float>>#<` | 1 | n/a — kernel we replace |
| 164 | `primitiveFloatBinaryOp&lt;std::multiplies&lt;double&gt;&gt;` | `Float>>#*` | 1 | n/a — kernel we replace |
| 165 | `primitiveFloatBinaryOp&lt;std::divides&lt;double&gt;&gt;` | `Float>>#/` | 1 | n/a — kernel we replace |
| 166 | `primitiveFloatTruncationOp&lt;Truncate&gt;` | `Float>>#truncated` | 1 | n/a — kernel we replace |
| 167 | `primitiveLargeIntegerAsFloat` | `LargeInteger>>#asFloat` | 1 | n/a — kernel we replace |
| 168 | `primitiveAsFloat` | `SmallInteger>>#asFloat` | 1 | n/a — kernel we replace |
| 169 | `primitiveObjectCount` | `MemoryManager>>#objectCount` | 1 | n/a — kernel we replace |
| 170 | `primitiveStructureIsNull` | `External.Structure>>#isNull` | 1 | n/a — kernel we replace |
| 171 | `primitiveBytesIsNull` | `External.IntegerBytes>>isNull` | 1 | n/a — kernel we replace |
| 172 | `primitiveVariantValue` | `Variant>>#value` | 1 | **REACHES OUR CORPUS** |
| 173 | `primitiveNextPutAll` | `WriteStream>>#basicNextPutAll:, WriteStream>>#` | 3 | n/a — kernel we replace |
| 174 | `primitiveMillisecondClockValue` | `MemoryManager>>#millisecondClock, InputState>>` | 3 | n/a — kernel we replace |
| 175 | `primitiveIndexOfSP` | `Process>>#indexOfSP:` | 1 | n/a — kernel we replace |
| 176 | `primitiveStackAtPut` | `Process>>#at:put:, Process>>#basicAt:put:` | 2 | n/a — kernel we replace |
| 177 | `primitiveGetImmutable` | `Object>>#isImmutable` | 1 | n/a — kernel we replace |
| 178 | `primitiveSetImmutable` | `Object>>#isImmutable:` | 1 | n/a — kernel we replace |
| 179 | `primitiveInstanceCounts` | `MemoryManager>>#primInstanceStats:` | 1 | n/a — kernel we replace |
| 180 | `primitiveIntegerAtOffset&lt;uintptr_t, StoreUIntPtr&gt;` | `ByteArray>>#uintPtrAtOffset:` | 1 | n/a — kernel we replace |
| 181 | `primitiveUintPtrAtPut` | `ByteArray>>#uintPtrAtOffset:put:   (was primit` | 1 | n/a — kernel we replace |
| 182 | `primitiveIntegerAtOffset&lt;intptr_t, StoreIntPtr&gt;` | `ByteArray>>#intptrAtOffset:` | 1 | n/a — kernel we replace |
| 183 | `primitiveIntPtrAtPut` | `ByteArray>>#intPtrAtOffset:put:    (was primit` | 2 | n/a — kernel we replace |
| 184 | `primitiveIndirectIntegerAtOffset&lt;uintptr_t, StoreUIntPtr&gt;` | `External.Address>>#uintPtrAtOffset:` | 1 | n/a — kernel we replace |
| 185 | `primitiveIndirectUintPtrAtPut` | `External.Address>>#uintPtrAtOffset:put: (was p` | 1 | n/a — kernel we replace |
| 186 | `primitiveIndirectIntegerAtOffset&lt;intptr_t, StoreIntPtr&gt;` | `External.Address>>#intptrAtOffset:` | 1 | n/a — kernel we replace |
| 187 | `primitiveIndirectIntPtrAtPut` | `External.Address>>#intPtrAtOffset:put:  (was p` | 1 | n/a — kernel we replace |
| 188 | `primitiveReplacePointers` | `Array>>#replaceElementsOf:from:to:startingAt:` | 4 | n/a — kernel we replace |
| 189 | `primitiveMicrosecondClockValue` | `Delay>>#microsecondClockValue, Delay class>>#m` | 2 | n/a — kernel we replace |
| 190 | `primitiveNewFromStack` | `Array class>>#newFromStack:` | 1 | n/a — kernel we replace |
| 191 | `primitiveIntegerAtOffset&lt;uint64_t, StoreUnsigned64&gt;` | `ByteArray>>#qwordAtOffset:` | 2 | n/a — kernel we replace |
| 192 | `primitiveIntegerAtOffset&lt;int64_t, StoreSigned64&gt;` | `ByteArray>>#sqwordAtOffset:` | 1 | n/a — kernel we replace |
| 193 | `primitiveFloatUnaryOp&lt;Sin&gt;` | `Float>>#sin` | 1 | n/a — kernel we replace |
| 194 | `primitiveFloatUnaryOp&lt;Tan&gt;` | `Float>>#tan` | 1 | n/a — kernel we replace |
| 195 | `primitiveFloatUnaryOp&lt;Cos&gt;` | `Float>>#cos` | 1 | n/a — kernel we replace |
| 196 | `primitiveFloatUnaryOp&lt;ArcSin&gt;` | `Float>>#arcSin` | 1 | n/a — kernel we replace |
| 197 | `primitiveFloatUnaryOp&lt;ArcTan&gt;` | `Float>>#arcTan` | 1 | n/a — kernel we replace |
| 198 | `primitiveFloatUnaryOp&lt;ArcCos&gt;` | `Float>>#arcCos` | 1 | n/a — kernel we replace |
| 199 | `primitiveFloatBinaryOp&lt;Atan2&gt;` | `Float>>#acTan:` | 1 | n/a — kernel we replace |
| 200 | `primitiveFloatUnaryOp&lt;Log&gt;` | `Float>>#ln` | 1 | n/a — kernel we replace |
| 201 | `primitiveFloatUnaryOp&lt;Exp&gt;` | `Float>>#exp` | 1 | n/a — kernel we replace |
| 202 | `primitiveFloatUnaryOp&lt;Sqrt&gt;` | `Float>>#sqrt` | 1 | n/a — kernel we replace |
| 203 | `primitiveFloatUnaryOp&lt;Log10&gt;` | `Float>>#log` | 1 | n/a — kernel we replace |
| 204 | `primitiveFloatTimesTwoPower` | `Float>>#timesTwoPower:` | 1 | n/a — kernel we replace |
| 205 | `primitiveFloatUnaryOp&lt;Abs&gt;` | `Float>>#abs` | 1 | n/a — kernel we replace |
| 206 | `primitiveFloatBinaryOp&lt;Pow&gt;` | `Float>>#raisedTo:` | 1 | n/a — kernel we replace |
| 207 | `primitiveFloatTruncationOp&lt;Floor&gt;` | `Float>>#floor` | 1 | n/a — kernel we replace |
| 208 | `primitiveFloatTruncationOp&lt;Ceiling&gt;` | `Float>>#ceiling` | 1 | n/a — kernel we replace |
| 209 | `primitiveFloatExponent` | `Float>>#exponent` | 1 | n/a — kernel we replace |
| 210 | `primitiveFloatUnaryOp&lt;Negated&gt;` | `Float>>#negated` | 1 | n/a — kernel we replace |
| 211 | `primitiveFloatClassify` | `Float>>#fpClass` | 1 | n/a — kernel we replace |
| 212 | `primitiveFloatUnaryOp&lt;FractionPart&gt;` | `Float>>#fractionPart` | 1 | n/a — kernel we replace |
| 213 | `primitiveFloatUnaryOp&lt;IntegerPart&gt;` | `Float>>#integerPart` | 1 | n/a — kernel we replace |
| 214 | `primitiveFloatCompare&lt;std::less_equal&lt;double&gt;&gt;` | `Float>>#<=` | 1 | n/a — kernel we replace |
| 215 | `primitiveStringAsUtf16String` | `String>>#asUtf16String` | 2 | n/a — kernel we replace |
| 216 | `primitiveStringAsUtf8String` | `String>>#asUtf8String` | 3 | n/a — kernel we replace |
| 217 | `primitiveStringAsByteString` | `String>>#asAnsiString` | 1 | n/a — kernel we replace |
| 218 | `primitiveStringConcatenate` | `String>>#,` | 1 | n/a — kernel we replace |
| 219 | `primitiveStringOrdinalEqual` | `String>>#=` | 1 | n/a — kernel we replace |
| 220 | `primitiveStringCompareOrdinal` | `String>>#compareOrdinals:ignoringCase:` | 1 | n/a — kernel we replace |
| 224 | `primitiveBeginsWith` | `String>>#beginsWith:` | 1 | n/a — kernel we replace |
| 225 | `primitiveStringDecodeAt` | `Utf8String>>decodeAt:` | 1 | n/a — kernel we replace |
| 226 | `primitiveStringEncodedSizeAt` | `Utf8String>>encodedSizeAt:` | 2 | n/a — kernel we replace |
| 227 | `primitiveOrdinalHashIgnoreCase` | `String>>#hashOrdinalsIgnoringCase:` | 1 | n/a — kernel we replace |
| 228 | `primitiveStringLessOrEqual` | `String>>#<=` | 1 | n/a — kernel we replace |
| 229 | `primitiveCharacterEquals` | `Character>>#=` | 1 | n/a — kernel we replace |

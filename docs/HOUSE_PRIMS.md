# House primitives — the substrate's own numbering (DD2)

Extracted mechanically from `st/world`, `st/ext/gamepane` and `st/attic/ide`
on 2026-08-15. **This is the authoritative numbering in this VM.** Dolphin's
numbering is a *different space* that collides on nearly every low number
(house 1 = `SmallInteger>>+`; Dolphin 1 = `^self`), which is why translation
goes through `PRIM_MAP.md` and an unmapped number is a hard error, never a
passthrough.

**128 numbered primitives in use across 141 sites**, range 1–252, with 124 unused numbers below the maximum (the space is grouped by area, not packed).

**96 named `<stprim: name>` primitives** across 97 sites — the newer, name-based form. New work should prefer it: it cannot collide with a number and it reads at the call site.

## Numbered primitives

| # | Class | Selector | Sites | Defined in |
|--:|---|---|--:|---|
| 1 | `SmallInteger` | `+ aNumber` | 1 | `06_smallinteger.mst` |
| 2 | `SmallInteger` | `- aNumber` | 1 | `06_smallinteger.mst` |
| 3 | `SmallInteger` | `* aNumber` | 1 | `06_smallinteger.mst` |
| 4 | `SmallInteger` | `// aNumber` | 1 | `06_smallinteger.mst` |
| 5 | `SmallInteger` | `aNumber isDouble ifTrue:` | 1 | `06_smallinteger.mst` |
| 6 | `SmallInteger` | `bitAnd: aNumber` | 1 | `06_smallinteger.mst` |
| 7 | `SmallInteger` | `bitOr: aNumber` | 1 | `06_smallinteger.mst` |
| 8 | `SmallInteger` | `bitXor: aNumber` | 1 | `06_smallinteger.mst` |
| 9 | `SmallInteger` | `bitShift: aNumber` | 1 | `06_smallinteger.mst` |
| 10 | `SmallInteger` | `` | 1 | `06_smallinteger.mst` |
| 11 | `SmallInteger` | `` | 1 | `06_smallinteger.mst` |
| 12 | `SmallInteger` | `> aNumber` | 1 | `06_smallinteger.mst` |
| 13 | `SmallInteger` | `>= aNumber` | 1 | `06_smallinteger.mst` |
| 14 | `SmallInteger` | `= aNumber` | 1 | `06_smallinteger.mst` |
| 15 | `SmallInteger` | `~= aNumber` | 1 | `06_smallinteger.mst` |
| 20 | `Object` | `identityHash` | 1 | `01_object.mst` |
| 21 | `Object` | `class` | 1 | `01_object.mst` |
| 22 | `Object` | `== anObject` | 1 | `01_object.mst` |
| 23 | `Object` | `basicNew` | 1 | `01_object.mst` |
| 24 | `Object` | `basicNew: n` | 1 | `01_object.mst` |
| 25 | `Object` | `instVarAt: i` | 1 | `01_object.mst` |
| 26 | `Array` | `at: i` | 1 | `10_array.mst` |
| 27 | `Array` | `at: i put: v` | 1 | `10_array.mst` |
| 28 | `LargeInteger` | `size` | 4 | `07_largeinteger.mst` |
| 40 | `LargeInteger` | `byteAt: i` | 3 | `07_largeinteger.mst` |
| 41 | `LargeInteger` | `byteAt: i put: v` | 3 | `07_largeinteger.mst` |
| 43 | `ByteArray` | `replaceFrom: from to: to with: src` | 2 | `11_bytearray.mst` |
| 44 | `LargeInteger` | `hash` | 3 | `07_largeinteger.mst` |
| 45 | `ByteArray` | `compare: other` | 2 | `11_bytearray.mst` |
| 50 | `BlockClosure` | `value` | 1 | `04a_blockclosure.mst` |
| 51 | `BlockClosure` | `value: a1` | 1 | `04a_blockclosure.mst` |
| 52 | `BlockClosure` | `value: a1 value: a2` | 1 | `04a_blockclosure.mst` |
| 53 | `BlockClosure` | `value: a1 value: a2 value: a3` | 1 | `04a_blockclosure.mst` |
| 54 | `BlockClosure` | `valueWithArguments: anArray` | 1 | `04a_blockclosure.mst` |
| 60 | `BlockClosure` | `ensure: aBlock <` | 1 | `04a_blockclosure.mst` |
| 61 | `BlockClosure` | `ifCurtailed: aBlock <` | 1 | `04a_blockclosure.mst` |
| 62 | `ClassMirror` | `ClassMirror class >> primitiveOf: aBehavior selector: aSelector` | 1 | `34_tools.mst` |
| 63 | `ClassMirror` | `ClassMirror class >> methodSends: aBehavior selector: mSel target: tSel` | 1 | `34_tools.mst` |
| 64 | `Object` | `perform: aSymbol withArguments: anArray` | 1 | `01_object.mst` |
| 91 | `TranscriptStream` | `basicPrint: aString` | 1 | `04_transcript.mst` |
| 92 | `SystemDictionary` | `millisecondClock` | 1 | `20_system.mst` |
| 93 | `SystemDictionary` | `gcScavenge` | 1 | `20_system.mst` |
| 94 | `SystemDictionary` | `gcFull` | 1 | `20_system.mst` |
| 95 | `Object` | `error: aString` | 1 | `01_object.mst` |
| 96 | `SystemDictionary` | `quit: code` | 1 | `20_system.mst` |
| 97 | `SystemDictionary` | `gcStats` | 1 | `20_system.mst` |
| 98 | `ClassMirror` | `ClassMirror class >> allClasses` | 1 | `34_tools.mst` |
| 99 | `ClassMirror` | `ClassMirror class >> selectorsOf: aBehavior` | 1 | `34_tools.mst` |
| 100 | `Double` | `+ aNumber` | 1 | `08_double.mst` |
| 101 | `Double` | `- aNumber` | 1 | `08_double.mst` |
| 102 | `Double` | `* aNumber` | 1 | `08_double.mst` |
| 103 | `Double` | `/ aNumber` | 1 | `08_double.mst` |
| 104 | `Double` | `` | 1 | `08_double.mst` |
| 105 | `Double` | `= aNumber` | 1 | `08_double.mst` |
| 106 | `Double` | `sqrt` | 1 | `08_double.mst` |
| 107 | `Double` | `floor` | 1 | `08_double.mst` |
| 108 | `SmallInteger` | `asDouble` | 1 | `06_smallinteger.mst` |
| 109 | `Double` | `printDigits` | 1 | `08_double.mst` |
| 110 | `String` | `asSymbol` | 1 | `12_string.mst` |
| 121 | `Double` | `sin` | 1 | `08_double.mst` |
| 122 | `Double` | `cos` | 1 | `08_double.mst` |
| 123 | `Double` | `tan` | 1 | `08_double.mst` |
| 124 | `Double` | `exp` | 1 | `08_double.mst` |
| 125 | `Double` | `ln` | 1 | `08_double.mst` |
| 126 | `Double` | `atan` | 1 | `08_double.mst` |
| 127 | `Float64x2` | `Float64x2 class >> x: a y: b` | 1 | `38_simd.mst` |
| 128 | `Float64x2` | `Float64x2 class >> splat: v` | 1 | `38_simd.mst` |
| 129 | `Float64x2` | `+ other` | 1 | `38_simd.mst` |
| 130 | `Float64x2` | `- other` | 1 | `38_simd.mst` |
| 131 | `Float64x2` | `* other` | 1 | `38_simd.mst` |
| 132 | `Float64x2` | `/ other` | 1 | `38_simd.mst` |
| 133 | `Float64x2` | `at: i` | 1 | `38_simd.mst` |
| 134 | `Float32x4` | `Float32x4 class >> x: a y: b z: c w: d` | 1 | `38_simd.mst` |
| 135 | `Float32x4` | `Float32x4 class >> splat: v` | 1 | `38_simd.mst` |
| 136 | `Float32x4` | `+ other` | 1 | `38_simd.mst` |
| 137 | `Float32x4` | `- other` | 1 | `38_simd.mst` |
| 138 | `Float32x4` | `* other` | 1 | `38_simd.mst` |
| 139 | `Float32x4` | `/ other` | 1 | `38_simd.mst` |
| 140 | `Float32x4` | `at: i` | 1 | `38_simd.mst` |
| 141 | `FloatArray` | `FloatArray class >> new: n` | 1 | `39_floatarray.mst` |
| 142 | `FloatArray` | `at: i` | 1 | `39_floatarray.mst` |
| 143 | `FloatArray` | `at: i put: aDouble` | 1 | `39_floatarray.mst` |
| 144 | `FloatArray` | `size` | 1 | `39_floatarray.mst` |
| 145 | `FloatArray` | `+@ other` | 1 | `39_floatarray.mst` |
| 146 | `FloatArray` | `sum` | 1 | `39_floatarray.mst` |
| 147 | `FloatArray` | `dot: other` | 1 | `39_floatarray.mst` |
| 148 | `Int32x4` | `Int32x4 class >> x: a y: b z: c w: d` | 1 | `38_simd.mst` |
| 149 | `Int32x4` | `Int32x4 class >> splat: v` | 1 | `38_simd.mst` |
| 150 | `Int32x4` | `+ other` | 1 | `38_simd.mst` |
| 151 | `Int32x4` | `- other` | 1 | `38_simd.mst` |
| 152 | `Int32x4` | `* other` | 1 | `38_simd.mst` |
| 153 | `Int32x4` | `at: i` | 1 | `38_simd.mst` |
| 154 | `FloatArray` | `scale: aNumber` | 1 | `39_floatarray.mst` |
| 155 | `FloatArray` | `max` | 1 | `39_floatarray.mst` |
| 156 | `FloatArray` | `min` | 1 | `39_floatarray.mst` |
| 157 | `ClassMirror` | `ClassMirror class >> instanceVariablesOf: aBehavior` | 1 | `34_tools.mst` |
| 158 | `ClassMirror` | `ClassMirror class >> classVariablesOf: aBehavior` | 1 | `34_tools.mst` |
| 200 | `GamePane` | `clearR: r g: g b: b` | 1 | `43_gamepane.mst` |
| 201 | `GamePane` | `paletteAt: index r: r g: g b: b` | 1 | `43_gamepane.mst` |
| 202 | `GamePane` | `cls: index` | 1 | `43_gamepane.mst` |
| 203 | `GamePane` | `point: x y: y color: c` | 1 | `43_gamepane.mst` |
| 204 | `GamePane` | `line: x0 y: y0 to: x1 y: y1 color: c` | 1 | `43_gamepane.mst` |
| 205 | `GamePane` | `fill: x y: y width: w height: h color: c` | 1 | `43_gamepane.mst` |
| 206 | `GamePane` | `disc: cx y: cy radius: r color: c` | 1 | `43_gamepane.mst` |
| 207 | `GamePane` | `present` | 1 | `43_gamepane.mst` |
| 208 | `GamePane` | `run` | 1 | `43_gamepane.mst` |
| 209 | `GamePane` | `stop` | 1 | `43_gamepane.mst` |
| 210 | `GamePane` | `primDefineSprite: id rows: hexRows` | 1 | `43_gamepane.mst` |
| 211 | `GamePane` | `primSpriteColor: id index: index r: r g: g b: b` | 1 | `43_gamepane.mst` |
| 212 | `GamePane` | `primMoveSprite: id x: x y: y` | 1 | `43_gamepane.mst` |
| 213 | `Sound` | `primPlay: n` | 1 | `43_gamepane.mst` |
| 214 | `Tune` | `primPlayTune: s` | 1 | `43_gamepane.mst` |
| 215 | `GamePane` | `blit: aByteArray` | 1 | `43_gamepane.mst` |
| 220 | `Worker` | `Worker class >> primSpawn: initString` | 1 | `47_worker.mst` |
| 221 | `Worker` | `Worker class >> primSend: i corr: c bytes: b` | 1 | `47_worker.mst` |
| 222 | `Worker` | `Worker class >> primPoll` | 1 | `47_worker.mst` |
| 223 | `Worker` | `Worker class >> primAwaitInbox: ms` | 1 | `47_worker.mst` |
| 224 | `Worker` | `Worker class >> primTerminate: i` | 1 | `47_worker.mst` |
| 225 | `Worker` | `Worker class >> primAlive: i` | 1 | `47_worker.mst` |
| 226 | `Worker` | `Worker class >> primSelfId` | 1 | `47_worker.mst` |
| 227 | `Worker` | `Worker class >> pickle: x` | 1 | `47_worker.mst` |
| 228 | `Worker` | `Worker class >> unpickle: b` | 1 | `47_worker.mst` |
| 246 | `Object` | `respondsTo: aSymbol` | 2 | `59_reflection.mst` |
| 247 | `Object` | `shallowCopy` | 1 | `59_reflection.mst` |
| 248 | `BlockClosure` | `numArgs` | 2 | `59_reflection.mst` |
| 250 | `Worker` | `Worker class >> primEvalDoit: aSource` | 1 | `47_worker.mst` |
| 251 | `Object` | `halt` | 1 | `01_object.mst` |
| 252 | `SystemDictionary` | `microsecondClock` | 1 | `20_system.mst` |

## Named stprims

| Name | Class | Selector | Defined in |
|---|---|---|---|
| `stAllClasses` | `None` | `ClassMirror class >> allClasses` | `76_reflection.mst` |
| `stAppUiBox` | `AppUI` | `box: id title: t frame: f` | `81_appui.mst` |
| `stAppUiButton` | `AppUI` | `button: id title: t frame: f onClick: aBlock` | `81_appui.mst` |
| `stAppUiCanvas` | `AppUI` | `canvas: id frame: f bg: rgb onClick: aBlock` | `81_appui.mst` |
| `stAppUiCheckbox` | `AppUI` | `checkbox: id label: t frame: f value: aBool onToggle: aBlock` | `81_appui.mst` |
| `stAppUiClear` | `AppUI` | `clear` | `81_appui.mst` |
| `stAppUiDraw` | `AppUI` | `draw: id ops: anArray` | `81_appui.mst` |
| `stAppUiField` | `AppUI` | `field: id text: t frame: f onText: aBlock onEnter: eBlock` | `81_appui.mst` |
| `stAppUiFocus` | `AppUI` | `focus: id` | `81_appui.mst` |
| `stAppUiHeight` | `AppUI` | `height` | `81_appui.mst` |
| `stAppUiInto` | `AppUI` | `into: id` | `81_appui.mst` |
| `stAppUiLabel` | `AppUI` | `label: id text: t frame: f align: a` | `81_appui.mst` |
| `stAppUiList` | `AppUI` | `list: id items: anArray frame: f onSelect: aBlock` | `81_appui.mst` |
| `stAppUiPane` | `AppUI` | `pane` | `81_appui.mst` |
| `stAppUiPopup` | `AppUI` | `popup: id items: anArray frame: f selected: s onSelect: aBlock` | `81_appui.mst` |
| `stAppUiProgress` | `AppUI` | `progress: id frame: f min: lo max: hi value: v` | `81_appui.mst` |
| `stAppUiRemove` | `AppUI` | `remove: id` | `81_appui.mst` |
| `stAppUiScroll` | `AppUI` | `scroll: id frame: f width: w height: h` | `81_appui.mst` |
| `stAppUiSecure` | `AppUI` | `secure: id text: t frame: f onText: aBlock onEnter: eBlock` | `81_appui.mst` |
| `stAppUiSet` | `AppUI` | `basicSet: id key: k value: v` | `81_appui.mst` |
| `stAppUiSlider` | `AppUI` | `slider: id frame: f min: lo max: hi value: v onSlide: aBlock` | `81_appui.mst` |
| `stAppUiTab` | `AppUI` | `tab: id index: n` | `81_appui.mst` |
| `stAppUiTabs` | `AppUI` | `tabs: id items: anArray frame: f` | `81_appui.mst` |
| `stAppUiTitle` | `AppUI` | `title: aString` | `81_appui.mst` |
| `stAppUiWidth` | `AppUI` | `width` | `81_appui.mst` |
| `stBlockNumArgs` | `None` | `BlockClosure >> numArgs` | `76_reflection.mst` |
| `stClassNameOf` | `None` | `Behavior >> name` | `76_reflection.mst` |
| `stClassNamed` | `Worker` | `Worker class >> classNamed: aSymbol` | `47_worker.mst` |
| `stClassVarNamesOf` | `None` | `ClassMirror class >> classVariablesOf: aBehavior` | `76_reflection.mst` |
| `stGpActive` | `None` | `GamePane >> activeBuffer: slot` | `84_gamepane_buffers.mst` |
| `stGpAddFrame` | `None` | `GamePane >> primAddFrame: id rows: hexRows` | `80_gamepane_wiring.mst` |
| `stGpBlit` | `None` | `GamePane >> blit: aByteArray` | `80_gamepane_wiring.mst` |
| `stGpBlitSlots` | `None` | `GamePane >> blitMode: mode src: src dst: dst sx: sx sy: sy dx: dx dy: dy w: w h: h value: v` | `84_gamepane_buffers.mst` |
| `stGpClearBlocks` | `None` | `GamePane class >> clearBlocks` | `80_gamepane_wiring.mst` |
| `stGpClearRGB` | `None` | `GamePane >> clearR: r g: g b: b` | `80_gamepane_wiring.mst` |
| `stGpCls` | `None` | `GamePane >> cls: index` | `80_gamepane_wiring.mst` |
| `stGpDefineSprite` | `None` | `GamePane >> primDefineSprite: id rows: hexRows` | `80_gamepane_wiring.mst` |
| `stGpDirectBlit` | `None` | `GamePane >> directBlit: aByteArray` | `83_gamepane_direct.mst` |
| `stGpDirectPal` | `None` | `GamePane >> directPal: index r: r g: g b: b` | `83_gamepane_direct.mst` |
| `stGpDisc` | `None` | `GamePane >> disc: cx y: cy radius: r color: c` | `80_gamepane_wiring.mst` |
| `stGpEffect` | `None` | `Sound class >> effect: params slot: n` | `80_gamepane_wiring.mst` |
| `stGpFill` | `None` | `GamePane >> fill: x y: y width: w height: h color: c` | `80_gamepane_wiring.mst` |
| `stGpHide` | `None` | `GamePane >> primHide: id` | `80_gamepane_wiring.mst` |
| `stGpLine` | `None` | `GamePane >> line: x0 y: y0 to: x1 y: y1 color: c` | `80_gamepane_wiring.mst` |
| `stGpLinePal` | `None` | `GamePane >> linePaletteAt: line index: i r: r g: g b: b` | `80_gamepane_wiring.mst` |
| `stGpLoad` | `None` | `GamePane >> loadBuffer: slot bytes: aByteArray` | `84_gamepane_buffers.mst` |
| `stGpMoveSprite` | `None` | `GamePane >> primMoveSprite: id x: x y: y` | `80_gamepane_wiring.mst` |
| `stGpOnReset` | `None` | `GamePane >> onReset: aBlock` | `80_gamepane_wiring.mst` |
| `stGpOnStep` | `None` | `GamePane >> onStep: aBlock` | `80_gamepane_wiring.mst` |
| `stGpPal` | `None` | `GamePane >> paletteAt: index r: r g: g b: b` | `80_gamepane_wiring.mst` |
| `stGpPlaceFrame` | `None` | `GamePane >> primPlace: id x: x y: y frame: f` | `80_gamepane_wiring.mst` |
| `stGpPlay` | `None` | `Sound >> primPlay: n` | `80_gamepane_wiring.mst` |
| `stGpPlaySlot` | `None` | `Sound class >> playSlot: n` | `80_gamepane_wiring.mst` |
| `stGpPlayTune` | `None` | `Tune >> primPlayTune: s` | `80_gamepane_wiring.mst` |
| `stGpPresent` | `None` | `GamePane >> present` | `80_gamepane_wiring.mst` |
| `stGpPset` | `None` | `GamePane >> point: x y: y color: c` | `80_gamepane_wiring.mst` |
| `stGpResetBlock` | `None` | `GamePane class >> resetBlock` | `80_gamepane_wiring.mst` |
| `stGpRun` | `None` | `GamePane >> run` | `80_gamepane_wiring.mst` |
| `stGpScroll` | `None` | `GamePane >> scrollTo: x y: y` | `84_gamepane_buffers.mst` |
| `stGpShader` | `None` | `GamePane >> shader: mslSource` | `80_gamepane_wiring.mst` |
| `stGpShaderParam` | `None` | `GamePane >> shaderParam: index value: aNumber` | `80_gamepane_wiring.mst` |
| `stGpSpriteColor` | `None` | `GamePane >> primSpriteColor: id index: index r: r g: g b: b` | `80_gamepane_wiring.mst` |
| `stGpStepBlock` | `None` | `GamePane class >> stepBlock` | `80_gamepane_wiring.mst` |
| `stGpStop` | `None` | `GamePane >> stop` | `80_gamepane_wiring.mst` |
| `stGpSwap` | `None` | `GamePane >> swapBuffers` | `84_gamepane_buffers.mst` |
| `stGpText` | `None` | `GamePane >> text: aString x: x y: y r: r g: g b: b scale: k` | `80_gamepane_wiring.mst` |
| `stGpTextClear` | `None` | `GamePane >> textClear` | `80_gamepane_wiring.mst` |
| `stHostAcceptClass` | `STHostService` | `acceptEditorClass: text` | `63_cocoaui_stub.mst` |
| `stHostBrowseRecords` | `STHostService` | `browseRecords` | `63_cocoaui_stub.mst` |
| `stHostClassSource` | `STHostService` | `classSourceFor: cls` | `63_cocoaui_stub.mst` |
| `stHostComment` | `STHostService` | `commentFor: cls` | `63_cocoaui_stub.mst` |
| `stHostMethodSource` | `STHostService` | `sourceForClass: cls side: side selector: sel` | `63_cocoaui_stub.mst` |
| `stHostNewClass` | `STHostService` | `newClassFrom: text` | `63_cocoaui_stub.mst` |
| `stHostPackageTree` | `STHostService` | `packageTree` | `63_cocoaui_stub.mst` |
| `stHostRemoveClass` | `STHostService` | `removeClassNamed: cls` | `63_cocoaui_stub.mst` |
| `stHostRemoveMethod` | `STHostService` | `removeMethodFor: cls side: side selector: sel` | `63_cocoaui_stub.mst` |
| `stHostSaveMethod` | `STHostService` | `saveMethodFor: cls side: side source: text` | `63_cocoaui_stub.mst` |
| `stHostSetComment` | `STHostService` | `setCommentFor: cls comment: text` | `63_cocoaui_stub.mst` |
| `stHostStoreClass` | `STHostService` | `storeEditorClass: text` | `63_cocoaui_stub.mst` |
| `stInstVarAtPut` | `None` | `Object >> instVarAt: i put: v` | `76_reflection.mst` |
| `stInstVarNamesOf` | `None` | `ClassMirror class >> instanceVariablesOf: aBehavior` | `76_reflection.mst` |
| `stIntByteAt` | `None` | `LargeInteger >> byteAt: i` | `07a_largeint_bytes.mst` |
| `stJoinRows` | `STCocoa` | `STCocoa class >> joinRows: anArray` | `49_cocoa.mst` |
| `stObjcActionTarget` | `STCocoa` | `STCocoa class >> actionTargetTicket: t` | `49_cocoa.mst` |
| `stObjcClassNamed` | `STCocoa` | `STCocoa class >> classNamed: aName` | `49_cocoa.mst` |
| `stObjcIsRef` | `STCocoa` | `STCocoa class >> isRef: x` | `49_cocoa.mst` |
| `stObjcPoolPop` | `STCocoa` | `STCocoa class >> poolPop: p` | `49_cocoa.mst` |
| `stObjcPoolPush` | `STCocoa` | `STCocoa class >> poolPush` | `49_cocoa.mst` |
| `stObjcSend` | `STCocoa` | `STCocoa class >> send: h sel: s args: a` | `49_cocoa.mst` |
| `stObjcSendMain` | `STCocoa` | `STCocoa class >> sendMain: h sel: s args: a` | `49_cocoa.mst` |
| `stObjcTableSource` | `STCocoa` | `STCocoa class >> tableSourceTicket: t` | `49_cocoa.mst` |
| `stObjcUTF8` | `STCocoa` | `STCocoa class >> utf8: x` | `49_cocoa.mst` |
| `stRaisedTo` | `None` | `Number >> raisedTo: aNumber` | `82_number_math.mst` |
| `stRespondsTo` | `None` | `Object >> respondsTo: aSymbol` | `76_reflection.mst` |
| `stSelectorsOf` | `None` | `ClassMirror class >> selectorsOf: aBehavior` | `76_reflection.mst` |
| `stSuperclassOf` | `None` | `Behavior >> superclass` | `76_reflection.mst` |

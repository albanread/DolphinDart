# dolphin2mst run report

- inputs: **177** source files (`.cls` + `.pax`)
- shared-pool constants available: **7908** from **216** pools
- loose methods adopted from `.pax`: **16**
- parsed: **177**  (unbalanced/skipped: 0)
- emitted: **180** `.mst`
- methods: **6076**
- refusals: **296**

## Refusals by rewrite class

| Rewrite | Count |
|---|--:|
| `hashhash` | 156 |
| `cascade` | 72 |
| `pragma` | 35 |
| `orphan-loose-methods` | 30 |
| `qq` | 3 |

## Per class

| Class | Methods | Refusals |
|---|--:|--:|
| `ARGB` | 21 | 0 |
| `AbstractFont` | 48 | 0 |
| `AbstractPen` | 14 | 0 |
| `AbstractRGB` | 4 | 0 |
| `AbstractToTextConverter` | 6 | 0 |
| `AcceleratorTable` | 25 | 0 |
| `BorderLayout` | 26 | 0 |
| `Brush` | 29 | 1 |
| `ButtonInteractor` | 19 | 0 |
| `CCITEM` | 32 | 0 |
| `Canvas` | 126 | 5 |
| `CapturingInteractor` | 38 | 1 |
| `CardContainer` | 48 | 3 |
| `CardLayout` | 25 | 1 |
| `Clipboard` | 42 | 1 |
| `Color` | 268 | 9 |
| `ColorDefault` | 11 | 1 |
| `ColorEvent` | 2 | 0 |
| `ColorNone` | 11 | 0 |
| `ColorRef` | 6 | 0 |
| `CommandButton` | 16 | 1 |
| `CommandDescription` | 46 | 0 |
| `CommandMenuItem` | 45 | 0 |
| `CommandPolicy` | 21 | 0 |
| `CommandQuery` | 39 | 2 |
| `CommonDialog` | 30 | 1 |
| `ContainerView` | 37 | 2 |
| `ControlView` | 61 | 2 |
| `CreateDialog` | 3 | 0 |
| `CreateInDpiAwarenessContext` | 5 | 0 |
| `CreateWindow` | 11 | 0 |
| `CreateWindowApiCall` | 10 | 0 |
| `CreateWindowFunction` | 12 | 0 |
| `Cursor` | 47 | 1 |
| `DelegatingCommandPolicy` | 1 | 0 |
| `Dialog` | 43 | 2 |
| `DialogView` | 57 | 5 |
| `DisplayMonitor` | 49 | 3 |
| `DividerMenuItem` | 26 | 1 |
| `DpiAwareness` | 27 | 0 |
| `DpiChangedEvent` | 5 | 0 |
| `DraggableViewInteractor` | 3 | 0 |
| `Event` | 5 | 2 |
| `FileDialog` | 40 | 4 |
| `FileOpenDialog` | 7 | 1 |
| `FlowLayout` | 17 | 1 |
| `Font` | 26 | 0 |
| `GraphicsTool` | 32 | 2 |
| `Icon` | 62 | 2 |
| `IconFromSystemInitializer` | 12 | 0 |
| `IconImageManager` | 10 | 0 |
| `IconicListAbstract` | 112 | 13 |
| `IconicListUpdateMode` | 9 | 0 |
| `Image` | 59 | 5 |
| `ImageFromHandleInitializer` | 7 | 0 |
| `ImageFromResourceInitializer` | 16 | 0 |
| `ImageFromStringResourceInitializer` | 3 | 1 |
| `ImageInitializer` | 19 | 0 |
| `ImageList` | 39 | 3 |
| `ImageManager` | 28 | 1 |
| `IntegerToText` | 1 | 0 |
| `Interactor` | 34 | 1 |
| `KeyEvent` | 9 | 0 |
| `LVCOLUMNW (reopen)` | 35 | 0 |
| `LVITEMW (reopen)` | 43 | 0 |
| `LayoutContext` | 16 | 0 |
| `LayoutManager` | 11 | 0 |
| `LayoutPlacement` | 11 | 0 |
| `ListControlView` | 81 | 1 |
| `ListModel` | 52 | 1 |
| `ListView` | 274 | 12 |
| `ListViewColumn` | 59 | 5 |
| `ListViewStaticUpdateMode` | 11 | 1 |
| `ListViewUpdateMode` | 8 | 0 |
| `ListViewVirtualUpdateMode` | 11 | 0 |
| `LookupTable (loose)` | 1 | 0 |
| `MONITORINFOEXW (reopen)` | 8 | 0 |
| `Menu` | 101 | 1 |
| `MenuBar` | 7 | 1 |
| `MenuItem` | 35 | 0 |
| `MessageSend` | 7 | 0 |
| `MessageSendAbstract` | 23 | 1 |
| `MessageSequence` | 14 | 0 |
| `MessageSequenceAbstract` | 14 | 0 |
| `Model` | 11 | 1 |
| `MouseEvent` | 13 | 1 |
| `MouseTracker` | 38 | 3 |
| `MouseWheelEvent` | 2 | 0 |
| `MultilineTextEdit` | 49 | 9 |
| `NeverSearchPolicy` | 2 | 0 |
| `NullConverter` | 2 | 0 |
| `NumberToText` | 2 | 0 |
| `Object (loose)` | 8 | 1 |
| `OrderedCollection (loose)` | 1 | 0 |
| `PaintEvent` | 6 | 0 |
| `Pen` | 33 | 0 |
| `PointEvent` | 5 | 0 |
| `PositionEvent` | 23 | 0 |
| `Presenter` | 152 | 4 |
| `Prompter` | 26 | 0 |
| `PushButton` | 41 | 3 |
| `RGB` | 11 | 0 |
| `RadioButton` | 1 | 0 |
| `Rectangle` | 98 | 1 |
| `ReferenceView` | 17 | 2 |
| `ResourceIdentifier` | 46 | 1 |
| `ResourceLibrary` | 21 | 0 |
| `RestrictedClassLocator` | 10 | 0 |
| `STBClassProxy` | 11 | 0 |
| `STBCollectionProxy` | 6 | 0 |
| `STBError` | 1 | 0 |
| `STBIdentityDictionaryProxy` | 3 | 0 |
| `STBInFiler` | 18 | 7 |
| `STBMetaclassProxy` | 2 | 0 |
| `STBSingletonProxy` | 5 | 1 |
| `STBSortedCollectionProxy` | 9 | 1 |
| `STBStaticVariableProxy` | 4 | 0 |
| `STBViewProxy` | 32 | 3 |
| `STLInFiler` | 22 | 0 |
| `STxFiler` | 24 | 0 |
| `STxInFiler` | 53 | 0 |
| `STxProxy` | 2 | 0 |
| `ScrollEvent` | 16 | 1 |
| `SelectionChangeEvent` | 12 | 0 |
| `SelectionChangingEvent` | 5 | 0 |
| `Set (loose)` | 1 | 0 |
| `Shell` | 39 | 1 |
| `ShellView` | 156 | 11 |
| `SingletonSearchPolicy` | 5 | 0 |
| `SlideyInneyOuteyThing` | 66 | 3 |
| `SlidingCardTray` | 47 | 3 |
| `Splitter` | 27 | 3 |
| `StaticControlView` | 5 | 0 |
| `StaticRectangle` | 7 | 0 |
| `StaticText` | 19 | 2 |
| `StaticView` | 10 | 1 |
| `StatusBar` | 46 | 4 |
| `StatusBarItem` | 21 | 0 |
| `StatusBarNullItem` | 1 | 0 |
| `StockBrush` | 7 | 0 |
| `StockFont` | 14 | 0 |
| `StockPen` | 8 | 0 |
| `String (loose)` | 5 | 0 |
| `SystemFont` | 5 | 0 |
| `SystemMetrics` | 77 | 2 |
| `TVITEMEXW (reopen)` | 9 | 0 |
| `TVITEMW (reopen)` | 38 | 1 |
| `TabView` | 78 | 3 |
| `TabViewXP` | 23 | 2 |
| `TextEdit` | 179 | 20 |
| `TextPresenter` | 20 | 1 |
| `ThemeColor` | 13 | 0 |
| `Toolbar` | 164 | 14 |
| `ToolbarButton` | 91 | 6 |
| `ToolbarIconButton` | 10 | 0 |
| `ToolbarItem` | 21 | 0 |
| `ToolbarSeparator` | 9 | 0 |
| `ToolbarTextButton` | 9 | 0 |
| `TreeModel` | 31 | 1 |
| `TreeModelAbstract` | 57 | 7 |
| `TreeNode` | 14 | 0 |
| `TreeView` | 142 | 10 |
| `TreeViewDynamicUpdateMode` | 2 | 0 |
| `TreeViewLazyUpdateMode` | 3 | 0 |
| `TreeViewStaticUpdateMode` | 5 | 2 |
| `TreeViewUpdateMode` | 2 | 0 |
| `TreeViewVirtualUpdateMode` | 3 | 0 |
| `TypeConverter` | 13 | 1 |
| `UserLibrary (loose)` | 177 | 0 |
| `ValueAdaptor` | 6 | 2 |
| `ValueAspectAdaptor` | 17 | 1 |
| `ValueBuffer` | 17 | 1 |
| `ValueConvertingControlView` | 19 | 2 |
| `ValueDialog` | 10 | 1 |
| `ValueHolder` | 4 | 2 |
| `ValueModel` | 17 | 2 |
| `ValuePresenter` | 8 | 1 |
| `View` | 667 | 16 |
| `VirtualColor` | 10 | 0 |
| `WindowsEvent` | 15 | 0 |

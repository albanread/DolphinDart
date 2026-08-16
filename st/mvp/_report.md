# dolphin2mst run report

- inputs: **46** source files (`.cls` + `.pax`)
- shared-pool constants available: **6522** from **173** pools
- loose methods adopted from `.pax`: **1**
- parsed: **46**  (unbalanced/skipped: 0)
- emitted: **47** `.mst`
- methods: **2493**
- refusals: **114**

## Refusals by rewrite class

| Rewrite | Count |
|---|--:|
| `hashhash` | 54 |
| `cascade` | 22 |
| `binding-literal` | 14 |
| `pragma` | 14 |
| `orphan-loose-methods` | 10 |

## Per class

| Class | Methods | Refusals |
|---|--:|--:|
| `ARGB` | 21 | 0 |
| `AbstractRGB` | 4 | 0 |
| `AbstractToTextConverter` | 6 | 0 |
| `BorderLayout` | 26 | 0 |
| `Color` | 268 | 9 |
| `ColorDefault` | 11 | 1 |
| `ColorNone` | 11 | 0 |
| `ColorRef` | 6 | 0 |
| `CommandDescription` | 46 | 0 |
| `CommandPolicy` | 21 | 0 |
| `CommandQuery` | 39 | 2 |
| `ContainerView` | 37 | 3 |
| `ControlView` | 61 | 3 |
| `CreateWindow` | 11 | 0 |
| `CreateWindowApiCall` | 10 | 0 |
| `CreateWindowFunction` | 12 | 0 |
| `DelegatingCommandPolicy` | 1 | 0 |
| `GraphicsTool` | 32 | 2 |
| `IntegerToText` | 1 | 0 |
| `LayoutContext` | 16 | 0 |
| `LayoutManager` | 11 | 0 |
| `LayoutPlacement` | 11 | 0 |
| `Menu` | 101 | 2 |
| `MenuBar` | 7 | 1 |
| `MenuItem` | 35 | 0 |
| `Model` | 9 | 1 |
| `NullConverter` | 2 | 0 |
| `NumberToText` | 2 | 0 |
| `Object (loose)` | 7 | 1 |
| `Presenter` | 152 | 6 |
| `Rectangle` | 98 | 2 |
| `Shell` | 39 | 2 |
| `ShellView` | 156 | 11 |
| `String (loose)` | 2 | 0 |
| `SystemMetrics` | 77 | 2 |
| `TextEdit` | 179 | 21 |
| `TextPresenter` | 20 | 5 |
| `TypeConverter` | 13 | 1 |
| `UserLibrary (loose)` | 177 | 0 |
| `ValueAdaptor` | 6 | 2 |
| `ValueAspectAdaptor` | 17 | 1 |
| `ValueBuffer` | 17 | 1 |
| `ValueConvertingControlView` | 19 | 2 |
| `ValueHolder` | 4 | 2 |
| `ValueModel` | 17 | 2 |
| `ValuePresenter` | 8 | 1 |
| `View` | 667 | 18 |

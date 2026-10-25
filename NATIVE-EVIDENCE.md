# SC4Speeding 0.58

Replace SC4Speeding.dll only. The main DLL has logging and Ctrl+Shift+F10
compiled out. It still reads its INI and starts normal native monthly scenes.
There are no GetAsyncKeyState, CreateFileA, WriteFile or CloseHandle imports
in the release DLL. Debug builds retain logging and the test/restart hotkey.

The optional debug build is in debug/SC4Speeding.dll.disabled. With the game
closed, copy it OVER the main DLL and rename that copy SC4Speeding.dll to use
it. Never enable both DLLs together. Plugins subfolders are scanned by the game,
so the bundled debug file intentionally has an inactive extension.

build.sh builds release and debug from the same source using
SC4_SPEEDING_DEBUG=0/1. Release tests verify no logs at startup, during a full
monthly scene or on shutdown, and no effect from holding the old shortcut.
Debug tests cover shortcut restart, overlapping monthly scenes, pause, UI and
native population-cap bypass. Both variants pass missing-manager cleanup and
recovery regression tests. No live-game test. All DAT files are unchanged.

## 0.48: explicit filter arrays and loaded-mask guard

The DAT writer used len(values)>1 for the array flag, so single-item filter
properties were scalar. Native crime loader5ffb40 calls variant GetCount slot4
and RefUint8 slot95, then copies that many bytes. The native scalar Uint8 setter
9157d9 writes type2 at+e and value at+4, leaving the count at+10 zero; GetCount
40ce60 returns that count. The mask builder69fcf0 sets an empty vector mask to0
(despite first assigning FFFFFFFF, it immediately overwrites that with0).
Thus scalar wealth/condition filters can exclude every lot from selection.

Writer now treats a tuple as an explicit array even with one item. Emit wealth
array[1], purpose array[1,2], condition array[0]. Native69fcf0 yields1,3,FFFFFFFF.
verify_native_crime_filters.py runs original9157d9/40ce60/69fcf0 and checks array
flags/counts in the shipped DBPF. This supplements the earlier weighted-loop
test, which used a prefiltered list and could not detect bad filter encoding.
No full exemplar-loader/monthly-simulator execution is claimed.

At bind, reject a matching category if any native mask18/1c/20/24 is zero,
logging a clear old-DAT warning. Log selection weight transitions without
changing stock category records. Header/schema and black minimap FSH unchanged.

## 0.47: native weighted crime notifications replace timer

Crime exemplar112: RelativeOccurrance aa12fcb8 Float32=4; WealthFilter
 aa12fcb3 Uint8=1; ZonePurposeFilter aa12fcb4 Uint8 array[1,2]. Everything else
including the authoritative opaque-black minimap FSH is preserved.

Native6a1a40 filters candidate category records by four masks at18/1c/20/24,
sums their weights at38, draws within that sum, and subtracts each candidate's
weight in6a1b43..6a1b9b. verify_native_crime_weights.py runs that original
loop with a controlled RNG and prefiltered category list; the full simulator,
lot eligibility and police suppression are not run by that test.

Native6a1d3e sets message type0a159d95,6a1d4d pushes selected category ID to
standard message SetData1 slot11;6a1d53..6a1d5a assigns selected lot via
SetIGZUnknown slot33;6a1db3..6a1db6 posts through its message server. The
existing native police listener6e2990 reads GetIGZUnknown slot32, QIs lot
IIDe818fced and uses its cell bounds. Our subscribed listener reads GetData1
slot9, ignores other IDs, QIs the same lot and calls GetCenter slot15. Native
6bf560 writes3 floats and returns void (the SDK bool annotation is inaccurate).
The emulator executes that native center getter for queued lot positions.

Queue64 copied centers and process at most one visual at a time in OnTick;
use an anchor search within48m of selected lot, then retain actual adjacency
and full corridor checks. No wall-clock automatic scene countdown exists.
Manual hotkey remains a separate test trigger. Drop requests on ordinance
gates/detach; no borrowed lot/message pointers retained. Existing instance
incident-array hook removes only native112 records and appends the active
scene's112 marker, copying unrelated records byte-for-byte.

Runtime selection gating changes only our unique category's heap weight38
between4 and0; restore4 on detach/context loss. A matching registered weighted
DAT is required at bind. Stock categories, their weights, monthly budget and
native random generator are not modified. Native message delivery and visuals
remain unverified in the running game.

## 0.46: final braking tangent and road-surface sampling

Regression: previous0.43 DLL steering-tail-west with100ms ticks records
position(64,.05,98), heading world+Z at15900ms, then same position heading-X
at16000ms. Normalized tangent length below.001 fell back to world+Z. Use the
original heading once u>=.7, the exact point lateral displacement derivative
has become zero; no near-zero tangent normalization during final braking.

Original EXE network tables aa8080/aaad40 expose GetAltitude at virtual56,
6197f0. It subtracts world origin X/Z at+9c/+a4 and interpolates two triangles
from stored vertex heights +a0/+b8/+d0/+e8 using reciprocal cell width b0b384.
The caller receives x87 float; parameters are world X/Z, not normalized UVs.
verify_native_road_height.py executes that original function on three planes
at corners and interior points with nonzero tile origins, with reciprocal
cell width initialized as the game would do. Terrain/network services and
initialization are otherwise mocked.

surface_height queries a road-filtered occupant, QIs network, reads native
surface altitude, and releases that QI. Otherwise it samples terrain. All
car poses use four contacts +/-1.5m forward and+/-.7m lateral to fit a plane.
Transform basis remains normal-aligned/orthonormal with native slot75 setter.
Height is max(mean contacts,center surface)+existing surface offset, preventing
center sinking at convex crests. No native GetNormal call is guessed.
Updated fixtures cover differing terrain/road surfaces and changing slopes;
actual renderer and third-party road-piece behavior remain unverified.

## Example-based ordinance rebuild (0.24)

Uploaded ordinal DAT is byte-identical to the generated0.22/0.23 resource.
sc4@0.2.24 independently parses all its original properties, including Sint64
costs and inline strings. This does not prove the game's native exemplar
factory accepts it, or establish the reason the host found zero exemplars.

The tutorial recommends copying SpaceExplorationProgramOrdinance.dat and
changing exemplar/LTEXT IDs. The new builder imports that actual example
from v1.0.1, filters to the eight common properties, rewrites all user-visible
text references, costs and ID, and serializes with sc4@0.2.24. Costs retain the
example's Sint32 encoding. Exemplar group remains2ecef8bb, instancef5ee0200;
LTEXTs use group18ed0359 and new instancesf5ee0201/f5ee0202. Name Key6a416b21
and Description Keyca416b2a resolve to exact UTF-16 strings. Population
conditions, monthly factors and all unrelated example effects are removed.

The reader/writer supplies QFS streams and a matching DIR record. Afterward
zero padding extends the archive to1KiB without changing index values. This
is a compatibility precaution, not a proven minimum-size requirement.
Python/QFS decoding verifies each property and LTEXT separately, then the
native-budget emulation runs on the decoded costs. check_ordinance_archive.mjs
performs an additional SC4 library read. The gameplay DLL remains0.23 unchanged.
No live loading verification has been performed; do not describe the host as
confirmed to find the new file until a game run supplies that evidence.

## Startup ordinance availability (0.23)

Host v1.0.1 CustomOrdinance constructor starts available=false. Init enables
and loads exemplar properties but does not set available. Native monthly
80d950 updates availability after CheckConditions. Version0.22 only read the
checkbox, leaving a registered new ordinance unavailable until that update.

The new startup check uses GetOrdinanceByID20, IsOrdinanceAvailable7 and
SetOrdinanceAvailable10. It retries absent registration and performs at most
one successful availability transition per city attachment. Already available
entries do not receive a Set call. Only f5ee0200 is addressed. No registration
is fabricated when the host/file is missing; the log reports that condition
after five seconds and the check continues waiting. The on/off state is not
set by the plugin. The native availability setter manages its own UI notices.

Fixtures verify initial-unavailable and delayed-registration transitions,
already checked state preservation, missing-registration diagnostics and
existing animation regressions. Resource loading at the user's installation
is still unknown until its host log is available.

## Speed Traps custom ordinance and host integration (0.22)

Uses Null 45 / Nicholas Hayes' Custom Ordinance Exemplar Host v1.0.1 as an
external dependency; its DLL is not patched or redistributed in this archive.
Source: https://github.com/0xC0000054/sc4-custom-ordinance-host/tree/v1.0.1
Docs: https://github.com/0xC0000054/sc4-custom-ordinance-host/blob/main/docs/Ordinance_Exemplar_Properties.md

Native 80e4a0 enumerates exemplar resources and 80e430 filters ExemplarType14.
80e360 then asks COM to create the exemplar instance ID with simple-ordinance
interface8bd4fc74. A new exemplar alone does not supply that COM class. The host's
EnumClassObjects/GetClassObject supply registration by scanning Documents/
SimCity 4/Plugins/140-ordinances. Its CustomOrdinance reads inline name/description
properties32/34, signed64 costs37/38/39 and Boolean Income Ordinance3c. Our new
6534284a-a9c2c209-f5ee0200 contains no availability conditions, no general crime
effect and no population multipliers. Monthly constant income is -60, switching
fees are zero and Income Ordinance is false. Stock resource IDs are unchanged.

cISC4OrdinanceSimulator native vtable is abeac0 (abeab0 is a secondary interface).
Slot8 IsOrdinanceOn=80d470, slot20 GetOrdinanceByID=80e040 and slot22 expense
getter=80d500. The speeding DLL reads only IsOrdinanceOn(f5ee0200); it does not
change availability, registration, checkboxes, budget totals or shared vtables.
Active sequences are cancelled and markers suppressed while checked. This gate
precedes automatic/hotkey triggers and does not alter other crime generation.

verify_native_ordinance.py independently parses the delivered host DAT and checks
its ID, description and exact costs. A synthetic native simple-ordinance object
uses those values while original EXE code performs ID lookup, IsOn, SetOn,
GetCurrentMonthlyIncome, Simulate and monthly aggregation80d950. Only the final
budget-change notification allocation/broadcast is skipped after totals commit.
It verifies expense60 on /0 off over repeated months and one-million population.
This proves the native budget convention and query ABI; it does not execute the
host DLL itself or verify live save/load. Compiled-DLL fixtures mock the host's
service state to test scene suppression, cancellation, marker/lights cleanup,
manual requests and repeal without any ordinance-state writes.

## Modal pause and game animation speed (0.21)

The public cIGZWin::GetWindowManager (slot6) and cIGZWinMgr::IsModal
(slot42) provide the modal UI gate. Reference SDK headers from
https://github.com/nsgomez/gzcom-dll/tree/master/gzcom-dll/include
are included as cIGZWin.h and cIGZWinMgr.h. The native window getter
9d7e63 reads the borrowed window-manager pointer at +4. No UI state,
simulator state, speed setting or shared vtable is modified by this check.

OnTick samples wall time even while blocked, returns before sequence updates,
and skips the first resumed tick to discard any remaining blocked interval.
This is separate from IsHiddenPaused, retaining 0.17's hidden-pause behavior.

cSC4Simulator vtable ab2fb8 slot32 points to 7026f0. The native getter
checks emergency/player state, reads GetSimSpeed through slot27 (8265c0),
and selects the configured animation factor from the table at simulator+108.
Speed enum3 uses +4, enum1 uses +8 and enum2 uses +c. The plugin consumes
this getter directly rather than assuming enum ordering or fixed multipliers.
Positive finite factors scale all scripted scene time; wall gaps are limited
to one second and scaled catch-up to four seconds before 0.25-second substeps.

verify_native_timing.py runs original 7026f0 and 8265c0 with a synthetic
factor table. Compiled-DLL tests check unchanged poses/opacities/removal and
stage logs during two modal intervals and on the first resume tick. Separate
runs use factors1/2/3 and a mid-scene change; whole-scene durations in those
fixtures are17/8.5/5.5 seconds. These are emulated observations, not live-game
rendering or actual default animation-factor measurements.

## Cached traffic leader release (0.20)

Native vehicle manager slot69 is 54fbc0, called separately by RemoveAutomaton
54d690 after its base removal. It walks the manager's actor list at +44 and
only recomputes vehicles whose cached leader (+b0) equals the argument.
It invokes vehicle slot148 (551c20), retains the new leader and releases the
old leader. It does not remove the parked model or change its opacity/state.

551c20 queries path candidates through 54fc30. That query invokes follower
slot73, which is 5059c0 on ordinary native vehicles: the same Collide check
verified in 0.19. Thus the query respects cleared collision flags, but clearing
flags alone does not invalidate an already cached leader. Version 0.20 clears
both owned collision flags first, then invokes manager69 once for each actor.
Binding rejects a manager whose slot69 differs from the expected function;
no global code or manager table is patched.

verify_native_followers.py executes original 54fbc0, 551c20, 54fc30, 5059c0,
4fad20, 4fad60 and 4fad80 instructions against synthetic actors/lane lists.
Only service lookup, positions and reference-count callbacks are simulated.
It reproduces unchanged cached leaders after clearing Collide, verifies that
the refresh chooses a real car farther ahead (or null), balances references,
and leaves a follower of an unrelated car unchanged. Compiled-DLL tests verify
both cars are fully parked and both flags cleared before either refresh.
No live game verification has been performed.

# Native interface evidence used for this experimental build

Target: uploaded SimCity 4(1).exe, SHA-256
3bc5c7fe807fe5aa24a3abb06e40f13486670bc1150612c09baf4ecedafe1a4b.
Ghidra 12.1.2 + bethington Ghidra MCP 6.0.0, x86 Windows compiler model.
Static analysis and SDK declarations do not replace a runtime game test.

| Address | Observed role |
|---|---|
| 0x00505370 | Seven-argument automata creation wrapper; adds to manager and returns a borrowed automaton pointer. |
| 0x00553080 | Vehicle manager random creation point implementation; searches road paths unless ignore-road/path flags are requested. |
| 0x0050BE90 | Exemplar selection; tExemplarData stride 0x6C, resource key at +0x10, name at +0x1C. |
| 0x005072E0 | Two-actor pursuit implementation (MSVC overload slot 22). |
| 0x0050B360 | Opacity target and transition time; immediate target applied with near-zero duration. |
| 0x0055CA90 | Vehicle state dispatcher routes state 21 to native pull-over update. |
| 0x0055E550 | Native pull-over update dereferences controller context; a null controller is unsafe. |
| 0x00516AA0 | Controller activation setter; used to disable attraction while retaining a valid context. |
| 0x00408480 | Native SC4String construction from one C string; thiscall, four-byte callee cleanup. |
| 0x0090CF63 | Native C string buffer free; cdecl, caller cleans stack. |
| 0x006A1450 | Enumerates crime exemplars of type 0x6534284A, group 0xEA12F32C. |
| 0x006A0BA0 | Loads category ID, name, icon key, filters, severity and weighting into a dynamic registry. |
| 0x006A1960 | Copies incident records into a 28-byte-per-entry output vector. |

The incident output includes cell X/Z, category ID, visualization-created flag,
and an icon key. The SDK calls the last field nameKey; its assignment from the
native category icon fields shows that the plugin must supply an icon key.
The output vector uses the game allocator. Existing native entries are retained
when one active scene marker is appended.

The new category has zero selection weight, so the native generator does not
produce unrelated incidents without this DLL's visual scene. The plugin does
not alter the native category registry in memory, crime statistics or saved
crime records. It appends a temporary map report through a per-instance interface
wrapper, and adds the category itself through one independent DBPF resource.

The native broad automata_pullover attractor targets nearby vehicles. The plugin
creates a separate instance for each scene vehicle and immediately deactivates
attraction before manually assigning the two pull-over states. This approach
still requires in-game confirmation of placement, control ownership and cleanup.

## Emergency traffic isolation

Ghidra MCP decompilation of 0x00530AF0 (police primary vtable 0x00A9A0C0,
slot 194, offset 0x308) shows that enabling the emergency effect constructs an
`automata_pullover` controller owned by that vehicle. Disabling it deactivates,
removes, shuts down, and releases that controller. Native dispatch calls this
slot on emergency state transitions (0x0052FF60). Version 0.2 redirects this
one slot on the plugin-owned patrol to invoke 0x00530AF0 with false. This
prevents creation rather than attempting to remove attraction on a later tick.
The 201-slot original table and its preceding RTTI locator are preserved in a
private copy; differing primary tables are rejected. Other vehicles retain their
original tables. The independent police controller at 0x00543C70 concerns the
police-specific controller and is not patched by this change.

## Optional road heading output

Inspection of the original x86 code for 0x00553080 shows the on-road branch
uses argument 5 as the output position (ESP+0x44 after its local frame and saved
registers), but never reads argument 7 (ESP+0x4C). The flag-controlled off-road
fallback passes a null direction to 0x00506DC0 as well. Earlier emulation wrote
a direction vector that the real function does not supply, masking this bug.
Version 0.4 obtains orientation from initialized automata through slot 15 and
passes null to the optional search output and vehicle creation direction input.

## Road occupants (0.5)

Uses the gzcom-dll SDK cISC4City::GetOccupantManager,
cISC4OccupantManager::GetFirstOccupantByPosition filter overload,
cISC4NetworkOccupant interface ID 0xA821EF94, IsOfType and IsIntersection.
The filter selects only Road/Street occupants. These newly used interfaces are
SDK-defined and covered by simulated callbacks, not newly verified runtime
observations. Four-metre corridor sampling approximates a straight segment;
it does not parse the game's exact lane path splines. Paired stopped positions
are explicitly controlled by this DLL after native pull-over movement finishes.

## Curved pull-over (0.7 supersedes the native stop sections)

This build no longer creates automata_pullover controllers or pushes native
state 21. It idles its own two actors and directly controls a three-second
forward-braking path with a seventh-order lateral ease. Orientations follow
path derivatives. The former driver/roadside sign convention was reversed
based on the reported inward movement; roadside is now (-heading.z, 0,
heading.x) for RightHandDrive and its opposite for LeftHandDrive, with the
driver's side opposite the roadside. The per-owned-patrol emergency-effect
suppression remains necessary during native driving before the curve.

## Silent lights, continuous driving and camera pan (0.8)

The current build positions both cars continuously from the first opacity update,
with a two-second straight approach and three-second curve. It does not invoke
native ChaseAutomaton or state21. Earlier native-driving sections are historical.

Ghidra MCP decompiled 0x0050EB20, the actor slot99 emergency visual selector.
Selector2 resolves property 0xC9E69AF6 and creates a visual through 0x0050E4D0.
The supplied DAT's Vehicle_CopCar_normal_10640000 exemplar maps that property to
a 0x5AD0E817 S3D visual model, rather than a sound resource. The DLL calls the
selector directly, storing the returned effect at the native emergency-visual
field +0x2D0. Native 0x00530AF0(false) removes/releases it on cleanup. The
owned-patrol slot194 wrapper now suppresses the combined emergency switch
entirely; no automata_pullover attraction is created. No StartSFX call is made,
and the compiled DLL no longer imports WINMM or includes a synthesized siren.

Decompiled 0x0050A930 shows the native camera-follow path obtains the renderer
from 0x00B43DD0, camera control via renderer slot16, and centres its target via
0x007CD810(control, vector). The latter updates target coordinates and sends
camera-update notifications. The DLL uses that route for a one-shot hotkey pan,
without enabling persistent follow or invoking the zoom-changing follow helper.
Ground coordinates are world X/Z (Y is elevation). The predicted stop centre
comes from the deterministic straight/curved motion, and zoom/rotation are not
assigned. Actual in-game camera behavior and visual flashing remain unverified
for this new build despite successful compiled-code emulation.

## Terrain poses and moving staggered turns (0.9)

Fresh disassembly verified primary actor slot75 points to 0x00509440 for both
stock vehicles (0x00A9D488) and police (0x00A9A0C0). It forwards a transform to
each visual model via its transform setter. Native GetTransform slot12 copies
its first model transform. The structure is 56 bytes: four flag bytes, nine
row-major floats containing basis columns, XYZ translation, and float scale.
The existing scale is retained. Flags are set to the native rotation/translation
combination (2,5), observed in 0x005094A0. Original helper 0x0080B830 confirms
forward in matrix column2 and up in column1. Tests execute the original matrix
helper and transform-forwarding code in Unicorn with a simulated model.

cISTETerrainMap is obtained from cISC4City::GetTerrain, using SDK-defined base
inheritance and methods GetAltitude(float,float) and GetLerpedNormal. The latter
is normalized; travel direction is projected into its tangent plane. Cross
products form the orthonormal right/up/forward basis. All terrain queries are
read-only. Missing heights, invalid normals, unsuitable steep normals, differing
native transform setters or elevated/inconsistent road surfaces cancel safely.

Lead forward motion uses a linear braking velocity over three seconds. The
patrol follows 0.65 seconds later with a blend of linear/quadratic braking,
retaining initial speed and the intended final spacing. Seventh-order lateral
easing completes after 70% of each curve so orientation is straight while
forward velocity remains positive. Vehicle fade-out is a separate core stage
following the officer visit and fade. Driver-side walking distance uses estimated
half body width plus 0.15 metres, instead of the actor's bounding radius.

These tests do not establish in-game graphics output, exact tire contact,
custom vehicle dimensions, native terrain-query behavior under all mods, or
suspension physics. The newly queried SDK surface is preserved in source/sdk.

## Officer placement and arrival facing (0.10)

The previous spawn method cached its intended foot position without explicitly
reapplying it after native creation and idle-state setup. Walking then used that
cached point, allowing a visible discontinuity if setup relocated the pedestrian.
All actors now start at zero opacity. Officer setup is hidden; it explicitly
sets the intended side, ground height, orientation and zero opacity before
becoming visible. Each subsequent update holds the cached foot position through
fade-in, walking, the arrival turn and fade-out.

On arrival, a 0.4-second smooth heading blend faces the speeder's centre from
the door-side endpoint. The core regards arrival as complete after this turn,
so the visit timer does not consume the turn interval. Regression callbacks
simulate both initial relocation and drift during fade-in. Assertions check
signed side, bounded step lengths, stationary arrival turning and final facing.
These are compiled-code tests with simulated pedestrian behavior, not a new
in-game rendering observation.

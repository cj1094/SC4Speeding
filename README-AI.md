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

# SC4Speeding 0.48 — fix native crime filter serialization

Close the game and replace BOTH SC4Speeding.dll and SC4Speeding.dat.
The CrimeUI DAT and ordinance DAT are unchanged.

Version0.47 encoded the one-value WealthFilter and LotConditionFilter as
scalar Uint8 properties. The native crime loader reads these as lists. The
native scalar variant setter leaves the array count at zero, and the crime
mask builder produces a zero eligibility mask for an empty list. That excludes
all lots even though the category's weight is4.

Encode WealthFilter as explicit array[1], PurposeFilter as array[1,2], and
LotConditionFilter as explicit array[0]. Their native masks are1,3 andFFFFFFFF
respectively. This preserves R$/CS$ selection and any lot condition. Weight4,
monthly native notifications, ordinance restrictions, road clearance, queue
behavior, manual test shortcut and the black-backed gauge are retained.

The DLL now detects empty loaded native filters at city attach and logs an
explicit DAT replacement message instead of silently waiting for selections.
It also logs transitions between enabled weight4 and ordinance-disabled
weight0. Normal selection produces the existing 'Speeding visual queued'
message; an unsuitable visual site produces a separate skipped-scene message.

Validation executes the original scalar variant setter and crime mask builder,
checks the shipped serialized arrays, verifies weighted choice, and exercises
notification-driven scenes/ordinance gates in DLL emulation. The previous
native weight test bypassed filter loading and therefore missed this error.
The real game's complete monthly simulation has not been tested here.

# SC4Speeding 0.47 — native crime selection, weight4

Close the game and replace BOTH SC4Speeding.dll and SC4Speeding.dat.
The CrimeUI DAT, ordinance DAT and black-backed gauge are unchanged.

Speeding now has native relative-occurrence weight4, matching Graffiti,
Pie Throwing, Flashing and Toilet Papering. Native filters restrict it to
low-wealth residential or commercial services lots. Selection probabilities
are normalized over the crimes eligible for the particular selected lot;
equal weight does not guarantee equal citywide incident counts.

There is no automatic elapsed-time timer. IntervalSeconds in an old INI is
ignored and can be removed. The game generates Speeding through its normal
crime process; the DLL listens for its crime-created notification and requests
a pullover near that selected lot (48m road-anchor search radius). The starting
road tile must still border an R$/CS$ building, and the full scene must fit
on a straight road/street without overflowing a curve/intersection. A selected
incident without a valid scene site is skipped visually and logged.

An incident is one Speeding crime selected by the game. If several are
selected, their animations queue and play one at a time. The queue holds up to
64 positions; excess visual requests are skipped and logged. Positions are
copied immediately; no lot or message references are retained. Automatic
scenes do not move the camera. Ctrl+Shift+F10 still cancels/restarts a manual
test scene and focuses its location, retaining the eligibility restrictions.

Speed Traps must be available and unchecked. While it is enacted/unavailable,
the DLL sets only its own native crime weight to zero and drops queued visuals.
The baseline weight4 is restored on city detach. Native monthly counting and
police suppression remain the game's responsibility. Only the active pullover's
Speeding marker is shown; unrelated minimap icons follow the native refresh.

Validation executes the original weighted-choice loop with controlled draws
and the compiled DLL with synthetic native notifications. Checks cover no
scene after125 seconds without a notification, unrelated crime IDs ignored,
queued events, proximity to selected lot, marker cleanup, unchanged other
icons, ordinance gates, hotkey restart and retained animation. No live game
or end-to-end monthly simulator test has been performed here.

# SC4Speeding 0.46 — smoother final heading and road-piece pitch

Close the game and replace SC4Speeding.dll. All DAT files are unchanged.

After lateral steering ends, retain the road heading through the rest of the
braking animation. The former code normalized a near-zero motion tangent,
which could briefly select world +Z before snapping back to the road heading.
The old DLL reproduces this stationary yaw jump in the small-tick westbound
test, and the updated DLL passes the same regression.

Throughout fade-in, driving, pull-over, parking, officer visit and fade-out,
both cars fit pitch/roll to four approximate wheel contacts (3m wheelbase,
1.4m track). On road/street tiles, use the native network surface height rather
than only the underlying terrain. Off the road use terrain height. Wheel
contacts span piece boundaries so pitch transitions as the axles cross them.
Keep body center above the road/terrain center height at convex crests.

Validation: compiled DLL emulation exercises slopes independent of flat
terrain, a crest, consecutive pieces with differing slopes, east/west final
braking, all game speeds, pause/menu behavior and retained eligibility. The
original EXE's road-height function also passes a separate world-coordinate
ABI test. These tests do not run the real game or verify rendered appearance.

# SC4Speeding 0.24 — rebuilt ordinance DAT

Close the game completely and replace SC4Speeding-SpeedTraps.dat in:
Documents/SimCity 4/Plugins/140-ordinances/
Keep the 0.23 SC4Speeding.dll and the existing ordinance host DLL.
The gameplay DLL, crime DAT, gauge and UI DAT are byte-identical to 0.23.

The ordinance is rebuilt by copying the host tutorial's Space Exploration
example, retaining its native Sint32 cost fields and resource structure,
changing the ordinance ID and creating separate unique name/description LTEXTs.
All inherited availability/population conditions and effects are removed.
The ID remains f5ee0200, matching the existing DLL's suppression gate.
The name is Speed Traps, description is Speeding deterrent for cities.,
and monthly constant expense is $60 with zero enactment/repeal fees.
The archive uses QFS-compressed resources with their directory record and
has a padded1KiB extent; resource offsets and index sizes are checked.

The uploaded317-byte file matches the previous generated DAT. An independent
sc4@0.2.24 parser can read it, so the exact reason the host reported zero
ordinances has not been demonstrated. This release follows the tutorial's
example-based build rather than claiming a confirmed native loading fix.
Host registration happens at application startup, so fully restart the game
before checking the host log again. Replace the old file; do not install both.

Validation: sc4@0.2.24 and a separate Python decoder both read the rebuilt
archive, text references and exact cost. Original EXE ordinance/budget routines
still give $60 on/$0 off. Actual host loading, menu visibility and saved-city
roundtrip remain unverified. If the host still reports zero, provide its new
log so the next step can address the loader rather than change gameplay logic.

Build instructions: npm install sc4@0.2.24; set SC4_LIBRARY_ROOT to the installed
node_modules/sc4 directory; run python3 make_ordinance.py. The build script and
upstream example/license are under source; no additional runtime dependency is
introduced. The host dependency and installation instructions below still apply.

# SC4Speeding 0.23 — ordinance visibility and diagnostics

Close the game and replace only SC4Speeding.dll. The ordinance DAT, its $60
cost, info text and both crime/UI DAT files are unchanged.

After loading a city, the DLL waits for the host to register Speed Traps. Once
found, it calls the native SetOrdinanceAvailable API if the entry is unavailable,
so it can appear without waiting for the next monthly simulation update. It does
not write the checkbox/on state or touch another ordinance. Existing available
entries are left alone. A delayed host registration is retried on later ticks.

SC4Speeding.log now reports one of:
- Speed Traps: made registered ordinance available in the menu.
- Speed Traps: registered ordinance already available in the menu.
- Speed Traps NOT REGISTERED: check SC4CustomOrdinanceHost.log and its ordinance
  folder path; SC4Speeding-SpeedTraps.dat must be in that folder.

If the entry is still absent, provide SC4CustomOrdinanceHost.log and
SC4Speeding.log. The host's `Ordinance folder path=` and `Found ... ordinance
exemplars.` lines distinguish its data scan from the availability issue.
The actual user installation has not been inspected; this release fixes a
verified startup gap, not a confirmed diagnosis of every missing-menu case.

Compiled-DLL tests cover initially unavailable, already available/checked,
missing and delayed registration, including no extra availability writes and
normal suppression/repeal behavior. These are emulation tests; live menu
visibility still needs confirmation.

# SC4Speeding 0.22 — Speed Traps ordinance

Adds a new City Ordinance named **Speed Traps**. Its info box reads exactly:
**Speeding deterrent for cities.**

When checked, it costs $60 per month and prevents SC4Speeding scenes, including
Ctrl+Shift+F10 requests. Checking it during a scene cleans up that scene and
its minimap marker. Unchecking restores normal speeding eligibility. There
are no enactment/repeal fees or population-based charges. The host and native
ordinance simulator handle the checkbox, saved state and budget totals.

## Installation

1. Close the game.
2. Install **Custom Ordinance Exemplar Host DLL v1.0.1 or later** if you do not
   already have it: https://community.simtropolis.com/files/file/36860-custom-ordinance-exemplar-host-dll/
   Put SC4CustomOrdinanceHost.dll at the top level of a Plugins folder, following
   its own installation instructions. Keep one copy; no modified host is supplied.
3. Replace SC4Speeding.dll with the one in this archive.
4. Copy this archive's **140-ordinances** folder into
   **Documents/SimCity 4/Plugins**. The resulting file must be:
   Documents/SimCity 4/Plugins/140-ordinances/SC4Speeding-SpeedTraps.dat
5. Keep your current SC4Speeding.dat and SC4Speeding-CrimeUI.dat; both are unchanged.

The ordinance DAT must be under the Documents path above even when the speeding
DLL is in the GOG installation's Plugins folder. The host scans that specific
Documents folder to register custom ordinances. Its own readme lists runtime
requirements and the SC4CustomOrdinanceHost.log diagnostic.

The new ordinance uses its own unique instance ID and does not replace an
existing ordinance, UI resource or shared code. Other ordinances and other mods'
dependencies are not edited. Version 0.21's modal pause and game-speed behavior
and version 0.20's follower refresh are retained.

Validation: compiled-DLL tests cover checked/unchecked state, automatic and
manual suppression, mid-scene cleanup and repeal. The native ordinance lookup,
checkbox and monthly aggregation routines were executed in emulation: checked
cost is $60; unchecked cost is $0; repeated months and a population of one million
do not increase it. Host exemplar properties were checked against its v1.0.1
source and documentation. Host resource loading, UI presentation and saved-city
roundtrip have not been tested in the actual game.

# SC4Speeding 0.21

Close the game and replace only SC4Speeding.dll.

Active scenes now check the game's UI modal state, so a quit/confirmation
menu freezes car movement, officer movement, fades and stage timers. Closing
the menu resumes from the same point, consuming the first resume tick to
avoid catching up time spent in the menu. Explicit and emergency pauses
still stop the animation; incidental hidden pauses still do not cause stalls.

Scene motion and timers now use GetAnimationTimeDilation, the game's own
animation speed factor. All three speeds and changes during a scene are
supported without hardcoded speed-button multipliers. Large update gaps
remain bounded and movement is subdivided into at most 0.25-second steps.

Compiled-DLL tests pass for modal freeze/resume, three animation factors,
mid-scene speed changes, user pause, hidden pauses and cleanup. Original EXE
7026f0 was executed in emulation to verify all three speed selections use
the configured factors. Live game behavior still needs confirmation.
Both DAT files and the working gauge/UI artwork are unchanged.

# SC4Speeding 0.20

Close the game and replace only SC4Speeding.dll. Both DAT files, gauge and
panel artwork are unchanged.

Version 0.19 disabled collision after both cars parked, but existing traffic
could retain a cached leader pointing to one of the scene cars. Version 0.20
also calls the native vehicle manager's follower refresh for each scene car,
after both collision flags are cleared and both final shoulder poses applied.
Only cars following one of those two actors have their leader recomputed.
The game chooses the next eligible car, or clears the leader if none remains.
The scene cars stay visible for the officer interaction and normal fade-out.
Traffic lights and other traffic conditions continue to apply.

Compiled-DLL timing tests and original EXE follower-refresh/path-query tests
pass in emulation. Native tests reproduce the stale leader with collision-only
changes, then verify reassignment, clearing on an empty lane, reference counts
and unchanged unrelated followers. Actual game behavior needs confirmation.

# SC4Speeding 0.19

Close the game and replace only SC4Speeding.dll. The DAT files, gauge and
current panel artwork are unchanged.

After both cars finish their complete shoulder curves and their final ground
poses are applied, the plugin clears AutomataFlagCollide on those two owned
cars only. Traffic collision filtering remains unchanged throughout driving
and while either car is still pulling over. Cars on the roadway can then pass
the parked pair under the game's normal traffic rules. No nearby car is
commanded to accelerate; red lights and other traffic conditions still apply.
The parked cars retain their appearance, lights, officer interaction and fade.

Compiled-DLL tests verify both cars reached full shoulder offset before either
flag changes, and collision eligibility remains enabled on all earlier frames.
Normal, left-hand, custom shoulder, hidden pause and fade-cancellation cases
pass. Executed native EXE functions4fad20/4fad60/5059c0 in emulation: clearing
the flag excludes these candidates and leaves an unrelated car unchanged.
Actual queued-traffic recovery still needs in-game confirmation.

# SC4Speeding 0.18

Close the game and replace only SC4Speeding.dll. The current UI, gauge,
officer clearance and 0.17 timing changes are retained.

Placement now requires exactly two opposite network connections (edge masks5
or10), in addition to the native intersection check. The complete network
mask must equal the Road/Street mask so another network's side branch cannot
hide behind a straight Road-only mask. The same axis must persist throughout
the checked corridor. Corners, junctions, dead ends and unknown connectivity
are rejected conservatively; some custom or diagonal pieces may be skipped.
This reads network geometry only and does not modify road pieces or dependencies.

Sampling is every2m with eight extra metres beyond both ends and an explicit
far endpoint check. It covers the driving/turning/stopping corridor and the
patrol's actual radius-derived trailing gap. A rejected full-route candidate
now tries another location within the existing32-attempt limit before any
scene is visible. The stop request rechecks the corridor before turning.

Twelve compiled-DLL scenarios pass, including unflagged and mixed-network
junctions, bends ahead, changes of road axis, normal placement, alternate
headings, left-hand traffic and hidden pauses. Original EXE methods61aee0 and
61ae90 were executed in emulation to verify all16 connection masks and a
mixed-network side branch. Actual game placement still needs confirmation.

# SC4Speeding 0.17

Close the game and replace only SC4Speeding.dll. Current DAT files, gauge and
UI artwork remain unchanged. Officer clearance remains 30cm farther out.

Active scenes now continue through hidden simulation pauses when active ticks
are still supplied. Manual/user pause and emergency pause still stop them.
New scenes do not begin while any pause is active. Scripted movement operates
only on this scene's owned actors on the game thread.

Delayed active updates now retain up to one second of elapsed time and advance
in steps no larger than 250ms. Previously all elapsed time above250ms was lost.
This reduces artificial slowdowns after delayed ticks; it cannot draw movement
while the game thread or rendering itself is blocked. Longer gaps remain bounded
to avoid large jumps. Timing logs identify hidden pauses and gaps over500ms.

Compiled-DLL tests pass for repeated hidden pauses, officer motion during hidden
pauses, irregular750ms callbacks, normal updates, left-hand driving and manual
pause. These tests use simulated game interfaces. The user's recurring pause
has not been reproduced or definitively diagnosed inside SimCity 4 here.

# SC4Speeding 0.16

Close the game and replace only SC4Speeding.dll. The DAT files in this package
retain the current gauge and completed panel artwork corrections.

The officer's driver-side spawn and walk path are 30cm farther from the car
centerlines: 1.45m at the default shoulder setting instead of 1.15m. The same
clearance is applied during fade-in, walking and the final door interaction.

Idle callbacks no longer reset the animation clock before an active tick.
OnTick now owns its clock baseline, including while the simulation is paused.
A compiled-DLL regression test injects an idle callback immediately before
every active tick and verifies the sequence completes. Normal, left-hand,
custom-shoulder and explicit-pause scenarios also pass. This addresses a
possible timing cause, not a confirmed diagnosis of the reported pauses.
Game-thread stalls can still delay visible animation. These changes have not
been tested inside SimCity 4 here.

Outline revision: the minimap outline now ends at the map bottom; the light blank space beneath it has no extended map border. Replace only SC4Speeding-CrimeUI.dat while the game is closed.

Color revision: the added strip below the minimap now matches the light crime-key background. Close the game and replace only SC4Speeding-CrimeUI.dat. No panel geometry, DLL or gauge changes.

# Crime UI background revision (for SC4Speeding 0.15)

Close the game and replace only SC4Speeding-CrimeUI.dat. The DLL and main DAT
are byte-for-byte unchanged from the user-confirmed working 0.15 build.
The current panel positions and working gauge are preserved.

This revision extends the white Crime panel artwork and the lower frame to
452 pixels. It covers both stock 546px textures and the compact 516px textures
(8bbea9d1 and cbbeab61), which earlier artwork changes missed. Independent
backing controls draw above native-owned backings and below the headers, so
native background selection cannot leave the shorter frame exposed.

All three Data View layouts now contain both extended backgrounds. Root,
radio-button and minimap definitions retain their original coordinates.
Resource/geometry checks pass; the new backgrounds need in-game confirmation.

# SC4Speeding 0.15 — experimental Windows DLL

Close the game and replace SC4Speeding.dll, SC4Speeding.dat and
SC4Speeding-CrimeUI.dat. Keep your existing INI configuration.

The Speeding minimap icon now uses an actual SHPI/FSH texture resource under
its dedicated bitmap key, not PNG bytes. It contains a transparent 16x16 gauge
in ARGB8888/BGRA format with a single mip level. The original EXE's bitmap
loader was executed in emulation and accepted it, including all pixel bytes;
the same loader rejects the previously packaged PNG. Stock Car Theft icons
are not changed. The key retains its matching gauge, needle leaning right.

The live Data View panel is found by walking up from the plugin's Speeding
key row; this avoids assuming the game retains the UI resource's root ID.
Only this plugin's modified panel is adjusted. Its root grows from 428px to
452px upward, keeping its bottom edge. Expanded panel containers and their
backings receive the same height to avoid clipping. Radio groups are set to
one exact position, not incrementally offset. The static DAT now leaves root
and radio positions at stock values so the adjustment cannot be applied twice.
The square minimap render surface remains 256x256.

Compiled-DLL tests cover a changed root ID, radio positions already shifted
twice, containing backgrounds, and repeated updates without drift. Original
EXE loader tests validate the FSH format. These are emulation tests; actual
SimCity 4 rendering, live docking and crash behavior remain unverified here.
A "Crime UI: native panel height changed" log line confirms the root adjustment.

Ctrl+Shift+F10 requests and focuses a scene. Automatic attempts start after
10 unpaused seconds, then every 90 seconds. See SC4Speeding.log beside the DLL.

## Behavior in 0.15

- Selects a shared road/street segment clear of intersections. Both cars move
  immediately at six world metres per second and fade in over 1.5 seconds.
- After two seconds the speeder starts a three-second outward pull-over curve.
  The patrol keeps driving straight for another 0.65 seconds, then follows its
  own three-second curve and brakes to the paired stopping gap.
- Steering completes during the first 70% of each curve while forward speed
  is still positive. The final section brakes while already facing straight.
  Cars no longer wait until nearly stationary to finish changing yaw.
- Samples terrain height and interpolated normal at every vehicle pose, including
  while driving, turning and waiting. The native full-transform setter applies
  an orthonormal orientation with its up axis aligned to the sampled normal.
  A small ground clearance is retained, and each car has its own sampled height.
- Both cars pull outward by two metres by default. The speeder finishes directly
  ahead of the police car. The following gap accounts for actor radii.
- The officer fades in beside the car at an estimated half-body-width plus
  15 cm, then walks close alongside the stopped pair to the driver's door.
  The officer is explicitly placed at this driver-side anchor while invisible,
  then held there throughout fade-in. The same position starts the walking path,
  preventing a side-to-side teleport after native pedestrian setup. At the door,
  the officer stops and turns toward the parked car over 0.4 seconds before
  the visit timer starts. Foot positions follow terrain height.
  After the visit, the officer fades out,
  followed by both cars fading out over 1.5 seconds before removal.
- Native police flashing visuals stay active without an audio stream or the
  emergency traffic attractor. No StartSFX command or WINMM import is used.
- Ctrl+Shift+F10 starts a scene and pans to its planned stop. Pressing it during
  a scene re-centres the view. Zoom and camera rotation are preserved. Automatic
  scenes do not pan the view; camera failures are logged.

Movement is scripted on scene-owned actors. Terrain height/normal following
uses SDK cISTETerrainMap queries and a verified 56-byte native transform layout.
This is body alignment to the sampled terrain normal, not individual wheel
suspension or collision physics. Road/Street occupants are supported. Elevated
or inconsistent road/terrain surfaces are rejected rather than snapped to
underlying terrain. Custom roads and sharp slope changes still need in-game
checking.

## Configuration

The [Speeding] section in SC4Speeding.ini contains:

- Enabled=1: activate the plugin.
- IntervalSeconds=90: real unpaused seconds between automatic attempts,
  minimum 30.
- LeftHandDrive=0: right-hand traffic; set 1 for left-hand traffic.
- ShoulderOffsetCentimeters=200: outward movement during the curve. Two metres
  approximate a full typical passenger car's width. Supported range 25–300 cm.
  This does not measure pavement edges or each custom model's width.

## Compatibility and cleanup

Only scene-owned actors are repositioned. There are no global traffic edits,
shared code patches, or overrides of original Lua/resources. A private copy of
the owned patrol's interface suppresses its broad emergency pull-over effect;
stock police interfaces are unchanged. The flashing visual is started separately
through the actor's native visual-model effect slot; no broad traffic controller
is created. No audio stream is opened. The original actor table
is restored during cleanup. Unexpected primary police tables cancel the scene
instead of replacing another mod's table.

The crime map uses an isolated per-city incident-array hook, retaining existing
incidents and appending one temporary visualization. An existing incompatible
hook disables integration. The independent DAT crime record has zero random
selection weight. This visual report does not change monthly crime statistics,
arrests, revenue, or saved crime incidents. Compatibility with all mods cannot
be guaranteed; guards cover the interfaces inspected for this executable.

Close the game and remove the three installed files to uninstall.

## Validation and building

Thirty-three compiled-DLL emulation scenarios pass. These cover continuous moving
fade-in, terrain planes/crests, missing or invalid terrain, normal-aligned
orthonormal transforms, forward movement during yaw changes, delayed police
steering, paired spacing, vehicle fade-out, close officer routing, camera pan,
silent lights, pause, compatibility guards and cancellation (including during
vehicle fade-out), simulated pedestrian relocation during spawn/idle, signed
driver-side placement, bounded walking steps and final facing toward the car. Callbacks simulate city services and graphics; no running
game or real rendering has been tested for this version.

Seven portable controller scenarios also pass. A separate Unicorn test executes
the original EXE's orientation-matrix helper at 0x0080B830 and transform setter
at 0x00509440 against a simulated model callback. This verifies matrix storage,
56-byte forwarding and the native calling convention, without running the game.

source/build.sh uses LLVM clang targeting i686-pc-windows-msvc and lld-link,
with no C++ runtime imports. Set SC4_LLVM_ROOT if LLVM-MinGW is elsewhere.
The DLL imports KERNEL32 and USER32 and exports GZDllGetGZCOMDirector.
Source and the minimal gzcom-dll SDK headers are included under their supplied
licenses; see LICENSE.txt and source/sdk/LICENSE. NATIVE-EVIDENCE.md records
reverse-engineering observations, including earlier approaches superseded by
this build. validation/ contains the test outputs and file hashes.

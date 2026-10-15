# Controller API Contract V2.3

**Status: DRAFT — AWAITING REVIEW**

Date: 15/10/2026. Controller owner: **Việt Xô**. SimulationEngine integration: **Vĩ**.
Target branch: `feat/algorithm` (confirmed by the requester; not `feat/algorithms`).
This document proposes a contract; it does not implement or approve Controller.
Do not begin official Controller implementation until team review and approval.

Design authority read for this revision: `../Traffic Light Signal Simulation/Thiết kế hệ thống smart traffic light.docx`,
D2.3 dated 12/10/2026, sections 3, 4.3, 7.3, 8.1–8.3, 8.7–8.10, 9,
10.3–10.6 and 13, including table text and pseudocode. Source document is not
committed here. **DESIGN SPECIFIED** means a DOCX requirement, not code.
**IMPLEMENTED** means present in inspected source (main-only where noted);
**PROPOSED** means a new interface; **NEEDS REVIEW** means unresolved approval.
This revision replaces the previous draft's engine-built-plan architecture.

## 1. Repository evidence and scope

Inspected branch revision: `13aeb0a`; latest fetched `origin/main`: `6fe897f`.
Compared source, README, algorithm/simulation contracts, Config/storage/algorithm,
snapshot/geometry tests and the Models handoff, Lane and Signal tests on main.
The handoff and Signal tests are absent on this branch. Source takes precedence
over historical TODO text or test counts recorded in documents.

| Component | On feat/algorithm | On origin/main | Contract status |
| --- | --- | --- | --- |
| Config, Motion2DConfig | Implemented | Implemented | IMPLEMENTED: rates_per_min, motion_2d.enabled, integer signal durations; validate/from_dict/to_dict |
| poisson_sample, allocate_green_adaptive | Implemented | Implemented | IMPLEMENTED; Controller does not sample arrivals |
| SignalSegment, SignalPlan, Lane | Placeholder modules | Implemented | IMPLEMENTED ON MAIN ONLY; dependency must be integrated before Controller code |
| SignalSnapshot, SimulationSnapshot | Implemented DTOs | Implemented DTOs | IMPLEMENTED validation/serialization, not a running engine |
| TrafficLightController | Placeholder module | Placeholder module | PROPOSED: all methods and properties below |
| SimulationEngine, MovementEngine | Module documentation only | Module documentation only | PROPOSED integration APIs; no callable engine class yet |

No source, tests, Models, Algorithm or engine files are changed by this task.
The branch has no additional source changes relative to its merge base with main;
it is missing later Models commits present on main. A PR must not present these
missing commits as intentional source deletions or claim full integration works.

## 2. Responsibilities and dependencies

Controller owns one six-segment NS/EW schedule, countdown, safe transitions,
ALL_RED clearance hold, cycle completion and signal-only state for the engine.
It computes demand/utilization, calls the existing Adaptive function and builds
its own plan at actual cycle boundaries. It never reallocates mid-cycle. Only one axis can have GREEN.

Controller does not generate Poisson arrivals, move Vehicles, pop or mutate Lane
queues, persist JSON/CSV, render Streamlit, or own the session clock/state.
GREEN is a necessary permission, not sufficient authorization for crossing.

Models own validation, FIFO, schedule representation and immutable DTOs.
Algorithms owns independent calculation. Controller owns demand/utilization,
Adaptive delegation, plan construction and signal execution. SimulationEngine
owns session/tick/statistics orchestration. MovementEngine owns physical motion,
gap, crossing and conflict occupancy. UI only issues commands and renders.
Controller imports Models/algorithms, not concrete Engine/Movement or Streamlit;
Movement reads signal permission, avoiding a circular import.

| Dependency | Relationship | Independent testing |
| --- | --- | --- |
| Config | Direct: validate and take detached value snapshot; budget, min, yellow/all-red, clearance_limit_s | Real Config fixtures |
| SignalSegment/SignalPlan | Direct, once main dependency is integrated; immutable segment values and controller-owned progression | Real Models plan; deterministic allocations |
| Adaptive | Direct: Controller calls allocate_green_adaptive(q_ns: int, q_ew: int, green_budget: int, min_green: int) -> tuple[int, int] | Fixed 21/39 allocation or pure function |
| SimulationEngine | Integration caller; owns sim_time, cycles_to_run, session state, cycle_index, cycle metrics and boundary inputs | Driver calling tick once per second |
| MovementEngine | Indirect; engine passes occupancy result, not Vehicle collections | Scripted bool conflict_clear sequence |
| SignalSnapshot | Direct output DTO; frozen, copied direction colors | Real DTO validation |

IMPLEMENTED ON MAIN: SignalPlan.from_config(config, green_ns_s, green_ew_s,
cycle_no=1), segments, nominal_duration_s, current(), move_next(), is_cycle_end().
SignalSegment exposes code, active_phase, color, duration_s, green_directions and
is_green_for(direction). Plans do not loop automatically. Never access _pending.

## 3. Proposed public API

Everything in this code block is **PROPOSED**, not an importable implementation.
Imports refer to existing DTO/Config and the SignalPlan implementation on main.

```python
from collections.abc import Mapping
from src.models.config import Config
from src.models.signal import SignalPlan  # available on main, absent here
from src.models.snapshot import SignalSnapshot

class TrafficLightController:
    def __init__(self, config: Config) -> None: ...
    def compute_phase_demand(self, queue_lengths: Mapping[str, int]) -> tuple[int, int]: ...
    def compute_utilization(self, q_ns: int, q_ew: int,
                            prev_green: tuple[int, int]) -> dict[str, float]: ...
    def build_cycle_plan(self, queue_lengths: Mapping[str, int], *, cycle_no: int) -> SignalPlan: ...
    def tick(self, *, conflict_clear: bool) -> None: ...
    def is_green_for(self, direction: str) -> bool: ...
    def start_next_cycle(self, queue_lengths: Mapping[str, int], *,
                         cycle_no: int, started_at: int, conflict_clear: bool) -> None: ...
    def to_signal_snapshot(self) -> SignalSnapshot: ...

    @property
    def current_segment_code(self) -> str | None: ...
    @property
    def remaining_s(self) -> int: ...
    @property
    def cycle_complete(self) -> bool: ...
    @property
    def in_error(self) -> bool: ...
    @property
    def clearance_hold_s(self) -> int: ...
```

Constructor validates and copies Config through Config.from_dict(config.to_dict()).
It creates UNSTARTED state: no plan, code=None, remaining=0, complete=False,
error=False, hold=0. Initial activation uses start_next_cycle with cycle_no=1,
started_at=0 and conflict_clear=True. No plan is supplied by the engine.
The Controller builds a fresh owned plan; no mutable plan cursor is shared.

Properties are read-only. remaining_s is nominal seconds left, >=0; hold shows 0.
clearance_hold_s is total extra ALL_RED seconds in the current cycle, reset only
when a new plan is accepted. A separate private counter tracks each contiguous
hold for timeout. No new public counter is required.

tick consumes exactly one completed logical second, not dt_s or wall time. It
returns None; inspect properties or request a detached SignalSnapshot afterwards.
is_green_for accepts N/S/E/W only (TypeError for non-string, ValueError for other
strings), returns False during yellow/red, completed cycles and ERROR. It does
not apply startup_delay_s, headway_s or spacing rules.

start_next_cycle accepts UNSTARTED (cycle 1) or safe cycle_complete (previous+1),
never ERROR. Require actual bool conflict_clear=True. It receives detached counts,
computes reporting utilization, calls build_cycle_plan once, validates and then
atomically activates the result. Reset counters and start NS_GREEN at full duration.
The first started_at is 0; later it must equal the completed boundary timestamp
tracked from accepted ticks. Engine supplies time; Controller never owns sim_time.
No implicit next cycle or reset exists. Snapshot before first activation raises
RuntimeError; after completion/ERROR it remains readable.

Wrong types: TypeError. Invalid values: ValueError. Wrong lifecycle (including
tick before activation/after completion/ERROR): RuntimeError. Validate before
mutating countdown, cursor, previous-green report or counters. Unexpected dependency
errors propagate with active state unchanged; Engine stops safely, not with a fake
plan. These exact signatures/error choices are PROPOSED, NEEDS REVIEW R1/R4.

### Method inputs, preconditions, postconditions and callers

| Method / caller | Inputs and preconditions | Return and postconditions | Exceptions |
| --- | --- | --- | --- |
| __init__ / Engine | Valid Config | None; detached configuration and UNSTARTED state | TypeError/ValueError from validation |
| compute_phase_demand / Controller, analysis tests | Mapping with exactly N/S/E/W and actual int counts >=0 | tuple[int,int] = (N+S,E+W), no mutation | TypeError map/value type; ValueError keys/range |
| compute_utilization / Controller, reporting | q_ns/q_ew int >=0, prev_green tuple of two positive ints each >=min and sum=budget | Fresh dict eta_ns,eta_ew,eta_bar; pure reporting, no schedule change | TypeError wrong types; ValueError invalid tuple/range/budget |
| build_cycle_plan / Controller only in production | Boundary-ready (UNSTARTED or complete), no ERROR; direction counts; cycle_no=1 or previous+1 | Fresh unconsumed SignalPlan, no activation or state mutation | RuntimeError lifecycle; TypeError/ValueError counts/cycle/result |
| start_next_cycle / Engine | Boundary-ready, counts/cycle/time valid, conflict_clear=True | None; one allocation/build, atomic activation at NS_GREEN; reset holds | RuntimeError lifecycle/time mismatch; TypeError wrong types; ValueError nonclear/invalid inputs |
| tick / Engine | Active, not complete/error; bool occupancy after one movement second | None; one countdown/transition or hold update, never Adaptive | RuntimeError lifecycle; TypeError occupancy |
| is_green_for / Movement | N/S/E/W string | bool, pure signal permission; False also before activation | TypeError non-string; ValueError other direction |
| to_signal_snapshot / Engine | At least one activated plan | Fresh immutable SignalSnapshot with copied colors; no mutation | RuntimeError UNSTARTED |

Counts are not limited to 100: Config's initial_queue bound is not a live Queue
capacity. Preview build_cycle_plan calls are boundary-only and nonactivating;
production Engine only uses start_next_cycle, not a preview followed by a second
allocation. No new public wrapper implementing Adaptive is introduced.

### Demand, utilization and plan construction

DESIGN SPECIFIED (DOCX section 7.3): utilization is normalized demand in vehicles/s,
not measured occupancy or a percentage. Return eta_ns=q_ns/prev_green[0],
eta_ew=q_ew/prev_green[1], eta_bar=(q_ns+q_ew)/config.green_budget_s.
For the first cycle prev_green=(budget//2,budget-budget//2), valid under budget>=2*min;
afterwards use the last completed plan's pair. Keep reports detached for Engine
statistics. These ratios never change the independent Adaptive formula.
Zero demand yields zero ratios and Algorithm's existing empty fallback.
Dict field names and report publication are PROPOSED, NEEDS REVIEW R1.

PROPOSED build_cycle_plan orchestration using IMPLEMENTED functions:

```python
q_ns, q_ew = self.compute_phase_demand(queue_lengths)
g_ns, g_ew = algorithms.allocate_green_adaptive(
    q_ns, q_ew, config.green_budget_s, config.min_green_s
)
plan = SignalPlan.from_config(config, g_ns, g_ew, cycle_no=cycle_no)
```

Do not copy proportional allocation, borrowing, half-up or fallback into Controller.
The class method named allocate_green_adaptive in the DOCX class table is fulfilled
by delegation to the existing module function; no duplicate wrapper is necessary
(NEEDS REVIEW R1). Given counts 7/4/16/5, demand=(11,21), first utilization is
(11/30,21/30,32/60), and the real Algorithm returns (21,39).

## 4. Six-segment cycle and invariants

| Segment | Duration | N/S colors | E/W colors | Crossing permission |
| --- | --- | --- | --- | --- |
| NS_GREEN | plan.green_ns_s | GREEN | RED | N/S only, subject to Movement guards |
| NS_YELLOW | config.yellow_s | YELLOW | RED | None |
| ALL_RED_1 | config.all_red_s + optional hold | RED | RED | None |
| EW_GREEN | plan.green_ew_s | RED | GREEN | E/W only, subject to Movement guards |
| EW_YELLOW | config.yellow_s | RED | YELLOW | None |
| ALL_RED_2 | config.all_red_s + optional hold | RED | RED | None |

green_ns_s + green_ew_s = config.green_budget_s; each >= config.min_green_s.
All nominal durations are actual ints, excluding bool/float/string, as Config
and SignalPlan enforce. Never hardcode 60/3/1 in the runtime Controller.
Nominal total = green_budget_s + 2*yellow_s + 2*all_red_s. Defaults are budget=60,
min_green=10 per phase, yellow=3 per phase and all_red=1 per phase, giving 68s;
21/39 gives [21,3,1,39,3,1]. Actual cycle time adds both holds and no startup
extension: startup is inside the green interval, not added to the plan.

## 5. Tick ordering and clock ownership — PROPOSED

Engine owns t and calls Controller at the end of [t,t+1), after moving all
substeps under the signal that was active at t. With dt_s=0.2 there are five
substeps; other valid Config dt values use round(1/dt_s) steps.
Arrivals are sampled once per direction per logical second, never per substep.
Engine then follows the proposed statistics/signal ordering below. New signal applies to the next
interval; no extra second of GREEN and no retroactive crossing permission.
Pause/read snapshot/UI reruns do not call tick. Step runs exactly one interval.

### BR-03 versus pseudocode — NEEDS REVIEW R4

DOCX BR-03 (§4.3) says arrivals → enqueue → serve → statistics → signal update.
Pseudocode §8.2 calls Controller advance before stats.capture_tick(t0+1), then
increments sim_time. §10.7 mentions Movement followed by Controller/Stats without
resolving the two statistics phases. This is an explicit source discrepancy.

Proposed reconciliation for Việt Xô/Vĩ approval: record crossing/exited events
and interval counters during movement using the signal that served [t,t+1);
after movement sample conflict_clear at t+1, call Controller.tick, set engine
sim_time=t+1, then capture aggregate end-of-tick statistics with boundary signals.
Never attribute preceding movement to the newly activated signal. This splits
event accounting from aggregate capture and moves the pseudocode clock assignment
before capture to avoid two timestamps. Names of Stats methods are not assumed.
Finally close cycle metrics and apply the actual-cycle protocol below before
publishing the synchronized overall snapshot. This ordering is PROPOSED,
not silently declared design-approved.

For GREEN/YELLOW, decrement remaining_s by one; if it reaches zero, consume the
segment once and initialize the next segment's full duration at the same boundary.
For ALL_RED, always finish its nominal countdown first. When it first reaches
zero, check conflict_clear: if clear transition immediately (or complete cycle);
otherwise stay red at zero. That boundary starts hold but has elapsed zero extra
seconds, so do not increment hold yet. Each following full red tick adds one
second to both cycle-total hold and this contiguous hold, then checks clearance
and timeout. Never allow a negative remaining_s or decrement the next segment
in the tick that starts it.

Without hold, boundaries for 21/39 at cycle start t=0 are:

| Time | State after boundary |
| --- | --- |
| 0 | NS_GREEN, 21 left |
| 21 | NS_YELLOW, 3 left |
| 24 | ALL_RED_1, 1 left |
| 25 | EW_GREEN, 39 left |
| 64 | EW_YELLOW, 3 left |
| 67 | ALL_RED_2, 1 left |
| 68 | cycle_complete=True, ALL_RED_2 displayed, 0 left |

At final safe completion consume the last plan segment but retain a terminal
ALL_RED_2 display for the existing snapshot DTO. Engine records metrics and
checks cycles_to_run before providing fresh Queue counts to Controller.
If continuing, start_next_cycle can run at the same boundary, without a movement
step or time increment. Snapshot then describes the new cycle at that same time;
the previous cycle metrics must already be recorded (R4).

### Actual cycle boundary and cycle_index ownership

DESIGN SPECIFIED BR-06/§8.3: finish ALL_RED_2 including safe clearance, close
actual-cycle metrics once, then either complete at cycles_to_run or read Queue
for a new plan. Engine owns cycle_index exclusively; Controller validates the
number passed and never increments Engine state. Engine passes current counts
and cycle_index+1 to start_next_cycle; Controller computes demand/utilization,
delegates Adaptive, builds and activates the plan. Only after success does Engine
assign its new cycle_index and reset green clocks before movement resumes.
Failure leaves terminal all-red; Engine stops in ERROR, without claiming a new
cycle. At the final configured cycle no further Adaptive call is made.
No rebuild occurs in tick, hold or reads. Pause/Stop do not tick or activate
cycles; explicit Step while paused runs one interval. Reset recreates the session.

## 6. Safety and clearance — PROPOSED / NEEDS REVIEW

Engine passes conflict_clear: bool obtained from MovementEngine.is_conflict_clear()
(a documented proposed method, not implemented). Missing/unknown occupancy must
not be turned into True. Occupancy requires full vehicle body bounds, including
rear still in conflict region; active_crossing count alone is insufficient.
Geometry width/physical occupancy remain unresolved in simulation_contracts.md;
Controller neither invents vehicle width nor calculates geometry.

No new crossing during yellow or red. Already-crossed vehicles keep moving to
clear the region. Movement owns startup/headway/min_gap/FIFO guards, Vehicle
crossing event and the single queue pop. Controller only supplies signal permission.
SimulationEngine stops further ticks on ERROR and owns session_state='ERROR'.

At a red release boundary require nominal remaining_s=0 and conflict_clear=True,
including final ALL_RED_2 before cycle_complete. Nonclear red stays at zero;
hold never modifies the green budget. Proposed timeout is **contiguous hold >
config.motion_2d.clearance_limit_s**, matching “quá” in the simulation contract.
At each held tick, timeout takes precedence over a newly clear reading if elapsed
hold is already above the limit. Equality is still allowed; for limit 2.5s,
the third extra second errors even if that reading is clear. This discretization,
priority and per-hold versus aggregate interpretation require explicit R3 approval.

On timeout keep the current ALL_RED_1/ALL_RED_2 code, remaining_s=0, all colors
RED, in_error=True, cycle_complete=False. No synthetic ERROR segment is added
(SignalSnapshot only allows six codes). No automatic recovery; engine reset
creates a new controller/session after addressing occupancy. Validate motion
parameters even when enabled=False; physical safety must not silently disappear.
Behavior of non-2D occupancy is unresolved (R5), not permission to assume clear.

### Lane and green-clock integration — PROPOSED / NEEDS REVIEW R1/R5

IMPLEMENTED ON MAIN: Lane.count() -> int includes approaching and stopped Queue
vehicles. Engine reads count once per direction at actual cycle start and sends
a new exact N/S/E/W mapping to Controller. No _queue access or mutable Queue/
Vehicle references. DOCX compute_phase_demand(lanes) becomes a detached mapping
here to limit coupling; direct Controller calls to Lane.count are a review
alternative, not a second concurrent data source.

IMPLEMENTED ON MAIN public APIs:

```python
lane.reset_green_clock(started_at: float | None = None,
                       startup_delay_s: float = 0.0, headway_s: float = 1.0) -> None
lane.is_cross_eligible(t: float) -> bool
lane.pop_crossed() -> Vehicle | None
```

Engine is the sole proposed green-clock notification owner. At initial/new
NS_GREEN or an EW_GREEN transition, detected through Controller's public state,
call reset_green_clock(boundary_time, config.startup_delay_s, config.headway_s)
once on the two green lanes before movement. On leaving GREEN call
reset_green_clock() on those lanes to disable eligibility. Never reset each
tick/read or restart crossed vehicles' motion. Lane sets next eligibility to
start+startup; pop_crossed advances it from crossed_stop_t+headway_s.
Movement combines is_cross_eligible(t), is_green_for(direction), gap/arrival/
stopline guards. Controller does not mutate Lane clocks or queue.
DOCX §13 TC-23 requires no departure before arrival_t+1; its interpretation with
fractional crossing (§8.11) needs Vĩ/Models confirmation (R5).
No callback/event class is assumed to exist.

## 7. Integration and snapshot adaptation

```text
Lane / Queue --public Lane.count() via Engine--> direction counts
    --> TrafficLightController.compute_phase_demand()
    --> compute_utilization() for reporting
    --> algorithms.allocate_green_adaptive() --> (g_ns, g_ew)
    --> TrafficLightController.build_cycle_plan() --> SignalPlan (six segments)
    --> Controller state/signals --> SimulationEngine
    --> SignalSnapshot inside SimulationSnapshot --> UI
```

This is responsibility/data flow, not the full tick call order. Controller owns
allocation orchestration and plan creation. Queue snapshot uses N+S and E+W
counts, excludes active crossings, and is captured once at actual cycle start.
Controller calls allocate_green_adaptive(11,21,60,10), which returns (21,39), then
uses SignalPlan.from_config(config,21,39,cycle_no=1), available on main.

Existing SignalSnapshot constructor is:

```python
SignalSnapshot(current_segment: str, active_phase: Phase | None,
               remaining_s: int, signal_colors: Mapping[Direction, SignalColor])
```

IMPORTANT: on main SignalSegment.active_phase is None for YELLOW and ALL_RED;
SignalSnapshot instead requires NS for NS_YELLOW and EW for EW_YELLOW. Therefore
to_signal_snapshot must map phase from segment code, not copy active_phase:

| Codes | SignalSegment.active_phase | SignalSnapshot.active_phase |
| --- | --- | --- |
| NS_GREEN / EW_GREEN | NS / EW | NS / EW |
| NS_YELLOW / EW_YELLOW | None | NS / EW |
| ALL_RED_1 / ALL_RED_2 | None | None |

Snapshot phase identifies the displayed axis; it never authorizes crossing.
Build four direction colors from the table in section 4, return a fresh frozen
DTO, and do not expose plan cursors. Error/terminal snapshots retain ALL_RED code.
No snapshot schema change is proposed. R2 requests Models owner confirmation.
MetricsSnapshot.clearance_hold_s receives cycle-total hold (float accepted);
session totals belong to engine/statistics and are not this property's meaning.

## 8. Unit test contract

Additional required cases, all **PLANNED**: read public Lane counts and aggregate
7/4/16/5 into 11/21; compute utilization 11/30,21/30,32/60; spy on exactly one
Adaptive call with correct arguments and verify its returned allocation creates
six segments; conserve budget/min including empty demand; no allocation during
ticks/hold/reads; fresh allocation once at each new actual cycle; no extra call
at cycles_to_run; green entry/exit resets Lane clocks once and Movement applies
startup/headway; validate missing/extra directions and bool/float/string counts.
Initial nearly equal previous-green fallback and later completed-plan reporting
must be tested independently of allocation. Engine alone updates cycle_index.
These extend the cases below; no tests are implemented or skipped by this task.

All rows are **PLANNED** for tests/test_controller.py; no Controller test is
implemented or claimed PASS by this documentation change. Tests can drive a
controller using scripted booleans without a real MovementEngine.

| ID | Test / acceptance |
| --- | --- |
| C01 | Valid detached Config: UNSTARTED; start with fresh counts/clear=True gives NS_GREEN,21, not complete/error |
| C02 | Exact six segment order and full-duration transition boundaries listed above |
| C03 | Countdown changes once per tick; reads/is_green_for do not mutate time |
| C04 | 68 ticks complete 21/39 cycle with no hold; custom yellow/all-red use Config |
| C05 | Every observable state: never both axes GREEN; invalid directions rejected |
| C06 | Yellow/all-red permission False for all directions; Movement integration separately verifies no crossing |
| C07 | Red nominal expiry occupied: zero remaining and zero extra elapsed; following ticks accumulate hold |
| C08 | Clearance at/below limit releases; above limit errors even if newly clear; fractional 2.5 limit covered |
| C09 | Holds on both red segments: cycle total accumulates, contiguous timeout counter resets at release |
| C10 | Final red occupied does not complete; clear completes once; no automatic plan loop |
| C11 | New demand/allocation/build only after safe completion, cycle_no+1; reset counters; reject invalid activation atomically |
| C12 | All six SignalSnapshots validate, especially yellow phase mapping; terminal/error all-red accepted |
| C13 | Reject Config/count/cycle/time/bool type or value errors; no partial mutation or caller-data mutation |
| C14 | tick after ERROR/completion rejected; snapshot remains readable and stable |
| C15 | Engine integration: end-of-interval occupancy, pause/step, new-cycle metrics/snapshot boundary, already-crossed motion |
| C16 | Nonclear initial start rejected; UNSTARTED snapshot rejected; enabled=False policy after R5 resolution |

Existing algorithm/Config/snapshot tests verify only their own implemented
components. Their PASS does not prove Controller, 68-second ticking, clearance,
Movement or Engine integration. No test is added, skipped or weakened here.

## 9. Design Compliance & Deviations

| Design Requirement | Reference | Proposed Implementation | Status |
| --- | --- | --- | --- |
| Independent Adaptive algorithm | §7.3 module pseudocode, §9.4 | Reuse existing algorithms.allocate_green_adaptive unchanged | IMPLEMENTED calculation; PROPOSED orchestration |
| Controller computes demand, utilization and builds/executes schedule | §9.1, §10.3 | compute_phase_demand, compute_utilization, build_cycle_plan, start_next_cycle | DESIGN SPECIFIED responsibilities; PROPOSED API |
| Class table lists allocate_green_adaptive | §10.3 versus §7.3 module function | Direct module delegation, no duplicated formula/wrapper | NEEDS REVIEW R1; preserves responsibility |
| Demand from Lane before crossing | §6.1, §6.4, §10.3 | Engine copies public Lane.count into exact direction mapping | NEEDS REVIEW R1; deliberate signature adaptation from lanes |
| Utilization reports normalized demand using previous green | §7.3 | eta_ns, eta_ew, eta_bar; first previous pair nearly equal | DESIGN SPECIFIED formula; PROPOSED dict/report interface |
| Engine coordinates session/time/statistics | §9, §10.4–10.6 | Engine owns sim_time/cycle_index and invokes Controller | DESIGN SPECIFIED; exact boundary handoff NEEDS REVIEW R4 |
| Movement owns physics/occupancy/crossing | §8.7–8.10, §10.4 | Movement uses signal+Lane eligibility and supplies conflict_clear | DESIGN SPECIFIED; physical width/non-2D/arrival timing NEEDS REVIEW R5 |
| Reuse Models, optional circular deque | §6.1, §10.3 and main Models API | Fresh one-cycle SignalPlan, public cursor only, no new enum | NEEDS REVIEW R6; optional rotation adapted to implemented Models |
| Reallocate only at actual cycle boundary | BR-06, §7.4, §8.3 | Controller builds after safe final red and Engine closes metrics | DESIGN SPECIFIED; activation protocol PROPOSED |
| Signal and statistics update ordering | BR-03 versus §8.2 and §10.7 | Event accounting before transition; aggregate capture after at one timestamp | NEEDS REVIEW R4; explicit discrepancy/reconciliation above |
| Startup/headway on GREEN | §8.3, §8.9 | Engine calls Lane.reset_green_clock once at entry/exit | DESIGN SPECIFIED rule; notification owner NEEDS REVIEW R5 |
| Safe all-red hold/timeout | §3.4, §8.10 | Hold until clear; all-red ERROR; per-hold >limit sampled each second | DESIGN SPECIFIED safety; timeout scope/precision/priority NEEDS REVIEW R3 |
| Snapshot yellow display versus crossing permission | SignalSegment and SignalSnapshot source | Explicit code-based yellow adapter | IMPLEMENTED DTO distinction; adapter NEEDS REVIEW R2 |
| No direct Streamlit dependency | §9.3, §10.5 | Controller depends only on Models/algorithms | DESIGN SPECIFIED; PROPOSED module boundary |

The older docs/algorithm_contracts.md §14 assigns plan creation to Engine. This
draft explicitly proposes replacing that orchestration with Controller ownership
to follow DOCX §10.3 and the current task. Synchronize dependent contracts after
team review (R1/R4); this task does not edit them. No signal Enum exists on main:
codes/colors are validated strings; snapshot Direction/Phase are Literal aliases.

## 10. Review questions and approval gate

| ID | NEEDS REVIEW | Owner |
| --- | --- | --- |
| R1 | Controller demand/utilization/Adaptive/build ownership; detached counts vs lanes signature; module delegation and reporting | Việt Xô + Models owner |
| R2 | Yellow snapshot adapter preserves distinct meanings of active_phase without changing Models | Models owner + Việt Xô |
| R3 | Timeout > limit, contiguous hold, sampled-second precision and timeout precedence | Việt Xô + Vĩ |
| R4 | BR-03/§8.2 ordering, sole Engine cycle_index ownership, terminal red and same-boundary activation/snapshot/lifecycle | Việt Xô + Vĩ |
| R5 | Reliable occupancy/width/non-2D safety, Engine green-clock notification ownership, arrival_t+1 with fractional crossing | Vĩ + Models owner + Việt Xô |
| R6 | Integrate main SignalPlan/Lane dependency through team Git workflow; fresh one-cycle cursor vs optional circular deque | Models owner + team |

## Review & Approval

**DRAFT — AWAITING REVIEW**

- [ ] Việt Xô — Review trách nhiệm Controller, public API, Adaptive integration và sáu đoạn tín hiệu.
- [ ] Vĩ — Review tích hợp SimulationEngine và MovementEngine.
- [ ] Models owner — Review tương thích Config, SignalSegment, SignalPlan, SignalSnapshot và Lane.
- [ ] Thống nhất thứ tự xử lý tick.
- [ ] Thống nhất cơ chế clearance hold.
- [ ] Thống nhất quyền sở hữu cycle_index và chu kỳ mới.
- [ ] Giải quyết toàn bộ NEEDS REVIEW.
- [ ] Contract được nhóm APPROVED.

Only reviewers can resolve these decisions and approve the contract. This task
ends after documentation, push and PR preparation; no official Controller code.

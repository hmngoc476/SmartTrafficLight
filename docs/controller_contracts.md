# Controller API Contract V2.3

**Status: DRAFT — AWAITING REVIEW**

Date: 15/10/2026. Controller owner: **Việt Xô**. SimulationEngine integration: **Vĩ**.
Target branch: `feat/algorithm` (confirmed by the requester; not `feat/algorithms`).
This document proposes a contract; it does not implement or approve Controller.
Do not begin official Controller implementation until team review and approval.

## 1. Repository evidence and scope

Inspected branch revision: `13aeb0a`; latest fetched `origin/main`: `6fe897f`.
Compared source, README, algorithm/simulation contracts, Config/storage/algorithm,
snapshot/geometry tests and the Models handoff and Signal tests on main.
The handoff and Signal tests are absent on this branch. Source takes precedence
over historical TODO text or test counts recorded in documents.

| Component | On feat/algorithm | On origin/main | Contract status |
| --- | --- | --- | --- |
| Config, Motion2DConfig | Implemented | Implemented | IMPLEMENTED: rates_per_min, motion_2d.enabled, integer signal durations; validate/from_dict/to_dict |
| poisson_sample, allocate_green_adaptive | Implemented | Implemented | IMPLEMENTED; Controller does not sample arrivals |
| SignalSegment, SignalPlan | Placeholder module | Implemented | IMPLEMENTED ON MAIN ONLY; dependency must be integrated before Controller code |
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
It receives a plan containing Adaptive's green allocation and never recalculates
green times during a cycle. Only one axis can have GREEN.

Controller does not generate Poisson arrivals, move Vehicles, pop or mutate Lane
queues, persist JSON/CSV, render Streamlit, or own the session clock/state.
GREEN is a necessary permission, not sufficient authorization for crossing.

| Dependency | Relationship | Independent testing |
| --- | --- | --- |
| Config | Direct: validate and take detached value snapshot; budget, min, yellow/all-red, clearance_limit_s | Real Config fixtures |
| SignalSegment/SignalPlan | Direct, once main dependency is integrated; immutable segment values and controller-owned progression | Real Models plan; deterministic allocations |
| Adaptive | Integration: engine calls allocate_green_adaptive(q_ns: int, q_ew: int, green_budget: int, min_green: int) -> tuple[int, int] | Fixed 21/39 allocation or pure function |
| SimulationEngine | Integration caller; owns sim_time, cycles_to_run, session state, cycle metrics and plan creation | Driver calling tick once per second |
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
from src.models.config import Config
from src.models.signal import SignalPlan  # available on main, absent here
from src.models.snapshot import SignalSnapshot

class TrafficLightController:
    def __init__(self, config: Config, plan: SignalPlan, *, conflict_clear: bool) -> None: ...
    def tick(self, *, conflict_clear: bool) -> None: ...
    def is_green_for(self, direction: str) -> bool: ...
    def start_next_cycle(self, plan: SignalPlan, *, conflict_clear: bool) -> None: ...
    def to_signal_snapshot(self) -> SignalSnapshot: ...

    @property
    def current_segment_code(self) -> str: ...
    @property
    def remaining_s(self) -> int: ...
    @property
    def cycle_complete(self) -> bool: ...
    @property
    def in_error(self) -> bool: ...
    @property
    def clearance_hold_s(self) -> int: ...
```

Constructor validates Config and a fresh, unconsumed plan; matching budget/min,
yellow/all-red and cycle_no >=1. Initial cycle_no must be 1. Require actual bool
conflict_clear=True before initial GREEN; otherwise reject with ValueError and
do not start movement. Engine checks occupancy before construction.
Copy Config through Config.from_dict(config.to_dict()). Clone plan from public
green_ns_s/green_ew_s/yellow_s/all_red_s/cycle_no values after verifying it is fresh;
never consume caller's mutable deque cursor. Caller changes cannot alter a cycle.

Properties are read-only. remaining_s is nominal seconds left, >=0; hold shows 0.
clearance_hold_s is total extra ALL_RED seconds in the current cycle, reset only
when a new plan is accepted. A separate private counter tracks each contiguous
hold for timeout. No new public counter is required.

tick consumes exactly one completed logical second, not dt_s or wall time. It
returns None; inspect properties or request a detached SignalSnapshot afterwards.
is_green_for accepts N/S/E/W only (TypeError for non-string, ValueError for other
strings), returns False during yellow/red, completed cycles and ERROR. It does
not apply startup_delay_s, headway_s or spacing rules.

start_next_cycle accepts only after cycle_complete and outside ERROR, with
conflict_clear=True and plan.cycle_no exactly previous +1; it validates/clones
before replacing state, resets counters and starts NS_GREEN with full duration.
No implicit next cycle, reset, automatic retry or Adaptive call exists here.

Wrong object/bool types: TypeError. Invalid values or plan/config mismatch:
ValueError. tick after completion/ERROR or starting a cycle at the wrong lifecycle
point: RuntimeError, without changing state. Snapshot reads remain permitted.
Validate inputs before countdown/cursor/counter mutation.
These lifecycle/error choices require approval (R1/R4).

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
Nominal total = green_budget_s + 2*yellow_s + 2*all_red_s. Defaults give 68s;
21/39 gives [21,3,1,39,3,1]. Actual cycle time adds both holds and no startup
extension: startup is inside the green interval, not added to the plan.

## 5. Tick ordering and clock ownership — PROPOSED

Engine owns t and calls Controller at the end of [t,t+1), after moving all
substeps under the signal that was active at t. With dt_s=0.2 there are five
substeps; other valid Config dt values use round(1/dt_s) steps.
Arrivals are sampled once per direction per logical second, never per substep.
Engine then samples Movement's conflict status at t+1, calls tick, advances
sim_time and constructs a synchronized snapshot. New signal applies to the next
interval; no extra second of GREEN and no retroactive crossing permission.
Pause/read snapshot/UI reruns do not call tick. Step runs exactly one interval.

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
checks cycles_to_run before calculating a fresh plan from current Queue lengths.
If continuing, start_next_cycle can run at the same boundary, without a movement
step or time increment. Snapshot then describes the new cycle at that same time;
the previous cycle metrics must already be recorded (R4).

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

## 7. Integration and snapshot adaptation

Adaptive Algorithm → SignalPlan → TrafficLightController → SimulationEngine →
SignalSnapshot (inside SimulationSnapshot) → UI. This is the data flow; engine
orchestrates plan creation and calls Controller, rather than Controller driving
the engine. Queue snapshot uses len(N)+len(S), len(E)+len(W), excludes active
crossings, and is captured once at cycle start. Example allocation:
allocate_green_adaptive(11,21,60,10) returns (21,39), then
SignalPlan.from_config(config,21,39,cycle_no=1) on main.

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

All rows are **PLANNED** for tests/test_controller.py; no Controller test is
implemented or claimed PASS by this documentation change. Tests can drive a
controller using scripted booleans without a real MovementEngine.

| ID | Test / acceptance |
| --- | --- |
| C01 | Construct fresh valid Config/plan, clear=True: NS_GREEN, 21, not complete/error; detached inputs |
| C02 | Exact six segment order and full-duration transition boundaries listed above |
| C03 | Countdown changes once per tick; reads/is_green_for do not mutate time |
| C04 | 68 ticks complete 21/39 cycle with no hold; custom yellow/all-red use Config |
| C05 | Every observable state: never both axes GREEN; invalid directions rejected |
| C06 | Yellow/all-red permission False for all directions; Movement integration separately verifies no crossing |
| C07 | Red nominal expiry occupied: zero remaining and zero extra elapsed; following ticks accumulate hold |
| C08 | Clearance at/below limit releases; above limit errors even if newly clear; fractional 2.5 limit covered |
| C09 | Holds on both red segments: cycle total accumulates, contiguous timeout counter resets at release |
| C10 | Final red occupied does not complete; clear completes once; no automatic plan loop |
| C11 | New plan only after safe completion, cycle_no+1, counters reset; reject premature/reused/mismatched plan atomically |
| C12 | All six SignalSnapshots validate, especially yellow phase mapping; terminal/error all-red accepted |
| C13 | Reject wrong Config/plan/bool types, invalid durations/config, nonfresh cursor; no partial mutation |
| C14 | tick after ERROR/completion rejected; snapshot remains readable and stable |
| C15 | Engine integration: end-of-interval occupancy, pause/step, new-cycle metrics/snapshot boundary, already-crossed motion |
| C16 | Constructor nonclear rejects start; enabled=False policy tested after R5 resolution |

Existing algorithm/Config/snapshot tests verify only their own implemented
components. Their PASS does not prove Controller, 68-second ticking, clearance,
Movement or Engine integration. No test is added, skipped or weakened here.

## 9. Review questions and approval gate

| ID | NEEDS REVIEW | Owner |
| --- | --- | --- |
| R1 | Constructor takes Config + plan + initial clearance; defensive plan copy, fresh cursor checks and initial cycle_no=1 | Việt Xô + Models owner |
| R2 | Yellow snapshot adapter preserves distinct meanings of active_phase without changing Models | Models owner + Việt Xô |
| R3 | Timeout > limit, contiguous hold, sampled-second precision and timeout precedence | Việt Xô + Vĩ |
| R4 | End-of-interval tick, terminal all-red, same-boundary new plan/snapshot and lifecycle RuntimeErrors | Việt Xô + Vĩ |
| R5 | Reliable occupancy, missing physical width, enabled=False safety and startup/headway ownership | Vĩ + Việt Xô |
| R6 | Integrate Models SignalPlan dependency from main through team's Git review workflow before coding; do not treat this contract as that integration | Models owner + team |

## Review & Approval

**DRAFT — AWAITING REVIEW**

- [ ] Việt Xô review Controller API và logic chuyển pha.
- [ ] Vĩ review cách tích hợp SimulationEngine/MovementEngine.
- [ ] Người phụ trách Models xác nhận khả năng tương thích.
- [ ] Các vấn đề NEEDS REVIEW được giải quyết.
- [ ] Nhóm thống nhất contract.
- [ ] Contract được APPROVED.

Only reviewers can resolve these decisions and approve the contract. This task
ends after documentation, push and PR preparation; no official Controller code.

# Hợp đồng hình học 2D và SimulationSnapshot

Cập nhật 18–19: xem [core_day18_19.md](core_day18_19.md). Các quyết định dưới đây
về width/hình bao/biên đã được hiện thực; bảng Task 4 còn lại là lịch sử.

Cập nhật đến 17/10: hai engine, Controller và Statistics đã hiện thực trên
feat/simulation; xem [hợp đồng runtime ngày 17](simulation_day17.md) và
[hợp đồng Controller](controller_contracts.md). Các trạng thái Task 4 bên dưới
ghi lại mốc thiết kế trước implementation; ví dụ JSON vẫn là fixture tĩnh.

## 1. Mục tiêu và phạm vi Task 4

**Quyết định interface nhóm ngày 15/10/2026:** trực tiếp gọi
`geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m)` khi cần tọa độ.
Bỏ `Vehicle.to_xy()` và hàm độc lập `core.geometry.to_xy()`. Đây là
**điều chỉnh public API so với thiết kế V2.3 gốc**, không thay đổi toán học
hình học V2.3. Các nhánh Models/Simulation/UI phải nhận cập nhật này.

Task 4 thuộc mốc thiết kế **12/10/2026**, được thực hiện ngày **13/10/2026**.
Chốt tọa độ N/S/E/W, Geometry, snapshot chỉ đọc và dữ liệu mẫu để nhóm UI có
thể phát triển renderer trước khi có engine. Phần đã hiện thực chỉ gồm hình học
tĩnh, các DTO bất biến, chuyển JSON và kiểm thử những phần này.
MovementEngine, SimulationEngine, động học, Poisson, Adaptive, clearance guard
và renderer thời gian thực **chưa được hiện thực hoặc tích hợp trong Task 4**.

Nguồn đối chiếu: tài liệu **Thiết kế hệ thống smart traffic light**, hồ sơ
D2.3/V2.3, ngày 12/10/2026, tại
`Traffic Light Signal Simulation/Thiết kế hệ thống smart traffic light.docx`
trong workspace. Đã đọc mục **6.2–6.4, 8.6–8.12, 9.5, 10.4–10.7**; mục 8.1–8.3
bổ sung lịch sáu đoạn và quy ước cycle_index bắt đầu từ 1.
Mọi chi tiết vượt mức quy định của tài liệu được ghi **ĐỀ XUẤT THIẾT KẾ**.
Mục 6.2 còn một đoạn văn V1 nói không đưa vị trí/vận tốc vào Vehicle, trong khi
bảng trường 2D và mục 8.7–8.9 yêu cầu chúng. Hợp đồng này theo phần 2D hiện hành;
không sửa tài liệu gốc hoặc hiện thực Vehicle trong Task 4.

## 2. Hệ tọa độ thế giới và hiển thị

Tâm ngã tư `(0, 0)`, **+x hướng Đông, +y hướng Nam**, đơn vị mét. Xe chỉ đi
thẳng, mỗi hướng xuất phát có một làn vào riêng. `(x, y)` trong snapshot là tọa
độ **đầu xe**, không phải tâm xe hoặc pixel. Models, Core và UI giữ cùng hệ trục.

Renderer đặt Bắc ở phía trên và Nam ở phía dưới: nếu thư viện hiển thị mặc định
y dương đi lên, đảo chiều trục hiển thị; không đổi dấu y trong dữ liệu Core.
Phép biến đổi mét sang pixel/đơn vị màn hình thuộc UI, không đưa trở lại Geometry.
Tâm thân xe là `front - (length_m / 2) * d`, đuôi xe là `front - length_m * d`.

## 3. Vector bốn hướng

| Origin | Xe đi từ → đến | Vector d | Trục thay đổi khi s tăng |
| --- | --- | --- | --- |
| N | Bắc → Nam | (0, +1) | y tăng |
| S | Nam → Bắc | (0, -1) | y giảm |
| E | Đông → Tây | (-1, 0) | x giảm |
| W | Tây → Đông | (+1, 0) | x tăng |

Không đảo vector khi xe qua tâm ngã tư. `origin` giữ nguyên cả khi xe đi trên
đoạn đường ra khỏi ngã tư. Bảng vector có một nguồn thực thi ở `core/geometry.py`.

## 4. s_front_m và crossing

`s_front_m: float` là vị trí dọc làn của đầu xe, gốc tại vạch dừng của hướng đó.

| Giá trị | Ý nghĩa hình học |
| --- | --- |
| s < 0 | Đầu xe trước vạch |
| s = 0 | Đầu xe đúng trên vạch |
| s > 0 | Đầu xe sau vạch |

**Làm rõ điểm biên:** mục 8.7 dùng s >= 0 cho xe vượt vạch và mã giả mục 8.11
phát CrossingEvent khi `old_s < 0 <= new_s`. Tọa độ s=0 tự nó không cấp quyền đi:
engine chỉ ghi crossing khi GREEN, startup delay/headway hợp lệ và xe là đầu FIFO.
`crossed_stop_t` là căn cứ sự kiện đã xảy ra. Tại đúng s=0, ownership tùy sự kiện,
không suy ra chỉ từ tọa độ; trong snapshot biểu diễn bằng motion_state.
Khởi tạo hàng chờ ở s=-stop_margin_m, không tự đánh dấu crossing ở lúc enqueue.
Phương thức `Geometry.lane_to_xy()` không xét đèn hoặc thay đổi trạng thái crossing.

## 5. Công thức ánh xạ

```text
(x, y) = (x_stop, y_stop) + s_front_m * d
N: (x_lane_N, y_stop_N + s)
S: (x_lane_S, y_stop_S - s)
E: (x_stop_E - s, y_lane_E)
W: (x_stop_W + s, y_lane_W)
```

Không clamp s vào vùng nhìn thấy. Queue dài có thể tạo tọa độ ngoài viewport;
Vehicle vẫn tồn tại, vẫn được cập nhật và vẫn được tính vào nhu cầu pha.

## 6. Tâm làn, vạch dừng và tham số

| Tham số Geometry | Mặc định | Vai trò |
| --- | --- | --- |
| intersection_width_m | 16,0m | Bề rộng vùng giữa giao lộ |
| approach_visible_m | 60,0m | Chiều dài tiếp cận được vẽ trước vạch |
| vehicle_length_m | 4,5m | Chiều dài xe mặc định, dùng cho đuôi/hình bao/gap |
| min_gap_m | 2,0m | Khoảng trống tối thiểu theo cùng làn |
| stop_margin_m | 0,5m | Đầu xe dừng ở s <= -0,5 khi không được crossing |
| lane_offset_m | 2,0m | **ĐỀ XUẤT THIẾT KẾ**: khoảng lệch tâm làn khỏi trục |
| vehicle_width_m | None | **ĐỀ XUẤT THIẾT KẾ**: tham số bề rộng chưa được nhóm chốt |

Năm giá trị đầu từ V2.3; đây là tham số mô phỏng học thuật, không phải chuẩn
an toàn giao thông thực địa. Width/approach/length phải >0, gap/margin >=0,
các giá trị hữu hạn. Offset phải >0 và < intersection_width_m/2; width nếu
được cung cấp phải >0. Bool hoặc kiểu không phải int/float bị từ chối.

**ĐỀ XUẤT THIẾT KẾ:** đặt vạch dừng tại biên hình vuông, tâm làn lệch đối xứng
theo quy ước bên phải. Gọi a = width/2 và o = lane_offset:

| Hướng | Tâm làn | Stop point (x_stop, y_stop) | Mặc định |
| --- | --- | --- | --- |
| N | x = -o | (-o, -a) | (-2, -8) |
| S | x = +o | (+o, +a) | (+2, +8) |
| E | y = -o | (+a, -o) | (+8, -2) |
| W | y = +o | (-a, +o) | (-8, +2) |

`stop_margin_m` không dịch vạch dừng: nó là khoảng chừa của đầu xe trước vạch.
Ví dụ N đứng đèn đỏ ở s=-0,5 có đầu xe (-2, -8.5), không phải (-2, -8).
Các số ±2 và ±8 là giá trị của Geometry mẫu, không phải tọa độ bắt buộc của V2.3.

## 7. Vùng xung đột và hình bao

Theo V2.3, vùng giữa giao lộ là hình vuông bề rộng intersection_width_m.
Geometry cung cấp tuple `(x_min, y_min, x_max, y_max)` = `(-a, -a, a, a)`;
mặc định `(-8, -8, 8, 8)`. Đây là **vùng đóng**, chạm biên được đề xuất tính là
còn chiếm vùng khi kiểm tra clearance.

V2.3 yêu cầu kiểm tra hình bao phương tiện, không chỉ kiểm tra đầu xe.
**ĐỀ XUẤT THIẾT KẾ:** hình chữ nhật thẳng theo vector d, từ đầu đến đuôi với
chiều dài `length_m`, bề rộng `vehicle_width_m`. Với vector vuông góc
`n=(-d_y, d_x)`, bốn góc là `front ± width/2*n` và `rear ± width/2*n`.
Do xe chỉ đi thẳng, hình bao luôn thẳng trục, có thể kiểm tra giao hai AABB.

```text
occupied = car_x_min <= region_x_max and car_x_max >= region_x_min
           and car_y_min <= region_y_max and car_y_max >= region_y_min
```

Tương đương mở rộng vùng theo nửa kích thước xe khi kiểm tra tâm thân xe;
không mở rộng vùng lần nữa nếu đã dùng AABB đầy đủ của xe.
Ví dụ N có đầu (-2, 10), dài 4,5m thì đuôi (-2, 5.5) vẫn trong vùng:
đầu xe ra khỏi vùng chưa đủ để cấp xanh đối diện.

**Bề rộng vật lý đã chốt 1,8m ngày 19/10/2026.** Geometry() giữ default
None cho metadata/API lịch sử; Geometry.for_motion(motion) truyền rõ 1.8m vào
Core và Snapshot. Không thêm key JSON V2. Giao lộ phải >=3.6m để đủ hai làn;
offset=min(2m, width/4), đảm bảo thân xe nằm trong phần đường mỗi hướng.
Config và JSON Schema được đồng bộ miền này. Thiếu width thì kiểm tra hình
bao báo lỗi, không tự coi vùng trống. Không lấy bề rộng biểu tượng UI làm vật lý.

Movement.is_conflict_clear chỉ True khi mọi hình bao active đã ra khỏi vùng đóng.
Xe active đã qua vùng nhưng chưa EXITED không giữ đỏ. Test vật lý ở
`tests/test_physics_day18.py` và thí nghiệm cùng horizon đã thực thi.

## 8. Hợp đồng Geometry.lane_to_xy

Các public API đã hiện thực:

```text
Geometry(...)                         # frozen dataclass, đơn vị mét
geometry.stop_point(direction) -> tuple[float, float]
geometry.conflict_bounds              # tuple[float, float, float, float]
geometry.to_snapshot() -> GeometrySnapshot
geometry.lane_to_xy(origin: str, s_front_m: float) -> tuple[float, float]
```

Direction chỉ nhận N/S/E/W; "X", chữ thường và giá trị thiếu gây ValueError.
s nhận int/float hữu hạn, không nhận bool; kiểu sai gây TypeError, NaN/inf gây
ValueError. Gọi trực tiếp trên đối tượng Geometry. Kết quả là tuple hai float bằng mét.
Hàm thuần: cùng đầu vào cho cùng kết quả, không đổi s, Vehicle, Queue, tín hiệu
hoặc viewport. Geometry không sinh Poisson, tính xanh, điều khiển đèn hay ghi file.

Ví dụ cho Geometry mặc định (**tọa độ minh họa được đề xuất**):

| Hướng | Stop point | Tâm làn | s=-10 | s=0 | s=10 |
| --- | --- | --- | --- | --- | --- |
| N | (-2,-8) | x=-2 | (-2,-18) | (-2,-8) | (-2,2) |
| S | (2,8) | x=2 | (2,18) | (2,8) | (2,-2) |
| E | (8,-2) | y=-2 | (18,-2) | (8,-2) | (-2,-2) |
| W | (-8,2) | y=2 | (-18,2) | (-8,2) | (2,2) |

Khi width=20, offset=3, `geometry.lane_to_xy("N", -4)` = (-3,-14).
Chỉ có một implementation chuyển tọa độ. Core/MovementEngine gọi trực tiếp
`geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m)`; Vehicle không chứa
`to_xy()` hay công thức hình học. Không duy trì wrapper thứ hai.

## 9. SimulationSnapshot và nguồn định nghĩa

Nguồn định nghĩa duy nhất: `src/models/snapshot.py`. Đây là DTO giá trị, không
phải Engine, Lane hoặc Vehicle nghiệp vụ. Core tạo một snapshot đồng bộ tại cuối
tick hoặc từ trạng thái đã khởi tạo; UI không yêu cầu snapshot trước khởi tạo.

**Tối thiểu theo mục 10.7 V2.3:** danh sách xe có id/x/y/speed/state, signals,
metrics và chỉ đọc. Các tên trường Python cụ thể, schema v1, cấu trúc DTO dưới
đây và metadata hình học đều là **ĐỀ XUẤT THIẾT KẾ Task 4** để thống nhất API.

| Trường SimulationSnapshot | Kiểu | Ý nghĩa |
| --- | --- | --- |
| schema_version | int, đúng 1 | Phiên bản API snapshot, độc lập junctions.json v2 |
| sim_time | int >=0 | Giây mô phỏng tại ranh giới tick, không phải giờ hệ điều hành |
| cycle_index | int >=1 | Chu kỳ hiện tại, bắt đầu từ 1 theo mục 8.3 |
| session_state | Literal | RUNNING, PAUSED, STOPPED, COMPLETED hoặc ERROR |
| geometry | GeometrySnapshot | Metadata tĩnh để renderer dựng đường |
| signals | SignalSnapshot | Đoạn tín hiệu và timer ở cùng thời điểm snapshot |
| metrics | MetricsSnapshot | Counters và Queue hiện tại |
| vehicles | tuple[VehicleSnapshot, ...] | Tất cả xe chưa EXITED, kể cả Queue ngoài viewport |

Không có session IDLE trong schema v1 này: trước khởi tạo UI hiển thị chưa có
snapshot; khi bắt đầu thì cycle_index=1. Không phụ thuộc thứ tự tuple vehicles
để xử lý FIFO; renderer dùng ID và tọa độ. Snapshot không cung cấp thao tác pop.

## 10. Hợp đồng các DTO thành phần

| DTO | Trường và kiểu | Định nghĩa |
| --- | --- | --- |
| GeometrySnapshot | intersection_width_m, approach_visible_m, lane_offset_m: float; vehicle_width_m: float hoặc None | Bản sao metadata từ Geometry; không chứa tham chiếu engine |
| VehicleSnapshot | vehicle_id: str, origin: Literal N/S/E/W | ID không rỗng, không trùng trong snapshot; hướng xuất phát |
| VehicleSnapshot | x, y, s_front_m, speed_mps, length_m: float | Mét; speed>=0; length>0; tất cả hữu hạn |
| VehicleSnapshot | motion_state: Literal APPROACHING/STOPPED/CROSSING | Hai trạng thái đầu thuộc Queue, CROSSING thuộc active; EXITED không nằm trong vehicles |
| SignalSnapshot | current_segment: str | NS_GREEN, NS_YELLOW, ALL_RED_1, EW_GREEN, EW_YELLOW, ALL_RED_2 |
| SignalSnapshot | active_phase: Literal NS/EW hoặc None | Pha của đoạn GREEN/YELLOW; None ở ALL_RED; không tự cấp quyền crossing |
| SignalSnapshot | remaining_s: int >=0 | Thời gian danh định còn lại của đoạn; có thể 0 khi clearance hold |
| SignalSnapshot | signal_colors: Mapping[Direction, SignalColor] | Đúng N/S/E/W; GREEN/YELLOW/RED khớp đoạn |
| MetricsSnapshot | queue_lengths: Mapping[Direction, int] | Số xe chưa crossing theo từng hướng, bao gồm xe đang tiến tới |
| MetricsSnapshot | initial_total, total_arrivals: int >=0 | Xe ban đầu và xe mới đến lũy kế phiên |
| MetricsSnapshot | crossed_stop_total, exited_world_total: int >=0 | Hai sự kiện khác nhau, lũy kế phiên |
| MetricsSnapshot | active_crossing_count: int >=0 | Xe đã crossing, chưa EXITED, hiện vẫn trong thế giới |
| MetricsSnapshot | clearance_hold_s: float >=0 | Tổng giây giữ ALL_RED bổ sung của chu kỳ hiện tại; reset ở chu kỳ mới |

Danh sách xe phải khớp queue_lengths và active_crossing_count. Counters phải giữ
`initial_total + total_arrivals = sum(queue_lengths) + crossed_stop_total` và
`crossed_stop_total = active_crossing_count + exited_world_total`.
ERROR phải có bốn đèn đỏ. NS/EW không được cùng GREEN. Trong YELLOW, active_phase
vẫn chỉ pha của đoạn, nhưng xe mới không được crossing.
Lỗi kiểu giá trị số gây TypeError; giá trị sai, trùng ID, counters/đèn không nhất
quán gây ValueError. Đối chiếu x/y với Geometry thuộc Core builder và kiểm thử
hình học, không import Core vào Models để lặp lại công thức.

## 11. Read-only sâu và chuyển JSON

Các dataclass đều frozen và slots. `vehicles` chuyển thành tuple mới; chỉ nhận
VehicleSnapshot, không nhận Vehicle thực tế hoặc dict mutable.
Các mapping màu/counters được chép thành dict mới, kiểm tra leaf là giá trị
scalar hợp lệ và bọc MappingProxyType. Frozen đơn thuần không đủ cho dict/list.

UI không nhận Lane.queue hay active_crossing; không sửa Vehicle thực tế, timer,
không gọi popleft và không sửa state/time của engine. Builder của SimulationEngine đọc
scalar từ Core rồi tạo DTO; không gắn đối tượng nghiệp vụ vào một trường mới.

`snapshot.to_dict()` tạo dict/list JSON mới, có thể sửa để phục vụ UI mà không
ảnh hưởng snapshot hoặc Core. `SimulationSnapshot.from_dict(data)` đọc JSON v1,
kiểm tra schema/counters, sao chép dữ liệu và không thực thi engine. Không dùng
`dataclasses.asdict` trực tiếp lên root chứa MappingProxyType.

```python
import json
from pathlib import Path
from src.models.snapshot import SimulationSnapshot

data = json.loads(Path("docs/examples/simulation_snapshot_example.json").read_text(encoding="utf-8"))
snapshot = SimulationSnapshot.from_dict(data)
plot_data = snapshot.to_dict()  # x/y/id, metadata đường và màu đèn cho renderer
encoded = json.dumps(plot_data, allow_nan=False)
```

Chỉ phụ thuộc standard library cho Geometry/DTO. Mẫu được đọc để kiểm tra hợp
đồng; việc này không thay thế storage cấu hình hoặc engine đang chạy.

## 12. Queue → active_crossing → exited

Trước crossing: xe thuộc đúng một Lane.queue, giữ FIFO; cả APPROACHING và STOPPED
đều tính vào Queue. Crossing hợp lệ: pop đúng đầu Queue một lần, ghi crossed_stop_t,
tăng crossed_stop_total và chuyển sang active_crossing, không xóa khỏi hình.
Sau crossing, xe không quay lại Queue và tiếp tục chạy trong vàng/all-red.

Khi đuôi xe vượt giới hạn thế giới hiển thị, ghi exited_world_t, xóa khỏi active,
tăng exited_world_total, không tăng crossed lần hai. **ĐỀ XUẤT THIẾT KẾ:** viewport
đối xứng có biên ±(width/2 + approach_visible_m), mặc định ±68m; renderer clip
xe ngoài viewport nhưng không tự thực hiện EXITED. Xe Queue ngoài viewport vẫn
có trong snapshot và counters. Movement đã kiểm tra đuôi xe theo đúng tọa độ thế giới ở cả bốn hướng (test ngày 18).

## 13. min_gap, tín hiệu, clearance và nhịp thời gian

```text
gap = s_front_leader - length_leader - s_front_follower
gap >= min_gap_m - 1e-6
```

Đo trên cùng hướng, tính cả leader đã crossing. Xử lý xe từ đầu đến cuối;
s không giảm. Xe chưa crossing chỉ vượt khi GREEN và đủ startup delay/headway;
khi không đủ điều kiện, đầu xe không đi qua s=-stop_margin_m.
Xe đã crossing bỏ stop_limit và tiếp tục đi ra khỏi vùng, kể cả YELLOW/ALL_RED.

Khi ALL_RED hết danh định mà vùng còn chiếm, giữ đỏ từng tick và tăng
clearance_hold_s. Chỉ cấp GREEN đối diện khi vùng trống. Quá clearance_limit_s
thì ERROR và giữ tất cả đỏ; không cưỡng bức xanh. Hold không làm đổi green_budget
hoặc min_green. Những ràng buộc này đã có code điều khiển và test ngày 18; xem tài liệu Core mới.

Một tick logic 1 giây gồm 5 substep × 0,2 giây. Poisson gọi một lần mỗi hướng
mỗi tick, không gọi lại trong substep hoặc khi UI rerun. Pause không chạy tick;
Step +1s chạy đúng 5 substep. Snapshot lấy sau khi vị trí, ownership, signals
và metrics cùng được chốt cho một thời điểm. `snapshot()` không tự tiến thời gian.

## 14. Snapshot minh họa

File `docs/examples/simulation_snapshot_example.json` là **dữ liệu dựng thủ công**,
không phải kết quả thực nghiệm hoặc sản phẩm của SimulationEngine.
Thời gian 20s, chu kỳ 1, RUNNING, NS_GREEN còn 20s: N/S xanh, E/W đỏ.
Có thể dùng lịch minh họa NS 40s, EW 20s với nhu cầu ban đầu NS=2, EW=1;
Task 4 không gọi Adaptive để sinh mẫu này.

| ID | Hướng / trạng thái | s | Đầu xe (x,y) |
| --- | --- | --- | --- |
| V-N-001 | N, APPROACHING | -10 | (-2,-18) |
| V-S-001 | S, APPROACHING | -6 | (2,14) |
| V-E-001 | E, STOPPED | -0,5 | (8.5,-2) |
| V-W-001 | W, STOPPED | -0,5 | (-8.5,2) |
| V-N-002 | N, CROSSING | 11 | (-2,3), trong vùng giao lộ |

Queue mỗi hướng 1, active=1, crossed=3, exited=2, initial=3, arrivals=4.
Bảo toàn: 3+4=4+3 và 3=1+2. Hai xe exited không có trong danh sách.
Gap N = 11-4,5-(-10)=16,5m >=2m. ID không trùng, tọa độ khớp Geometry,
không có xe cùng lúc ở Queue và active. Snapshot chưa chứng minh lịch sử chuyển
động hoặc khoảng cách ở mọi substep; chỉ chứng minh tính nhất quán của mẫu.

## 15. Bảng kiểm thử

| Mã | Tình huống / expected | Trạng thái phạm vi Task 4 |
| --- | --- | --- |
| G-01 | N: s âm phía Bắc vạch; s tăng làm y tăng | Test Geometry.lane_to_xy |
| G-02 | S: s âm phía Nam vạch; s tăng làm y giảm | Test Geometry.lane_to_xy |
| G-03 | E: s âm phía Đông vạch; s tăng làm x giảm | Test Geometry.lane_to_xy |
| G-04 | W: s âm phía Tây vạch; s tăng làm x tăng | Test Geometry.lane_to_xy |
| G-05 | direction X → ValueError | Test Geometry.lane_to_xy |
| G-06 | Sửa field, tuple, mapping bị chặn; sửa input/export không đổi DTO | Test DTO đã hiện thực, không phải engine |
| G-07 | ID trùng → ValueError | Test DTO đã hiện thực |
| G-08 | Queue/active rời nhau, counters khớp mẫu | Test dữ liệu mẫu đã hiện thực |
| G-08 động | Crossing chỉ pop một lần; active rồi EXITED; không quay lại Queue | **CHƯA THỰC THI**, cần engine |
| G-09 tĩnh | Công thức gap của cặp xe N mẫu cho 16,5m | Test dữ liệu mẫu, không chứng minh động học |
| G-09 động | Gap >= min-1e-6 trong mọi substep, kể cả leader đã crossed | **CHƯA THỰC THI**, cần engine |
| G-10 | Snapshot NS và EW cùng GREEN → ValueError | Test DTO đã hiện thực |
| G-11 | JSON hợp lệ, schema và kiểu đúng, roundtrip không mất dữ liệu | Test DTO đã hiện thực |
| G-12 | Geometry width=20, offset=3; N s=-4 →(-3,-14) | Test không hard-code hình mẫu |
| G-13 | s NaN/inf, kiểu sai; Geometry âm/zero không hợp lệ | Test validation đã hiện thực |
| G-14 | Đầu xe ra vùng, đuôi còn trong vùng → không clear | Đã có test vật lý ngày 18 (xem core_day18_19.md) |
| G-15 | ALL_RED hold khi vùng chưa trống, timeout giữ ERROR/all-red | Đã có test Controller/Engine ngày 18 |
| G-16 | Pause đứng yên, Step một lần Poisson + năm substep | **CHƯA THỰC THI**, cần engine |

Test tương lai chỉ được ghi expected trong tài liệu, chưa được tính PASS hoặc
SKIP của pytest. Không tạo fixture giả để làm test xanh. Kết quả pytest thực tế
được báo cáo riêng sau khi chạy. Task 3 còn trên feat/algorithm, không merge
nhánh thuật toán vào feat/simulation để đưa thay đổi ngoài Task 4 vào commit.

```powershell
uv sync
uv run pytest
uv run python -m compileall -q src tests
git diff --check
git status
```

Workspace còn bản clone lồng `SmartTrafficLight/SmartTrafficLight/`; nếu pytest
quét cả hai bộ test trùng tên, dùng `uv run pytest --ignore=SmartTrafficLight`.
Trên checkout sạch, dùng lệnh pytest thông thường. Không xóa bản clone trong Task 4.

## 16. Công việc ngày 16–18/10 và quyết định cần review

- Review **ĐỀ XUẤT THIẾT KẾ**: offset 2m, vạch tại biên giao lộ, viewport ±68m,
  bề rộng xe cần bổ sung, schema snapshot v1 và các field/enum cụ thể.
- Hiện thực Vehicle/Lane và builder đọc scalar để tạo DTO; cập nhật x/y bằng
  Geometry.lane_to_xy duy nhất. Đảm bảo snapshot đồng bộ và không lộ tham chiếu mutable Core.
- Hiện thực MovementEngine: front→back, gia tốc, stop_limit, gap, startup/headway,
  CrossingEvent/ExitedEvent đúng một lần; thêm test G-08/G-09 động.
- Chốt width rồi hiện thực AABB, is_conflict_clear và clearance hold/timeout.
- Hiện thực SimulationEngine tick 1s, năm substep, kết nối thuật toán Task 3
  và kế hoạch tín hiệu sau khi các PR tương ứng được review/merge.
- Nhóm UI đọc DTO hoặc to_dict để dựng đường/xe; renderer không làm nghiệp vụ,
  không dùng JSON mẫu để giả vờ đang chạy mô phỏng thực.
- Chạy test tích hợp trạng thái, gap, clearance, Pause/Step/Reset và bảo toàn xe.

Danh sách trên là kế hoạch lịch sử. Bề rộng 1.8m đã được người dùng chốt;
trạng thái hiện tại và API mới nằm trong core_day18_19.md.

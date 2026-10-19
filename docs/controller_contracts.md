# Controller API Contract V2.3

Trạng thái: **Controller đã hợp nhất vào main; Core tiếp tục đến task 18–19**.
Nguồn Controller duy nhất là `src/core/controller.py`; không duy trì bản riêng
cho Simulation. Xem [Core ngày 18–19](core_day18_19.md) cho policy/replay/physics.

Tài liệu thay thế draft ngày 15/10. Căn cứ: Thiết kế hệ thống D2.3/V2.3,
§§7.3, 8, 9, 10 và hợp đồng Models/Snapshot hiện có trên main.
Kết quả pytest phải lấy từ lần chạy ở head PR, không dùng số test lịch sử.

## 1. Trách nhiệm

- Algorithms: Poisson và hàm thuần `allocate_green_adaptive`; không điều phối đèn.
- Controller: demand/utilization, gọi Adaptive, xây SignalPlan, countdown,
  chuyển sáu đoạn và cung cấp SignalSnapshot. Không sinh xe, pop Queue, ghi file
  hoặc gọi Streamlit.
- SimulationEngine: nguồn thời gian phiên và cycle_index, RNG/Poisson,
  điều phối Movement, thống kê và chuyển chu kỳ.
- MovementEngine: vị trí/vận tốc, crossing, startup/headway và occupancy.
- Models: Config/validation, Lane FIFO, SignalPlan một chu kỳ, DTO bất biến.

## 2. Public API đã có

```python
TrafficLightController(config: Config, *, policy='adaptive')
controller.compute_phase_demand(queue_lengths) -> tuple[int, int]
controller.compute_utilization(q_ns, q_ew, prev_green) -> dict[str, float]
controller.build_cycle_plan(queue_lengths, *, cycle_no) -> SignalPlan
controller.start_next_cycle(queue_lengths, *, cycle_no, started_at, conflict_clear=True)
controller.tick(*, conflict_clear=True)
controller.is_green_for(direction) -> bool
controller.to_signal_snapshot() -> SignalSnapshot
```

Thuộc tính chỉ đọc: `config` (bản sao), `current_segment_code`, `remaining_s`,
`cycle_complete`, `in_error`, `clearance_hold_s`, `cycle_no`, `elapsed_s`,
`last_utilization` (bản sao). elapsed_s là số interval Controller đã nhận,
không phải nguồn đồng hồ phiên thứ hai; Engine truyền started_at đúng boundary.

Direction counts có đúng N/S/E/W, int không âm, không bool/float/string.
Không áp giới hạn 100 của initial_queue lên Queue trong phiên.
Config được validate và sao chép; các caller không đổi cấu hình giữa chu kỳ.
Sai kiểu gây TypeError, sai miền ValueError, sai vòng đời RuntimeError.

## 3. Demand, Adaptive và lịch sáu đoạn

Demand: q_ns=N+S, q_ew=E+W, chỉ xe còn Queue.
Utilization báo cáo: eta_ns=q_ns/prev_ns, eta_ew=q_ew/prev_ew,
eta_bar=(q_ns+q_ew)/budget. Chu kỳ đầu dùng previous green chia gần đều;
chu kỳ sau dùng cặp xanh của lịch vừa hoàn tất. Utilization không sửa Adaptive.

Controller gọi `algorithms.allocate_green_adaptive` rồi
`SignalPlan.from_config(config, g_ns, g_ew, cycle_no)`.
`build_cycle_plan` chỉ preview tại boundary; Engine sản xuất chỉ gọi
`start_next_cycle`, tránh gọi Adaptive hai lần cho một lần kích hoạt.

| Đoạn | Thời gian mẫu | Quyền crossing |
| --- | ---: | --- |
| NS_GREEN | 21 | N/S, còn phải qua guard của Movement |
| NS_YELLOW | 3 | Không có |
| ALL_RED_1 | 1 tối thiểu | Không có |
| EW_GREEN | 39 | E/W, còn phải qua guard của Movement |
| EW_YELLOW | 3 | Không có |
| ALL_RED_2 | 1 tối thiểu | Không có |

Với Queue 7/4/16/5, tổng danh định 68 giây. Không có hold: boundary ở
0 NS_GREEN/21; 21 NS_YELLOW/3; 24 ALL_RED_1/1; 25 EW_GREEN/39;
64 EW_YELLOW/3; 67 ALL_RED_2/1; 68 ALL_RED_2/0 và cycle_complete.
Duration vàng/đỏ lấy Config, không hard-code 68 cho cấu hình khác.
Không thay plan giữa chu kỳ, không tự quay vòng deque sau ALL_RED_2.

## 4. Tick, chu kỳ và thống kê

Trong [t,t+1), Engine lấy Poisson theo N/S/E/W và chạy các substep với tín hiệu
ở t. Sự kiện crossing ghi cuối substep t_sub+dt. Sau chuyển động, Engine cập
nhật counters, lấy occupancy và gọi Controller.tick một lần; sim_time trở thành
t+1. Snapshot/tín hiệu/metrics cùng timestamp boundary mới.

Khi ALL_RED_2 hoàn tất, Engine chốt metrics chu kỳ trước. Nếu đủ cycles_to_run,
giữ terminal red, state COMPLETED và không gọi Adaptive thêm. Nếu còn, đọc
Queue mới, truyền cycle_no+1/started_at vào Controller và chỉ cập nhật cycle_index
sau activation thành công. Lỗi activation phải dừng ở ERROR an toàn.

Engine thông báo Lane.reset_green_clock đúng một lần ở entry GREEN; tắt clock
khi rời GREEN và giữ lịch sử crossing cuối của làn qua các pha/chu kỳ.
Entry GREEN chờ cả `green_start + startup_delay_s` và
`last_crossed_at + headway_s` (nếu đã có crossing). Reset toàn phiên mới xóa
lịch sử. Movement kết hợp signal, startup/headway, vị trí và FIFO.
Controller không trực tiếp sửa Lane. Pause giữ thời gian, Step tiến có kiểm soát
và giữ PAUSED, Reset tạo lại RNG/plan/counters từ bản chốt Config.

## 5. Pha vàng và snapshot

SignalSegment.active_phase=None ở vàng có nghĩa không cấp crossing.
SignalSnapshot.active_phase=NS/EW ở vàng là pha hiển thị. Controller ánh xạ
bằng current_segment code, không chép máy móc active_phase từ Segment.
Màu N/S/E/W được chép sang DTO bất biến. Tất cả sáu snapshot, đặc biệt hai
đoạn vàng và terminal ALL_RED_2, phải validate được.

## 6. Phạm vi clearance và các phần sau 17/10

Controller hiện có cơ chế nhận conflict_clear, giữ ALL_RED tại remaining=0,
đếm hold theo tick và timeout khi contiguous hold vượt clearance_limit_s.
Đây là behavior đang có để không làm hỏng caller; Engine luôn truyền bool
occupancy tường minh, không dựa vào default True khi tích hợp.

Cập nhật 18–19: Movement dùng hình bao đầy đủ, xe rộng 1.8m và kiểm tra
invariants sau substep; occupancy bool luôn được Engine truyền tường minh.
Fixed-Time dùng cùng Controller/guard, chỉ đổi phân bổ xanh. fail_safe() giữ
bốn đèn đỏ khi Engine phát hiện vi phạm bất biến. CSV/dashboard UI để riêng.

## 7. Kiểm thử đến hết 17/10

`tests/test_controller.py` kiểm tra import, Config detached, demand/utilization,
preview không activation, 21/39 đủ 68 tick, duration tùy Config, sáu snapshot,
không xanh đồng thời, vàng/đỏ không cấp crossing, đúng một Adaptive/chu kỳ,
validation đầu vào và activation sai không đổi state.

Test Engine/Movement và counters thuộc PR #15: Poisson một lần mỗi hướng,
năm substep mặc định, FIFO/crossing một lần, Step/Pause/Stop/Reset, seed replay,
đóng chu kỳ và không gọi Adaptive sau Completed.

Formal GitHub approval và test trên bản tích hợp được ghi ở PR; trạng thái
implementation trong tài liệu không thay thế review hay kết quả pytest thực tế.

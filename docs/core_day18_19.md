# Core Algorithms/Simulation — task 18–19/10

Triển khai tiếp từ main `70862b6`, trên nhánh `feat/core-day18-19`. Người dùng
đã chốt bề rộng xe **1.8m** ngày 19/10/2026. Đây là giả định mô phỏng bổ sung
cho thiết kế D2.3/V2.3, không phải kích thước biểu tượng UI hoặc quy chuẩn thực địa.
Phần Core này không triển khai giao diện hay CSV lịch sử của UI.

## 1. Trách nhiệm và tương thích

- Models giữ Config/Vehicle/Lane/SignalPlan và DTO Snapshot hiện có.
- Geometry tính tọa độ, hình bao và biên; Movement sở hữu Queue/active/exited.
- Controller giữ sáu đoạn và guard; hai policy chỉ khác phân bổ green.
- SimulationEngine sở hữu đồng hồ, RNG/replay, vòng đời và chốt dữ liệu.
- Statistics giữ số liệu; comparison/experiment thực hiện đối chứng headless.
- `SimulationEngine(config)` vẫn chạy Adaptive theo `cycles_to_run`.
  Constructor có thêm các keyword tùy chọn, không thay bộ khóa JSON V2.
- Geometry() mặc định width=None được giữ cho metadata/fixture lịch sử;
  Core gọi Geometry.for_motion để truyền rõ width=1.8m. Thiếu width thì
  vehicle_bounds/occupancy báo lỗi, không trả kết quả clear giả.

## 2. Hình học và miền cấu hình

Tâm giao lộ (0,0), +x Đông/+y Nam; s đo từ vạch dừng. Đầu xe=`stop+s*d`,
đuôi=`front-length*d`, bề rộng thân vuông góc vector d là 1.8m.
`Geometry.vehicle_bounds(origin,s,length)` trả AABB `(xmin,ymin,xmax,ymax)`.

Vùng xung đột là hình vuông đóng ±width/2: thân chạm biên vẫn chiếm vùng.
Không mở rộng vùng lần nữa sau khi đã dùng AABB toàn thân. Xe active đã ra
khỏi vùng nhưng chưa ra khỏi thế giới không giữ ALL_RED.

Mỗi trục có hai làn ngược chiều, vì vậy intersection_width_m>=2×1.8=3.6m.
Đây là điều kiện khả thi từ width đã chốt, thay cho việc width=4 hợp lệ với
Config nhưng lỗi vì offset cố định. Config và JSON Schema đều kiểm tra >=3.6;
`lane_offset_m=min(2m,width/4)` bảo đảm thân xe nằm trong nửa đường mỗi hướng.
Mặc định width=16 vẫn có offset=2 như hợp đồng cũ. JSON không thêm field width.

Thế giới có biên ±(width/2+approach_visible_m), mặc định ±68m. EXITED chỉ khi
**toàn bộ đuôi/thân đã ra** theo hướng chạy, không khi đầu xe ra hoặc khi thân
bị clip bởi viewport UI. Ranh giới EXITED là mở: chạm biên chưa EXITED.

## 3. Substep, crossing, dừng và ownership

- Initial queue đứng ở -stop_margin, khoảng cách length+min_gap; đánh dấu là
  xe tồn đầu phiên. Xe Poisson mới sinh phía sau xe cuối cùng cùng hướng,
  xét cả Queue lẫn active, ít nhất ở -approach_visible và trước stop_margin.
- Mỗi tick sinh Poisson một lần/hướng, hoặc lấy đúng một hàng ArrivalTape.
  Mặc định năm substep 0.2s; dt khác phải chia tick thành số bước nguyên.
- Thứ tự cập nhật trước→sau; active đã crossing vẫn đi trong vàng/đỏ.
- Xe mới chỉ crossing khi cuối substep>=arrival_t+1s (TC-23), đúng GREEN,
  là đầu FIFO, đủ startup/headway và tới s>=0. Xe initial không chịu thời
  gian chờ một giây của xe mới; vẫn chịu startup/headway/signal đầy đủ.
- Headway áp dụng giữa hai crossing liên tiếp cùng làn trong toàn phiên,
  kể cả khi chuyển pha/chu kỳ hoặc Queue đã rỗng rồi có xe mới. Lane giữ
  crossing cuối qua vàng/đỏ. Khi vào xanh, đồng hồ đủ điều kiện là
  `max(green_start + startup_delay_s, last_crossed_at + headway_s)`;
  nếu chưa crossing thì chỉ dùng startup. Tắt clock khi rời xanh không
  xóa lịch sử này; chỉ Reset toàn phiên tạo Lane mới và xóa lịch sử.
- Crossing ghi t_sub+dt, pop FIFO đúng một lần và chuyển sang active dict.
  advance_substep trả tuple các crossing mới để Statistics không cộng lại
  mọi xe đã qua vạch ở những tick sau. EXITED tăng exit, không tăng crossing.
- Stopped delay cộng dt nếu xe trước vạch có speed<=0.1m/s (tolerance 1e-9).
  Không cộng sau crossing. Đây là ngưỡng đo của thiết kế, không phải đổi
  công thức chuyển động hoặc cố tình làm speed bằng 0.
- Kiểm tra gap>=min_gap-1e-6, ID/ownership Queue/active/exited trước/sau mỗi
  substep và khi spawn. Engine đối chiếu hai đẳng thức counter sau substep.
  Vi phạm bất biến dừng ERROR, giữ đỏ và phát lại exception để caller biết
  lỗi; không sửa số liệu hoặc tiếp tục chạy để che dữ liệu hỏng. Reset tạo
  phiên mới. Với dữ liệu đã bị can thiệp/hỏng, Snapshot có thể từ chối validate.

Core tiếp tục duy trì gap/clearance khi motion_2d.enabled=False; toggle này
không cho phép bỏ luật an toàn. UI có thể dùng flag để ẩn xe; không có engine
“bỏ vật lý” riêng trong đợt này.

## 4. Clearance và vòng đời

Giữ state machine Controller đã có. Hết ALL_RED danh định, nếu AABB còn giao
vùng thì remaining=0 và giữ đỏ từng giây. Khi clear mới bật đối diện/đóng
chu kỳ. Hold vượt clearance_limit_s thì ERROR/bốn đỏ, kể cả vùng vừa clear
ở tick đã quá giới hạn. Hold nằm ngoài green budget/min_green.

Start/Pause/Resume/Stop/Reset theo hợp đồng ngày 17. PAUSED Step vẫn chạy
đúng tick/substep rồi giữ PAUSED nếu chưa terminal. Reset giữ Config chốt,
policy, ArrivalTape và horizon, khởi tạo lại RNG/IDs/counters/time; gọi Start
để chạy phiên mới. Không thay UI để che quy tắc Reset này.

## 5. Statistics ngày 19

`engine.stats.ticks/cycles` là tuple frozen records; `engine.stats.summary()`
và `engine.summary()` trả dict mới. Summary Engine thêm policy/config_id/seed,
status/error_message/min_gap_violations. Sáu khóa summary cũ vẫn giữ.

| Metric | Quy tắc |
|---|---|
| Initial/arrivals/crossed/active/exited/remaining | Initial+arrivals=remaining+crossed; crossed=active+exited; kiểm tra cả ID/ownership để số đếm không che mất/trùng xe. |
| Avg Queue | Trung bình tổng Queue cuối tick trên đúng số tick đã chạy, không đưa t=0 vào mẫu số. Chưa chạy tick thì None. |
| Max Queue | Lớn nhất trên initial Queue và các mẫu cuối tick. |
| Avg wait departed | Mean(crossed_stop_t-arrival_t) của các ID đã crossing; gồm thời gian tiếp cận, không gọi là thời gian đứng yên. |
| Avg stopped delay | Mean(stopped_delay tại crossing) trên đúng các ID đã crossing. |
| Throughput/min | crossed×60/simulation_seconds; None nếu thời lượng bằng 0. |
| Avg green NS/EW | Trung bình green của các chu kỳ đã hoàn tất; chưa có chu kỳ thì None. |
| Hold toàn phiên | Hold các chu kỳ đã đóng + hold chu kỳ dở; không dùng hold riêng của Controller cuối phiên. |

Hai average delay để None khi chưa crossing. Mỗi crossing chỉ cộng một lần
theo ID; xe còn Queue không được đưa vào mẫu số average departed.
CycleMetrics giữ API cũ và thêm avg_queue_cycle, clearance_hold_s;
actual_cycle_s=end-start, có thể >68. Queue start/end chụp đúng ranh giới.
Chốt chu kỳ trước activation kế tiếp. Stop/ERROR giữ phần đã quan sát, không
tính chu kỳ dở vào cycles_completed. Các metric mới không ghi vào junctions.json.

## 6. Fixed-Time, arrivals replay và cùng horizon

```python
from src.core.arrivals import ArrivalTape
from src.core.simulation import SimulationEngine
from src.models.config import Config

config = Config(seed=42)
tape = ArrivalTape.from_config(config, horizon_s=180)
engine = SimulationEngine(config, policy='fixed', arrival_tape=tape, horizon_s=180)
engine.start()
engine.run_ticks(180)
print(engine.summary())
```

Fixed-Time: green_NS=budget//2, green_EW=budget-green_NS; mặc định 30/30,
budget lẻ lệch 1s. Kiểm tra integer/budget>=2*min_green như Adaptive.
Hai policy dùng cùng Controller sáu đoạn, yellow/all-red/startup/headway,
Movement và guard; Fixed-Time không bỏ hold để ép đúng 68s.

ArrivalTape là tuple các hàng N/S/E/W không âm kiểu int, được tách khỏi input
mutable. from_config sinh trước H hàng bằng Poisson/RNG hiện có. Hai Engine
cùng đọc bảng này, không tự lấy RNG riêng khi replay. Test đối chiếu từng
tick/hướng qua các Vehicle thật, không chỉ so tổng arrivals.

`horizon_s` là ngân sách quan sát riêng, không lấy cycles_to_run×68. Khi được
truyền, Engine bỏ điều kiện dừng theo số chu kỳ, chạy đủ H hoặc dừng ERROR.
Đủ H thì STOPPED; chu kỳ vừa hoàn tất vẫn chốt, chu kỳ dở không tính completed.
Không activation thêm khi H trùng cuối chu kỳ. Không truyền horizon thì giữ
chu kỳ và trạng thái COMPLETED như API cũ. Replay yêu cầu đủ hàng cho H.

`compare_policies(config,H)` tạo một Tape, trả ComparisonResult bất biến với
hai PolicyResult. Summary trong kết quả là mapping chỉ đọc, to_dict trả dữ liệu
tách biệt. comparable chỉ True nếu cả hai chạy đủ H và không ERROR. Thí nghiệm
ERROR không được đưa vào mean/std như một cặp chạy đủ thời gian.

## 7. Chạy, kiểm thử và phạm vi nghiệm thu

```bash
uv run pytest
uv run python -m src.core.experiment --horizon 180 --output reports/comparison.json
```

experiment chạy 6 kịch bản: empty, balanced, ns_heavy, ew_heavy, peak và
clearance (xe chậm), mặc định seed 0–9. Có 60 cặp/120 phiên. JSON lưu từng
seed và mean/population_std của các cặp comparable; average chưa có mẫu
giữ None cùng samples=0. Không chọn một seed thuận lợi hoặc khẳng định
Adaptive luôn tốt hơn. Output này là báo cáo thí nghiệm riêng, không thay
schema CSV lịch sử của UI.

- test_physics_day18.py: body/biên ở bốn hướng, geometry hẹp, spawn active,
  tuổi xe mới, exit một lần, hold/release/timeout ở hai ALL_RED và fail-safe.
- test_statistics_day19.py: null/zero, đo dừng, unique crossing, Queue,
  hold nhiều chu kỳ và Stop giữa chu kỳ.
- test_comparison_day19.py: budget fixed, Tape bất biến, đúng arrivals từng
  tick/hướng, horizon qua giới hạn cycles, Reset replay và ERROR không comparable.
- test_headway_across_cycles.py: headway 13s/100s qua nhiều chu kỳ ở cả bốn
  làn và cả hai policy; Reset xóa lịch sử; replay ca đối chứng 48s xác nhận
  từng crossing đủ headway trước khi đối chiếu kết quả runner.
- test_simulation_day17.py giữ kiểm tra nền. Fixture crossing một lần nay dùng
  xe initial thay xe mới để không mâu thuẫn TC-23; vị trí/timestamp kỳ vọng vẫn giữ.

Các test và thí nghiệm chỉ nghiệm thu mô hình học thuật, không xác nhận hệ
thống điều khiển giao thông thực. UI, DashboardData/SimulationSummary của
nhánh UI và CSV lịch sử còn là phần tích hợp riêng, không gắn nhãn đã hoàn thành
chỉ vì Core ngày 18–19 đã có.

Kết quả lần chạy bàn giao: [core_day18_19_results.md](core_day18_19_results.md).

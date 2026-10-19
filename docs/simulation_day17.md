# Simulation — bàn giao lịch sử đến hết task 17/10

Cập nhật: Core ngày 18–19 đã hoàn thiện tiếp trên nền này; xem
[core_day18_19.md](core_day18_19.md) cho API/kiểm thử hiện tại. Phần dưới mô tả mốc 17.

Hai engine và thống kê Core đã có trên feat/simulation. Controller lấy cùng
commit với feat/algorithm/PR #9. UI/renderer không được chỉnh trong đợt này.

## Vòng đời và thời gian

Constructor validate/sao chép Config, tạo initial queue, RNG, Controller chu kỳ 1
và state PAUSED tại t=0. Start kích hoạt phiên mới; tick chỉ cho RUNNING.
Pause không tiến thời gian. run_ticks(n) yêu cầu phiên đã Start, nhận int >0;
RUNNING chạy liên tiếp, PAUSED Step n tick rồi giữ PAUSED nếu chưa kết thúc.
Resume chỉ nhận PAUSED của phiên đã Start. Stop kết thúc phiên; Start/Resume
không nối lại phiên STOPPED. Reset khởi tạo lại bản chốt Config, IDs, seed,
clock, plan và statistics; gọi Start để chạy phiên mới.

Mỗi interval lấy Poisson đúng một lần theo N/S/E/W rồi cập nhật Movement
round(1/dt_s) lần (dt=0.2 mặc định là 5). Sau chuyển động, ghi sự kiện/counters,
lấy occupancy, Controller.tick một lần và tăng sim_time một giây.

## Ownership và crossing

- Initial queue: xe đầu ở -stop_margin_m; xe sau lùi length+min_gap.
- Xe mới Poisson: spawn phía sau Queue, ít nhất ở -approach_visible_m.
- Mỗi Vehicle được cập nhật đúng một lần/substep theo thứ tự trước→sau,
  gồm active cùng hướng rồi Queue. Crossing ghi t_sub+dt, pop đầu FIFO một lần.
- active_crossing là dict[id,Vehicle], property trả mapping chỉ đọc; Engine đọc
  values để xây DTO. Xe crossed tiếp tục đi khi vàng/đỏ, EXITED chuyển ownership
  riêng và không làm tăng crossing lần nữa.
- Snapshot chỉ chứa DTO và bản sao counters, không lộ Lane/Vehicle mutable.
- Lane clocks được bật/tắt đúng entry/exit GREEN; crossing kết hợp signal,
  startup_delay và headway, không chỉ dựa vào tọa độ.

## Statistics ngày 17

SimulationStats ghi arrivals theo hướng, deduplicate crossing theo vehicle_id,
chụp TickMetrics bất biến sau mỗi giây và chốt CycleMetrics trước khi kích hoạt
chu kỳ mới. Bản ghi có Queue đầu/cuối hai trục, xanh NS/EW, arrivals/departures
và thời gian bắt đầu/kết thúc; actual_cycle_s lấy hiệu boundary thực tế.
Counters trong MetricsSnapshot được đối chiếu với Statistics và bảo toàn xe.

Engine.stats.ticks/cycles trả tuple frozen records; summary() trả dict mới.
Stop giữa chu kỳ giữ các counters/tick đã chạy, không tính chu kỳ dở là completed.
CSV, dashboard, các chỉ số phân tích đầy đủ và Fixed-Time thuộc task sau 17.

Khi đủ cycles_to_run, Controller giữ ALL_RED_2/0 và state COMPLETED, không gọi
Adaptive thêm. Activation chu kỳ mới thất bại giữ terminal đỏ, ERROR và cycle_index
cũ. Statistics đã chốt chu kỳ cũ đúng một lần trước activation.

## Kiểm chứng và phần còn lại

- tests/test_controller.py: Controller, 68 tick và adapter pha vàng.
- tests/test_simulation_engine.py: kiểm tra nền tảng đã có.
- tests/test_simulation_day17.py: hồi quy bốn lỗi review, event timestamp,
  Poisson/substep, seed replay, startup/headway/FIFO, counters, cycle boundary,
  failed activation và Storage→Config→Engine→Snapshot.

Behavior occupancy/clearance đã có được giữ để tương thích. Nghiệm thu an toàn
vật lý/min_gap toàn diện/vehicle width, motion_2d.enabled=False và vùng exit
thuộc task 18, không được coi hoàn tất bởi suite đến 17. Không thêm CSV hoặc UI
trong đợt sửa này. JSON snapshot trong docs/examples vẫn là fixture minh họa,
không đổi thành kết quả mô phỏng giả.

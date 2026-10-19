# Bàn giao nhiệm vụ Models ngày 14/10/2026

Cập nhật 19/10: Config/Vehicle đã đồng bộ miền hình học xe 1.8m và ngưỡng
dừng <=0.1m/s; xem [Core ngày 18–19](docs/core_day18_19.md). Các số test/bàn giao
ngày 14 bên dưới là lịch sử.

Ghi chú API ngày 15/10/2026: nhóm chốt bỏ `Vehicle.to_xy()`/`GeometryProtocol` và
gọi trực tiếp `Geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m)`.
Đây là thay đổi hợp đồng so với V2.3 gốc; Models chỉ giữ dữ liệu Vehicle,
Geometry sở hữu công thức tọa độ. Test tích hợp dùng hai đối tượng thật.

Ghi chú đồng bộ ngày 15/10/2026: phần bàn giao và kết quả kiểm thử ngày 14 dưới đây
là lịch sử. Config hiện nhận hợp đồng main về JSON V2, tên trường và thời lượng int;
những mục API tương ứng được cập nhật, các phần tích hợp khác giữ nguyên.
Kiểm chứng sau đồng bộ bằng `uv run pytest`: 446 passed, không fail hoặc skip.

Đã hoàn thiện trên feat/models để review; chưa commit/push/merge.
Đây là bàn giao cho nhiệm vụ ngày 14, không thay đổi mặc định Models ngày 13.

## Phạm vi và trạng thái

- SignalSegment: hoàn thành, dataclass frozen, kiểm tra code/phase/color và int > 0.
- SignalPlan: hoàn thành, sáu đoạn đúng thứ tự, deque riêng, không tự quay vòng.
- FIFO nâng cao: đạt với 20 xe trên mỗi hướng, thêm mới sau pop và bốn làn độc lập.
- Models ổn định trong phạm vi unit test: đạt, giữ nguyên toàn bộ test ngày 13.

File thay đổi: src/models/signal.py, src/models/__init__.py.
File mới: tests/test_signal.py, tests/test_fifo_day14.py,
demo_models_day14.py, MODELS_DAY14_HANDOFF.md.
Không sửa Config, Vehicle, Lane, dependencies, JSON, Algorithm, Controller hoặc UI.

## Public API và trách nhiệm

```python
from src.models import Config, SignalSegment, SignalPlan

plan = SignalPlan.from_config(Config(), green_ns_s=21, green_ew_s=39, cycle_no=1)
segment = plan.current()
if segment is not None:
    green_for_north = segment.is_green_for('N')
    directions = segment.green_directions
    nominal_seconds = segment.duration_s
# Controller chỉ gọi khi đoạn hết thời gian và điều kiện an toàn đã đạt:
next_segment = plan.move_next()
cycle_finished = plan.is_cycle_end()
```

SignalSegment là một đoạn; SignalPlan là lịch một chu kỳ và con trỏ tiến qua lịch.
Hai pha xanh NS/EW, mỗi pha có GREEN, YELLOW, ALL_RED nên tổng cộng sáu đoạn.
YELLOW và ALL_RED có active_phase=None, không cấp quyền xe mới vượt vạch.
ALL_RED cho xe pha trước thoát vùng xung đột trước xanh đối diện.
current() chỉ đọc, move_next() hoàn tất đoạn hiện tại bằng deque.popleft().
Sau ALL_RED_2, current() và move_next() trả None; is_cycle_end() trả True.
segments là tuple đủ sáu đoạn bất biến, kể cả sau kết thúc; nominal_duration_s
không giảm khi chuyển đoạn. Tham số public của kế hoạch không thể gán lại.

Lane dùng deque xe; SignalPlan dùng deque đoạn chưa hoàn tất. Mỗi instance có
Queue riêng. Thuộc tính private không phải API cho UI/Controller.
SignalPlan không tự tính Adaptive: Algorithm phân bổ xanh dựa trên Queue mới.
Không tự xoay chu kỳ vì Core cần chốt thống kê, kiểm tra số chu kỳ và tính lại xanh.
is_green_for() chỉ kiểm tra tín hiệu; startup/headway/min_gap/crossing vẫn thuộc Core.
Hướng sai raise TypeError/ValueError thay vì âm thầm trả False.

from_config() kiểm tra Config, budget và min_green; phân bổ xanh và mọi thời lượng
tín hiệu trong Config phải là int thực sự, không nhận bool, float hoặc chuỗi.
Cả 3.0 và 3.5 đều bị từ chối; không ép kiểu, cắt hoặc làm tròn thời lượng.
SignalPlan khởi tạo trực tiếp chỉ nhận int cho mọi thời lượng và cycle_no >= 1.
Kế hoạch giữ bản chụp giá trị, Config đổi sau đó không làm thay đổi lịch đã tạo.

## Đối chiếu tài liệu V2.3

Đã đọc phần Models, lịch tín hiệu, crossing và JSON trong tài liệu workspace:
`../Traffic Light Signal Simulation/Thiết kế hệ thống smart traffic light.docx`,
`../Traffic Light Signal Simulation/Tổng quan smart traffic light.docx` và các
file thiết kế trong `../Yêu cầu/`. Tài liệu có mô tả deque quay vòng; yêu cầu
nhiệm vụ này ưu tiên mỗi SignalPlan chỉ biểu diễn một chu kỳ, không tự xoay.

| Hợp đồng đã nhận từ main | Biểu diễn trong Models | Quy tắc |
| --- | --- | --- |
| configs | Danh sách chứa các Config dạng dict | JSON khởi tạo rỗng, mẫu nằm riêng trong docs/examples |
| rates_per_min | rates_per_min | Dictionary đủ N/S/E/W, đơn vị xe/phút |
| motion_2d | motion_2d | Tên trường chuẩn JSON V2 |
| motion_2d.enabled | Motion2DConfig.enabled | Boolean, giữ giá trị khi đọc/ghi |

Tài liệu mẫu dùng rates 12/9/18/7, queue 7/4/16/5, seed 2026,
max_speed_mps=9, approach_visible_m=60, intersection_width_m=16;
Default 2D đã đồng bộ main với max_speed_mps=9, approach_visible_m=60,
intersection_width_m=16. Các giá trị lưu lượng, queue và seed của Config() vẫn
có thể khác cấu hình mẫu. Config.from_dict() nạp trực tiếp một phần tử của JSON
V2, yêu cầu đủ trường và từ chối alias cũ arrival_rates/motion2d.

## Kiểm chứng lịch sử trước đồng bộ main

Các lệnh uv dùng cache trong repository vì cache mặc định của tài khoản Admin
không phù hợp quyền sandbox:

```powershell
uv --cache-dir .uv-cache sync
uv --cache-dir .uv-cache run pytest -q tests/test_signal.py
uv --cache-dir .uv-cache run pytest -q tests/test_fifo_day14.py
uv --cache-dir .uv-cache run pytest -q
uv --cache-dir .uv-cache run pytest -q -o cache_dir=.uv-cache/pytest
uv --cache-dir .uv-cache run python demo_models_day14.py
```

- uv sync: thành công, kiểm tra 44 package.
- Signal: 65 passed, 0 failed.
- FIFO ngày 14: 8 passed, 0 failed.
- Toàn bộ: 187 passed, 0 failed; gồm 114 test có sẵn.
- Các lần đầu có PytestCacheWarning do thiếu quyền ghi .pytest_cache.
  Dùng cache_dir=.uv-cache/pytest để tránh vấn đề quyền mà không thay cấu hình dự án.
- Demo: sáu đoạn 21/3/1/39/3/1, tổng danh định 68 giây, kết thúc không quay lại xanh.

Chưa kiểm chứng tích hợp runtime với Algorithm/Controller/Movement/Storage.
Không có test tick 68 giây hay clearance hold thực tế trong Models.
Controller phải giữ ALL_RED khi vùng xung đột còn xe và chỉ gọi move_next()
khi đủ điều kiện; Models không tự kiểm tra vùng xung đột hoặc tăng thời lượng.

## Git và review

Sẵn sàng review phần Models; chưa bảo đảm tích hợp toàn hệ thống.
Các file cần stage là sáu file trong phần phạm vi, bao gồm demo và bàn giao.
Chỉ commit sau khi chủ nhiệm nhiệm vụ kiểm tra/cho phép:

```text
feat(models): implement signal plan and FIFO tests
```

Chưa tự mở Pull Request, push hoặc merge.

# Bàn giao nhiệm vụ Models ngày 14/10/2026

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

from_config() kiểm tra Config, budget và min_green; phân bổ xanh phải là int thực sự,
không nhận bool, float hoặc chuỗi. Config ngày 13 cho phép số thực tại yellow_s/all_red_s:
3.0/1.0 được chuyển chính xác sang int; 3.5 bị từ chối, không cắt hoặc làm tròn.
SignalPlan khởi tạo trực tiếp chỉ nhận int cho mọi thời lượng và cycle_no >= 1.
Kế hoạch giữ bản chụp giá trị, Config đổi sau đó không làm thay đổi lịch đã tạo.

## Đối chiếu tài liệu V2.3

Đã đọc phần Models, lịch tín hiệu, crossing và JSON trong tài liệu workspace:
`../Traffic Light Signal Simulation/Thiết kế hệ thống smart traffic light.docx`,
`../Traffic Light Signal Simulation/Tổng quan smart traffic light.docx` và các
file thiết kế trong `../Yêu cầu/`. Tài liệu có mô tả deque quay vòng; yêu cầu
nhiệm vụ này ưu tiên mỗi SignalPlan chỉ biểu diễn một chu kỳ, không tự xoay.

| Repository | Tài liệu V2.3 | Đề xuất thống nhất |
| --- | --- | --- |
| configurations | configs | Storage thống nhất envelope hoặc migration rõ ràng |
| arrival_rates | rates_per_min | Storage ánh xạ tên ở biên, giữ API đang dùng |
| motion2d | motion_2d | Storage ánh xạ tên ở biên, không đổi Models tự động |
| Không có enabled | motion_2d.enabled | Nhóm quyết định thêm trường hay mô phỏng luôn bật |

Tài liệu mẫu dùng rates 12/9/18/7, queue 7/4/16/5, seed 2026,
max_speed_mps=9, approach_visible_m=60, intersection_width_m=16;
Config ngày 13 có default khác. Đây là cấu hình mẫu tài liệu, không tự ghi đè
default đang dùng. arrival_rates được đề xuất xe/phút, phù hợp tên rates_per_min.
Config.from_dict() hiện nhận đủ tên trường repository và từ chối trường thừa;
không thể nạp trực tiếp JSON mẫu V2.3 nếu chưa có ánh xạ được nhóm thống nhất.

## Kiểm chứng

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

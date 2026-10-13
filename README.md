# Smart Traffic Light Simulator

## Giới thiệu và mục tiêu

Dự án **SmartTrafficLight** thuộc học phần Python Module 1, hướng tới mô phỏng
đèn giao thông thông minh và so sánh cách phân bổ thời gian xanh theo lưu lượng xe.
Nền tảng ngày **12/10/2026** chỉ gồm bộ khung kiến trúc V2.3, môi trường uv,
giao diện thông báo và smoke tests. Chưa có mô phỏng hoặc thuật toán hoạt động.

## Phạm vi

Một ngã tư bốn hướng **N/S/E/W**, hai pha **NS/EW**, dự kiến mô phỏng xe 2D.
SimulationEngine dự kiến dùng tick 1 giây; MovementEngine dùng substep 0,2 giây.

## Công nghệ

Python >=3.13, **uv**, **Streamlit**, **Plotly**, **pandas**, **pytest** và Git/GitHub.
Dependencies được quản lý trong `pyproject.toml` và khóa bằng `uv.lock`.

## Kiến trúc Models – Core Logic – UI

| Thư mục / file | Vai trò |
| --- | --- |
| `src/models/` | Khung OOP Vehicle, Lane, Config, SignalPlan |
| `src/core/` | Khung thuật toán, điều phối, hình học, chuyển động, mô phỏng, thống kê, quản lý và lưu trữ |
| `src/ui/` | Khung renderer 2D |
| `src/app.py` | Điểm vào Streamlit với hai tab, chỉ hiển thị thông báo đang phát triển |
| `data/junctions.json` | Cấu hình mẫu hợp lệ: schema_version 2, configurations rỗng |
| `tests/` | Smoke tests cấu trúc, imports, JSON, metadata uv; test thuật toán còn TODO |
| `src/smarttrafficlight/` | Package do uv khởi tạo trước đó, giữ nguyên để tương thích build hiện tại |

Models biểu diễn dữ liệu; Core Logic xử lý nghiệp vụ; UI hiển thị và tiếp nhận thao tác.
Không đặt thuật toán hoặc xử lý nghiệp vụ trong `app.py`.

## Cấu trúc dữ liệu dự kiến

- **Dictionary**: ánh xạ hướng N/S/E/W tới làn xe, cấu hình và trạng thái.
- **Queue / collections.deque**: hàng đợi FIFO cho xe đến và rời làn.

Các cấu trúc này chưa được triển khai trong bộ khung hiện tại.

## Thuật toán dự kiến

- **Poisson**: sinh số xe đến theo lưu lượng và khoảng thời gian.
- **Adaptive + t_min**: phân bổ thời gian xanh theo nhu cầu hai pha và giới hạn
  thời gian xanh tối thiểu. Công thức và các trường hợp biên sẽ được triển khai,
  kiểm thử ở giai đoạn thuật toán.

## Cài đặt và chạy

Cài Python >=3.13, uv và Git. Trong thư mục dự án:

```powershell
uv sync
uv run streamlit run src/app.py
```

Ứng dụng hiện chỉ có tab **Quản lý cấu hình** và **Mô phỏng 2D**, kèm thông báo
đang phát triển. Dừng server bằng Ctrl+C.

## Kiểm thử

```powershell
uv run pytest
uv run python -m py_compile src/app.py
```

Smoke tests không chứng minh tính đúng đắn của các thuật toán chưa được viết.
`tests/test_algorithms.py` chỉ có TODO.

## Git Flow

`main` giữ phiên bản ổn định. Nhánh tính năng khởi tạo từ `main` mới nhất:

| Branch | Phạm vi dự kiến |
| --- | --- |
| `feat/models` | Mô hình OOP và cấu trúc dữ liệu |
| `feat/algorithm` | Poisson, Adaptive và t_min |
| `feat/simulation` | SimulationEngine và MovementEngine |
| `feat/ui` | Streamlit và renderer Plotly |
| `feat/storage` | JSON, CSV và thống kê |

Trước khi phát triển: cập nhật `main`, chuyển sang branch phù hợp, commit nhỏ
có mô tả rõ và chạy kiểm thử. Chỉ mở Pull Request khi có thay đổi tính năng thực tế;
review và merge về `main` sau khi kiểm tra đạt. Không force push hoặc ghi đè lịch sử.
Việc tạo/push branch trên GitHub phụ thuộc remote hợp lệ và quyền truy cập.

Sau khi repository GitHub được cấu hình, thay `<REPOSITORY_URL>` bằng URL thực:

```powershell
git clone <REPOSITORY_URL>
cd SmartTrafficLight
uv sync
uv run streamlit run src/app.py
```

## Thành viên

| Họ tên | Mã sinh viên | Vai trò |
| --- | --- | --- |
| Cập nhật sau | Cập nhật sau | Cập nhật sau |

## Trạng thái theo giai đoạn

| Giai đoạn | Trạng thái / kết quả |
| --- | --- |
| 12/10 – Nền tảng V2.3 | Bộ khung, cấu hình mẫu, giao diện hai tab và smoke tests |
| Models | Dự kiến: Vehicle, Lane, Config, SignalPlan, Dictionary và deque |
| Thuật toán | Dự kiến: Poisson, Adaptive + t_min và kiểm thử thực tế |
| Mô phỏng | Dự kiến: tick 1 giây, chuyển động 2D substep 0,2 giây |
| UI hoàn chỉnh | Dự kiến: chỉnh cấu hình và hiển thị xe 2D |
| Lưu trữ / thống kê | Dự kiến: cấu hình JSON và thống kê CSV |
| Tích hợp | Dự kiến: kiểm thử và đánh giá toàn hệ thống |

Kết quả chạy lệnh và trạng thái GitHub được báo cáo riêng khi bàn giao; không
coi các chức năng dự kiến là đã hoạt động.

## Models triển khai ngày 13/10/2026

Import API: `from src.models import Config, Motion2DConfig, Vehicle, Lane`.
Models không triển khai Poisson, Adaptive, Geometry, MovementEngine hoặc UI.

- `Config()` tự validate; `validate()` kiểm tra lại sau khi chỉnh cấu hình.
  `arrival_rates` là dictionary N/S/E/W (đề xuất xe/phút, cần xác nhận với Poisson),
  `initial_queue` là dictionary số xe nguyên mỗi hướng. `motion2d` chứa tham số 2D.
  `to_dict()` trả bản sao độc lập; `Config.from_dict(data)` nhận đủ các trường
  của một cấu hình, từ chối trường thiếu/thừa. Không nhận envelope Storage.
- Default đề xuất: id="default", name="Ngã tư mặc định", lưu lượng 10/hướng,
  queue 0/hướng, green_budget_s=60, min_green_s=10, yellow_s=3, all_red_s=1,
  startup_delay_s=2, headway_s=2, cycles_to_run=10, seed=42.
  Motion2D: dt_s=0.2, vehicle_length_m=4.5, min_gap_m=2, max_speed_mps=13.9,
  accel_mps2=2, approach_visible_m=100, intersection_width_m=20,
  stop_margin_m=0.5, clearance_limit_s=30. Bảng default V2.3 không có trong
  yêu cầu gửi kèm/repository; cần đối chiếu trước khi tích hợp.
- `Vehicle` có trường chỉ đọc; dùng `update_motion(s_front_m, speed_mps)`
  để cập nhật tiến, không tự ghi nhận crossing. Xe mới ở s_front_m <= 0.
  Controller kiểm tra tín hiệu, vị trí và xe đầu Lane, rồi gọi `mark_crossed(t)`
  một lần khi đầu xe tới/vượt vạch, ngay sau đó `Lane.pop_crossed()` và chuyển
  xe sang active_crossing. `mark_exited(t)` dùng sau crossing khi Core xác nhận
  xe rời khung. Các thời điểm sự kiện cùng hệ thời gian mô phỏng, đơn vị giây.
  `elapsed_to_stopline()` trả None trước crossing; `add_stopped_delay(dt_s)`
  cộng thời gian đứng yên trước crossing; `snapshot()` phục vụ UI/thống kê.
  `to_xy(geometry)` cần `geometry.lane_to_xy(origin, s_front_m) -> (x, y)`.
- `Lane(direction)` dùng deque; `enqueue(vehicle)` yêu cầu thứ tự arrival_t
  không giảm (cùng thời điểm theo thứ tự enqueue). ID không được tái sử dụng
  trong cùng Lane kể cả sau khi pop. Core cấp ID duy nhất toàn mô phỏng.
  `peek()` xem đầu, `pop_crossed()` lấy đầu đã crossing; cả hai trả None khi rỗng.
  Pop khi đầu chưa crossing raise ValueError và giữ nguyên Queue.
  `get_vehicles()` trả tuple, `count()` đếm mọi xe còn trong Queue.
- Controller gọi `reset_green_clock(started_at, startup_delay_s, headway_s)`
  khi bắt đầu xanh: thời điểm đủ điều kiện đầu tiên là start + startup delay.
  Sau pop, đồng hồ kế tiếp là max(đồng hồ cũ, crossed_stop_t + headway).
  `is_cross_eligible(t)` chỉ kiểm tra đồng hồ và Queue, không cấp quyền qua đèn.
  `reset_green_clock()` xóa clock khi kết thúc xanh; không xóa xe.

Storage cần thống nhất tên trường, đơn vị lưu lượng và default ở trên.
JSON hiện dùng `{"schema_version": 2, "configurations": []}`; tài liệu V2.3
được đề cập trong yêu cầu dùng `configs`. Chưa đổi JSON hoặc smoke test;
Storage phải thống nhất envelope riêng với nhóm trước khi nối Config.

# Smart Traffic Light Simulator

## Giới thiệu và mục tiêu

Dự án **SmartTrafficLight** thuộc học phần Python Module 1, hướng tới mô phỏng
đèn giao thông thông minh và so sánh cách phân bổ thời gian xanh theo lưu lượng xe.
Nền tảng ngày **12/10/2026** chỉ gồm bộ khung kiến trúc V2.3, môi trường uv,
giao diện thông báo và smoke tests.

Hiện tại đã có Config theo JSON V2, Poisson, Adaptive và đọc/ghi JSON cấu hình.
Config dùng `rates_per_min`, `motion_2d.enabled` và thời lượng tín hiệu kiểu `int`.
`data/junctions.json` khởi tạo với `configs: []`; dữ liệu mẫu nằm riêng trong
`docs/examples/junctions_v2.example.json`. Controller sáu đoạn đã có trên nhánh Algorithm; hai engine và renderer chưa triển khai ở nhánh này.

## Phạm vi

Một ngã tư bốn hướng **N/S/E/W**, hai pha **NS/EW**, dự kiến mô phỏng xe 2D.
SimulationEngine dự kiến dùng tick 1 giây; MovementEngine dùng substep 0,2 giây.

## Công nghệ

Python >=3.13, **uv**, **Streamlit**, **Plotly**, **pandas**, **pytest** và Git/GitHub.
Dependencies được quản lý trong `pyproject.toml` và khóa bằng `uv.lock`.

## Kiến trúc Models – Core Logic – UI

| Thư mục / file | Vai trò |
| --- | --- |
| `src/models/` | Config/validation, Vehicle, Lane FIFO, SignalPlan và snapshot đã có; chưa tích hợp engine |
| `src/core/` | Poisson, Adaptive, hình học, quản lý cấu hình và JSON đã có; Controller sáu đoạn đã có; chuyển động, mô phỏng, thống kê còn là khung |
| `src/ui/` | Khung renderer 2D |
| `src/app.py` | Điểm vào Streamlit với hai tab, chỉ hiển thị thông báo đang phát triển |
| `data/junctions.json` | Cấu hình khởi tạo hợp lệ: schema_version 2, configs rỗng |
| `tests/` | Smoke tests, thuật toán, hình học/snapshot, Config, JSON và tích hợp Storage → Config → Adaptive |

Models biểu diễn dữ liệu; Core Logic xử lý nghiệp vụ; UI hiển thị và tiếp nhận thao tác.
Không đặt thuật toán hoặc xử lý nghiệp vụ trong `app.py`.

Dự án là ứng dụng Streamlit chạy trực tiếp từ `src/app.py`; uv quản lý môi trường
và dependencies, không đóng gói ứng dụng thành thư viện Python.

## Cấu trúc dữ liệu dự kiến

- **Dictionary**: ánh xạ hướng N/S/E/W tới làn xe, cấu hình và trạng thái.
- **Queue / collections.deque**: hàng đợi FIFO cho xe đến và rời làn.

Dictionary đã được dùng làm chỉ mục cấu hình trong ConfigManager;
Lane và SignalPlan đã dùng deque; engine điều phối mô phỏng chưa được triển khai trên nhánh Algorithm.

## Thuật toán

- **Poisson**: sinh số xe đến theo lưu lượng và khoảng thời gian.
- **Adaptive + t_min**: phân bổ thời gian xanh theo nhu cầu hai pha và giới hạn
  thời gian xanh tối thiểu; làm tròn half-up cho NS, EW nhận phần ngân sách còn lại.

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

`tests/test_algorithms.py` kiểm tra Poisson và Adaptive; các test Config/Storage
kiểm tra JSON V2 và việc truyền thời lượng số nguyên vào Adaptive.
Các test này chưa kiểm chứng hai engine hoặc mô phỏng chuyển động hoàn chỉnh.

## Git Flow

`main` giữ phiên bản ổn định. Nhánh tính năng khởi tạo từ `main` mới nhất:

| Branch | Phạm vi dự kiến |
| --- | --- |
| `feat/models` | Mô hình OOP và cấu trúc dữ liệu |
| `feat/algorithm` | Poisson, Adaptive, t_min và TrafficLightController |
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
| Models | Config, snapshot, Vehicle, Lane FIFO và SignalPlan đã có; chưa tích hợp engine |
| Thuật toán | Poisson và Adaptive + t_min đã có implementation và kiểm thử |
| Mô phỏng | Dự kiến: tick 1 giây, chuyển động 2D substep 0,2 giây |
| UI hoàn chỉnh | Dự kiến: chỉnh cấu hình và hiển thị xe 2D |
| Lưu trữ / thống kê | Cấu hình JSON đã có; thống kê CSV chưa triển khai |
| Tích hợp | Dự kiến: kiểm thử và đánh giá toàn hệ thống |

Kết quả chạy lệnh và trạng thái GitHub được báo cáo riêng khi bàn giao; không
coi các chức năng dự kiến là đã hoạt động.

## Models triển khai ngày 13/10/2026

Import API: `from src.models import Config, Motion2DConfig, Vehicle, Lane`.
Models không triển khai Poisson, Adaptive, Geometry, MovementEngine hoặc UI.

- `Config()` tự validate; `validate()` kiểm tra lại sau khi chỉnh cấu hình.
  `rates_per_min` là dictionary N/S/E/W, đơn vị xe/phút;
  `initial_queue` là dictionary số xe nguyên mỗi hướng. `motion_2d` chứa tham số 2D
  và `enabled` kiểu bool. Các thời lượng tín hiệu là int, không nhận float/bool/chuỗi.
  `to_dict()` trả bản sao độc lập; `Config.from_dict(data)` nhận đủ các trường
  của một cấu hình, từ chối trường thiếu/thừa. Không nhận envelope Storage.
- Default đề xuất: id="default", name="Ngã tư mặc định", lưu lượng 10/hướng,
  queue 0/hướng, green_budget_s=60, min_green_s=10, yellow_s=3, all_red_s=1,
  startup_delay_s=2, headway_s=2, cycles_to_run=10, seed=42.
  Motion2D theo hợp đồng main: enabled=True, dt_s=0.2, vehicle_length_m=4.5,
  min_gap_m=2, max_speed_mps=9, accel_mps2=2, approach_visible_m=60,
  intersection_width_m=16, stop_margin_m=0.5, clearance_limit_s=30.
- `Vehicle` có trường chỉ đọc; dùng `update_motion(s_front_m, speed_mps)`
  để cập nhật tiến, không tự ghi nhận crossing. Xe mới ở s_front_m <= 0.
  Controller kiểm tra tín hiệu, vị trí và xe đầu Lane, rồi gọi `mark_crossed(t)`
  một lần khi đầu xe tới/vượt vạch, ngay sau đó `Lane.pop_crossed()` và chuyển
  xe sang active_crossing. `mark_exited(t)` dùng sau crossing khi Core xác nhận
  xe rời khung. Các thời điểm sự kiện cùng hệ thời gian mô phỏng, đơn vị giây.
  `elapsed_to_stopline()` trả None trước crossing; `add_stopped_delay(dt_s)`
  cộng thời gian đứng yên trước crossing; `snapshot()` phục vụ UI/thống kê.
  Core lấy tọa độ bằng `geometry.lane_to_xy(vehicle.origin, vehicle.s_front_m)`.
  Vehicle không giữ `to_xy()`; công thức hình học chỉ có trong Geometry.
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

JSON khởi tạo dùng `{"schema_version": 2, "configs": []}` theo hợp đồng main.
`Config.from_dict()` nhận một phần tử trong `configs`; `to_dict()` trả đúng
các trường JSON V2, gồm `rates_per_min`, `motion_2d` và `motion_2d.enabled`.

## Thiết kế UI và lưu trữ Task 5

[Hợp đồng UI/Storage](docs/ui_storage_contracts.md) chốt hai wireframe desktop,
[JSON mẫu V2.3](docs/examples/junctions_v2.example.json),
[JSON Schema](docs/schema/junctions_v2.schema.json) và
[test cases](docs/testcases/ui_storage_testcases.md).
Khóa danh sách cấu hình chính thức là `configs`. Skeleton `configurations: []`
ban đầu đã được đổi an toàn vì chưa chứa dữ liệu người dùng.
Wireframe là tài liệu thiết kế; CRUD, FileStorage, dashboard và mô phỏng chưa
được kết nối với ứng dụng Streamlit hiện tại.

## Controller đến hết task 17/10

Controller sở hữu xây lịch/chuyển sáu đoạn và adapter pha vàng; Engine sở hữu
clock/cycle_index. Xem [hợp đồng Controller](docs/controller_contracts.md).
`tests/test_controller.py` kiểm tra runtime; phần clearance/min_gap chuyên sâu
ngày 18 và tích hợp hai engine trên PR #15 được đánh giá riêng.

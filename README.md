# Smart Traffic Light Simulator

## Giới thiệu và mục tiêu

Dự án **SmartTrafficLight** thuộc học phần Python Module 1, hướng tới mô phỏng
đèn giao thông thông minh và so sánh cách phân bổ thời gian xanh theo lưu lượng xe.
Nền tảng ngày **12/10/2026** chỉ gồm bộ khung kiến trúc V2.3, môi trường uv,
giao diện thông báo và smoke tests.

Hiện tại đã có Config theo JSON V2, Poisson, Adaptive và đọc/ghi JSON cấu hình.
Config dùng `rates_per_min`, `motion_2d.enabled` và thời lượng tín hiệu kiểu `int`.
`data/junctions.json` khởi tạo với `configs: []`; dữ liệu mẫu nằm riêng trong
`docs/examples/junctions_v2.example.json`. Core Algorithms/Simulation đến task 18–19
đã có hình bao xe 1,8m, clearance, invariants, thống kê và đối chứng Fixed-Time.
UI hai tab đã nối Core/Storage thật, renderer và CSV lịch sử.

## Phạm vi

Một ngã tư bốn hướng **N/S/E/W**, hai pha **NS/EW**, mô phỏng xe 2D trong Core.
SimulationEngine dùng tick 1 giây; MovementEngine dùng substep 0,2 giây mặc định.

## Công nghệ

Python >=3.13, **uv**, **Streamlit**, **Plotly**, **pandas**, **pytest** và Git/GitHub.
Dependencies được quản lý trong `pyproject.toml` và khóa bằng `uv.lock`.

## Kiến trúc Models – Core Logic – UI

| Thư mục / file | Vai trò |
| --- | --- |
| `src/models/` | Config/validation, Vehicle, Lane FIFO, SignalPlan và snapshot đã được nối với engine |
| `src/core/` | Poisson/Adaptive/Fixed-Time, Controller, hình học/Movement, replay arrivals, thống kê và đối chứng; quản lý cấu hình JSON |
| `src/ui/` | CRUD, điều khiển phiên, timer, dashboard/charts và renderer 2D chỉ đọc |
| `src/app.py` | Điểm vào Streamlit với hai tab Quản lý cấu hình và Mô phỏng và phân tích |
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
Lane và SignalPlan dùng deque; engine điều phối, active_crossing dùng dict theo ID.

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

Tab **Quản lý cấu hình** tạo/sửa/xóa và chọn cấu hình đã lưu. Tab **Mô phỏng và
phân tích** chạy Core, Pause/Resume/Step/chạy hết chu kỳ, Reset cùng seed và
xuất báo cáo CSV. Reset cần Start lại. Dừng server bằng Ctrl+C.

## Kiểm thử

```powershell
uv run pytest
uv run python -m py_compile src/app.py
```

`tests/test_algorithms.py` kiểm tra Poisson và Adaptive; các test Config/Storage
kiểm tra JSON V2 và việc truyền thời lượng số nguyên vào Adaptive.
Có thêm test_controller.py và test_simulation_day17.py để kiểm chứng Core đến 17/10.
UI động và nghiệm thu an toàn task 18 chưa thuộc phạm vi này.

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
| Models | Config, snapshot, Vehicle, Lane FIFO và SignalPlan đã tích hợp Core |
| Thuật toán | Poisson, Adaptive + t_min, Fixed-Time và arrivals replay đã có |
| Mô phỏng | Đã có tick 1 giây, chuyển động 2D substep 0,2 giây và snapshot |
| UI hoàn chỉnh | Dự kiến: chỉnh cấu hình và hiển thị xe 2D |
| Lưu trữ / thống kê | JSON và thống kê tick/chu kỳ/phiên đã có; CSV lịch sử UI chưa triển khai |
| Tích hợp | Core 18–19 có test hình bao/gap/clearance, metrics/invariants và so sánh cùng horizon; UI tách riêng |

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
- Engine gọi `reset_green_clock(started_at, startup_delay_s, headway_s)`
  khi bắt đầu xanh: thời điểm đủ điều kiện là
  `max(start + startup delay, crossing cuối cùng + headway)` nếu đã có crossing;
  nếu chưa có thì dùng `start + startup delay`.
  Sau pop, đồng hồ kế tiếp là max(đồng hồ cũ, crossed_stop_t + headway).
  `is_cross_eligible(t)` chỉ kiểm tra đồng hồ và Queue, không cấp quyền qua đèn.
  `reset_green_clock()` tắt clock khi kết thúc xanh; giữ xe và lịch sử crossing
  qua vàng/đỏ, qua chu kỳ và cả khi Queue rỗng. Reset toàn phiên tạo Lane mới,
  xóa lịch sử crossing.

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
Ứng dụng hiện có CRUD qua FileStorage JSON và dashboard/mô phỏng dùng Core thật.
Wireframe là tài liệu thiết kế; xem [hợp đồng tích hợp UI](docs/ui_core_integration.md)
để biết lifecycle, timer và CSV đã hiện thực.

## Controller đến hết task 17/10

Controller sở hữu xây lịch/chuyển sáu đoạn và adapter pha vàng; Engine sở hữu
clock/cycle_index. Xem [hợp đồng Controller](docs/controller_contracts.md).
`tests/test_controller.py` kiểm tra runtime; phần clearance/min_gap chuyên sâu
ngày 18 và tích hợp hai engine trên PR #15 được đánh giá riêng.

## Simulation đến hết task 17/10

Xem [hợp đồng runtime](docs/simulation_day17.md) để biết lifecycle, Step/Stop,
ownership theo ID, thống kê và phạm vi test. Các test UI thực nằm trong
`tests/test_ui_runtime.py`; chúng chạy hai tab trên Core/Storage thật.


## Core ngày 18–19 và thí nghiệm không cần UI

Xem [hợp đồng và tiêu chí nghiệm thu](docs/core_day18_19.md). Bề rộng vật lý
1,8m được chốt cho Core, vì vậy giao lộ phải rộng ít nhất 3,6m để chứa hai làn.
JSON V2 giữ nguyên bộ khóa; Geometry.for_motion truyền rõ width vào Snapshot.

```python
from src.models.config import Config
from src.core.comparison import compare_policies

result = compare_policies(Config(seed=42), horizon_s=180)
print(result.to_dict())
```

Hai policy dùng cùng bảng arrivals và cùng H giây; số chu kỳ có thể khác.
Kết quả ERROR/không đủ H có comparable=False. Chạy 6 kịch bản × 10 seed:

```bash
uv run python -m src.core.experiment --horizon 180 --output reports/comparison.json
uv run pytest
```

Output là báo cáo thí nghiệm, không phải sim_history.csv/cycle_metrics.csv của UI.
Không mặc định Adaptive tốt hơn ở mọi kịch bản. UI đã nối với API báo cáo mới;
thí nghiệm đối chứng nhiều seed vẫn là CLI độc lập, chưa có màn so sánh policy trong UI.

# Smart Traffic Light Simulator

## Giới thiệu và mục tiêu

Dự án **SmartTrafficLight** thuộc học phần Python Module 1, hướng tới mô phỏng
đèn giao thông thông minh và so sánh cách phân bổ thời gian xanh theo lưu lượng xe.
Nền tảng ngày **12/10/2026** chỉ gồm bộ khung kiến trúc V2.3, môi trường uv,
giao diện thông báo và smoke tests.

Hiện tại đã có Config theo JSON V2, Poisson, Adaptive và đọc/ghi JSON cấu hình.
Config dùng `rates_per_min`, `motion_2d.enabled` và thời lượng tín hiệu kiểu `int`.
`data/junctions.json` khởi tạo với `configs: []`; dữ liệu mẫu nằm riêng trong
`docs/examples/junctions_v2.example.json`. Hai engine và renderer vẫn chưa triển khai.

## Phạm vi

Một ngã tư bốn hướng **N/S/E/W**, hai pha **NS/EW**, dự kiến mô phỏng xe 2D.
SimulationEngine dự kiến dùng tick 1 giây; MovementEngine dùng substep 0,2 giây.

## Công nghệ

Python >=3.13, **uv**, **Streamlit**, **Plotly**, **pandas**, **pytest** và Git/GitHub.
Dependencies được quản lý trong `pyproject.toml` và khóa bằng `uv.lock`.

## Kiến trúc Models – Core Logic – UI

| Thư mục / file | Vai trò |
| --- | --- |
| `src/models/` | Config/validation và snapshot đã có; Vehicle, Lane, SignalPlan còn là khung |
| `src/core/` | Poisson, Adaptive, hình học, quản lý cấu hình và JSON đã có; điều phối, chuyển động, mô phỏng, thống kê còn là khung |
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
Queue/deque cho mô phỏng chưa được triển khai.

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
| Models | Config và snapshot đã có; Vehicle, Lane, SignalPlan và deque chưa triển khai |
| Thuật toán | Poisson và Adaptive + t_min đã có implementation và kiểm thử |
| Mô phỏng | Dự kiến: tick 1 giây, chuyển động 2D substep 0,2 giây |
| UI hoàn chỉnh | Dự kiến: chỉnh cấu hình và hiển thị xe 2D |
| Lưu trữ / thống kê | Cấu hình JSON đã có; thống kê CSV chưa triển khai |
| Tích hợp | Dự kiến: kiểm thử và đánh giá toàn hệ thống |

Kết quả chạy lệnh và trạng thái GitHub được báo cáo riêng khi bàn giao; không
coi các chức năng dự kiến là đã hoạt động.

## Thiết kế UI và lưu trữ Task 5

[Hợp đồng UI/Storage](docs/ui_storage_contracts.md) chốt hai wireframe desktop,
[JSON mẫu V2.3](docs/examples/junctions_v2.example.json),
[JSON Schema](docs/schema/junctions_v2.schema.json) và
[test cases](docs/testcases/ui_storage_testcases.md).
Khóa danh sách cấu hình chính thức là `configs`. Skeleton `configurations: []`
ban đầu đã được đổi an toàn vì chưa chứa dữ liệu người dùng.
Wireframe là tài liệu thiết kế; CRUD, FileStorage, dashboard và mô phỏng chưa
được kết nối với ứng dụng Streamlit hiện tại.

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

Models biểu diễn dữ liệu; Core Logic xử lý nghiệp vụ; UI hiển thị và tiếp nhận thao tác.
Không đặt thuật toán hoặc xử lý nghiệp vụ trong `app.py`.

Dự án là ứng dụng Streamlit chạy trực tiếp từ `src/app.py`; uv quản lý môi trường
và dependencies, không đóng gói ứng dụng thành thư viện Python.

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

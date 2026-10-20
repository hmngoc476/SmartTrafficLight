# Smart Traffic Light Simulator

**Ứng dụng mô phỏng và điều khiển đèn giao thông thích nghi tại một ngã tư bằng Python**

Đồ án **Python Module 1**: vận dụng lập trình hướng đối tượng (OOP), cấu trúc dữ liệu, thuật toán và kiến trúc phân tầng để mô phỏng dòng xe, điều khiển tín hiệu và quan sát kết quả trên giao diện web Streamlit.

> **Phạm vi:** Mô hình học thuật của **một ngã tư, bốn hướng, hai pha NS/EW**. Đây **không phải** hệ thống điều khiển đèn giao thông ngoài thực địa hay phần mềm bảo đảm an toàn giao thông thực tế.

## Mục lục

1. [Tổng quan và tính năng](#1-tổng-quan-và-tính-năng)
2. [Công nghệ và yêu cầu môi trường](#2-công-nghệ-và-yêu-cầu-môi-trường)
3. [Cài đặt và khởi chạy](#3-cài-đặt-và-khởi-chạy)
4. [Hướng dẫn sử dụng](#4-hướng-dẫn-sử-dụng)
5. [Nguyên lý mô phỏng](#5-nguyên-lý-mô-phỏng)
6. [Kiến trúc và cấu trúc thư mục](#6-kiến-trúc-và-cấu-trúc-thư-mục)
7. [Cấu hình và dữ liệu](#7-cấu-hình-và-dữ-liệu)
8. [Chỉ số, báo cáo và so sánh thuật toán](#8-chỉ-số-báo-cáo-và-so-sánh-thuật-toán)
9. [Kiểm thử và điều kiện bàn giao](#9-kiểm-thử-và-điều-kiện-bàn-giao)
10. [Quy trình Git/GitHub và thành viên](#10-quy-trình-gitgithub-và-thành-viên)
11. [Các vấn đề thường gặp](#11-các-vấn-đề-thường-gặp)
12. [Giới hạn và tài liệu tham khảo](#12-giới-hạn-và-tài-liệu-tham-khảo)

---

## 1. Tổng quan và tính năng

### 1.1. Bài toán

Tại một ngã tư, lưu lượng xe theo trục **Bắc–Nam (NS)** và **Đông–Tây (EW)** thường không đồng đều. Việc cấp thời gian xanh cố định có thể làm một hướng chờ quá lâu trong khi hướng khác ít xe. Dự án thử nghiệm **phân bổ thời gian xanh theo lượng xe chưa vượt vạch**, so sánh với điều khiển **Fixed-Time** và minh họa chuyển động của từng xe trong không gian 2D.

### 1.2. Những chức năng có trong source

| Nhóm | Chức năng |
| --- | --- |
| Quản lý cấu hình | Tạo, xem, chỉnh sửa, xóa, chọn cấu hình; kiểm tra dữ liệu; lưu/đọc lại từ JSON V2. |
| Sinh xe | Mỗi hướng N/S/E/W sinh xe theo phân phối Poisson, có `seed` để tái lập. |
| Điều khiển đèn | Sáu đoạn tín hiệu, hai pha xanh NS/EW, phân bổ Adaptive có thời gian xanh tối thiểu, kiểm soát vùng xung đột. |
| Mô phỏng 2D | Xe đi thẳng, tăng tốc/dừng, xếp hàng FIFO, giữ khoảng cách, vượt vạch và rời phạm vi mô phỏng. |
| Điều khiển phiên | Start, Pause, Resume, Stop, Reset, Step +1s, chạy đến hết chu kỳ; chế độ tự tiến theo nhịp trình duyệt. |
| Dashboard | Đèn hiện tại, thời gian còn lại, chu kỳ, các Queue, số xe đến/qua/ra khung, biểu đồ và chỉ số an toàn. |
| Lưu kết quả | Ghi lịch sử phiên và các chu kỳ đã chốt vào CSV; tải CSV tổng hợp từ Tab 2. |
| So sánh phiên trên trình duyệt | Đối chứng phiên Adaptive vừa kết thúc với Fixed-Time, hiển thị bảng và tải CSV so sánh theo đúng cấu hình đã chạy. |
| Thí nghiệm độc lập | So sánh Adaptive và Fixed-Time trên **cùng luồng xe sinh** và **cùng thời gian quan sát** bằng dòng lệnh. |
| Kiểm thử | Các bài test cho Models, thuật toán, chuyển động, Controller, lưu trữ, giao diện và báo cáo. |

### 1.3. Phạm vi giao thông

- **Một giao lộ chữ thập**, bốn hướng tiếp cận: `N`, `S`, `E`, `W`; **một làn đầu vào cho mỗi hướng**.
- Xe **chỉ đi thẳng**; không mô phỏng rẽ, người đi bộ, phương tiện ưu tiên hoặc nhiều nút giao liên thông.
- Hai trục tín hiệu **NS/EW không được xanh xung đột**. Có các đoạn vàng và tất cả đỏ (all-red).
- Hệ tọa độ 2D: **`+x` hướng Đông, `+y` hướng Nam**. Vị trí xe trong thế giới mô phỏng được đo bằng mét.
- `motion_2d.enabled=false` **chỉ tắt phần hiển thị xe trên bản đồ**; Core vẫn mô phỏng, tính toán xe và các chỉ số.

Xem bản vẽ tham khảo: [Tab 1 – Quản lý cấu hình](docs/wireframes/tab1_config.png) và [Tab 2 – Mô phỏng](docs/wireframes/tab2_simulation.png). Đây là **wireframe thiết kế**, không phải ảnh chụp kết quả kiểm thử.

---

## 2. Công nghệ và yêu cầu môi trường

| Thành phần | Mục đích |
| --- | --- |
| **Python >= 3.13** | Viết Models, thuật toán và SimulationEngine. |
| **uv** | Tạo/đồng bộ môi trường, cài thư viện từ `pyproject.toml` và `uv.lock`. |
| **Streamlit** | Ứng dụng web gồm hai tab quản lý và mô phỏng. |
| **Plotly** | Vẽ giao lộ, xe, tín hiệu và đồ thị số liệu. |
| **pandas** | Hỗ trợ xử lý và hiển thị dữ liệu trong giao diện. |
| **pytest** | Kiểm thử tự động (nhóm dependency dành cho phát triển). |
| **Git/GitHub** | Quản lý mã nguồn, nhánh, Pull Request và review. |
| **JSON / CSV** | Lưu cấu hình và lịch sử mà không cần hệ quản trị cơ sở dữ liệu. |

**Yêu cầu:** Python 3.13 trở lên, `uv`, trình duyệt web và terminal (PowerShell, CMD, Bash...). Nên chạy ứng dụng từ **thư mục gốc dự án** để đường dẫn dữ liệu và tài nguyên UI được nhận đúng.

Không yêu cầu cài đặt MySQL, PostgreSQL, camera, YOLO hay SUMO.

---

## 3. Cài đặt và khởi chạy

### 3.1. Lấy mã nguồn

**Cách 1 – Dùng file ZIP đã cung cấp:** giải nén, mở terminal tại thư mục chứa `pyproject.toml`, ví dụ `SmartTrafficLight-main/`.

**Cách 2 – Clone GitHub** (tài khoản phải có quyền truy cập nếu repository là private):

```bash
git clone https://github.com/hmngoc476/SmartTrafficLight.git
cd SmartTrafficLight
```

### 3.2. Đồng bộ môi trường

```bash
python --version
uv --version
uv sync
```

`uv sync` cài các dependencies từ `pyproject.toml` và khóa phiên bản theo `uv.lock`. Không commit thư mục `.venv/` lên GitHub.

### 3.3. Mở ứng dụng

```bash
uv run streamlit run src/app.py
```

Mở URL cục bộ do Streamlit hiển thị (thường là `http://localhost:8501`). Dừng ứng dụng bằng **Ctrl + C** trong terminal.

### 3.4. Chạy lần đầu

File `data/junctions.json` trong bản bàn giao hiện có cấu hình mẫu `JCT-001`, có thể chọn để chạy ngay. Các cấu hình tạo hoặc cập nhật trên giao diện cũng được lưu trong file này.

Nếu file chưa tồn tại, ứng dụng tự tạo dữ liệu rỗng theo JSON V2:

```json
{
  "schema_version": 2,
  "configs": []
}
```

Khi danh sách cấu hình rỗng, trong Tab **Quản lý cấu hình**, bấm **Tạo cấu hình mẫu** hoặc **Tạo mới**, nhập tên, chọn tham số rồi lưu. Sau đó bấm **Dùng cấu hình này** và chuyển sang Tab **Mô phỏng và phân tích**.

Đường dẫn JSON/CSV được xác định từ thư mục gốc dự án, không phụ thuộc thư mục chạy lệnh; ứng dụng không tạo thêm `src/data`.

---

## 4. Hướng dẫn sử dụng

### 4.1. Tab 1 – Quản lý cấu hình

Tab này quản lý các cấu hình được lưu trong `data/junctions.json`.

1. **Chọn theo ID:** xem thông số cấu hình đã lưu (ví dụ `JCT-001`).
2. **Tạo mới:** tạo biểu mẫu mới và điền đủ thông tin bắt buộc; bấm **Lưu cấu hình**.
3. **Cập nhật:** chỉnh thông số và bấm **Cập nhật** để ghi lại JSON. Việc thay đổi ô nhập **chưa phải là lưu**.
4. **Xóa · cần xác nhận:** loại bỏ cấu hình sau khi xác nhận; thao tác bị hạn chế khi cấu hình đó đang được dùng trong một phiên chạy/tạm dừng.
5. **Dùng cấu hình này:** đánh dấu cấu hình được chọn để **Start phiên tiếp theo**; tránh vô tình chạy một ID khác.
6. **Làm mới biểu mẫu:** quay lại dữ liệu đã lưu; nếu có thay đổi chưa lưu, UI yêu cầu xác nhận bỏ thay đổi.

Dữ liệu được kiểm tra bởi `Config`/`ConfigManager`, bao gồm kiểu số, phạm vi, đủ bốn hướng, thời lượng xanh, tham số chuyển động và ID. Thông báo lỗi hiển thị tại giao diện; không tự ép chuỗi hoặc số thực thành thời lượng nguyên.

### 4.2. Tab 2 – Mô phỏng và phân tích

- **Start:** bắt đầu phiên mới với cấu hình đã chọn và lưu; dữ liệu phiên được chốt khi Start.
- **Pause / Resume:** tạm dừng hoặc tiếp tục mô phỏng đang chạy.
- **Stop:** kết thúc sớm phiên đang chạy hoặc tạm dừng; có thể lưu lịch sử phiên đã dừng.
- **Reset:** xóa tiến độ mô phỏng hiện tại, quay về trạng thái ban đầu của **cùng bản cấu hình đã chốt và cùng seed**. Sau Reset, bấm **Start** để phát lại.
- **Step +1s:** khi đã Start và đang **PAUSED**, tiến thêm đúng một giây mô phỏng.
- **Chạy hết chu kỳ:** khi **PAUSED**, chạy tới khi chu kỳ hiện tại hoàn tất thực tế, bao gồm thời gian giữ tất cả đỏ nếu có.

Trạng thái thường gặp:

| Trạng thái | Ý nghĩa |
| --- | --- |
| `IDLE` | Chưa có Engine/phiên mô phỏng. |
| `RUNNING` | Đang chạy và tiếp nhận nhịp tự động. |
| `PAUSED` | Chưa Start sau Reset/khởi tạo, hoặc phiên đã chạy và đang tạm dừng (phân biệt bằng `has_started`). |
| `STOPPED` | Phiên được người dùng dừng hoặc kết thúc theo thời gian quan sát riêng. |
| `COMPLETED` | Đã chạy đủ `cycles_to_run` chu kỳ theo cấu hình. |
| `ERROR` | Phát hiện tình huống lỗi/bất biến hoặc vượt giới hạn an toàn; Controller chuyển về cơ chế fail-safe. |

Số **chu kỳ** trên dashboard có dạng `chu kỳ hiện tại / tổng số chu kỳ đã chốt khi Start`. Tổng số không được thay đổi giữa phiên chỉ vì người dùng chỉnh cấu hình ở Tab 1.

### 4.3. Cập nhật cấu hình khi mô phỏng đang dùng bản cũ (ví dụ 10 → 3 chu kỳ)

Đây là cơ chế đã bổ sung để xử lý trường hợp giao diện vẫn hiện `1 / 10` sau khi bạn lưu cấu hình mới thành `3` chu kỳ.

1. Trong Tab 1, sửa **Số chu kỳ** thành `3` rồi bấm **Cập nhật** để lưu vào JSON. Nếu cần, bấm **Dùng cấu hình này** để xác nhận ID muốn chạy.
2. Phiên đang chạy **vẫn giữ 10 chu kỳ**, vì Engine đã nhận bản cấu hình chốt ban đầu. Tab 2 hiển thị cảnh báo khi cấu hình đã lưu khác bản chốt.
3. Nếu phiên `RUNNING`, hãy **Pause** hoặc **Stop**.
4. Bấm **Áp dụng cấu hình đã lưu (3 chu kỳ) và chạy phiên mới**, sau đó xác nhận.
5. Ứng dụng tạo **Engine mới** từ cấu hình đã lưu; dashboard phiên mới bắt đầu từ `1 / 3`.

**Phân biệt ba thao tác quan trọng:**

| Thao tác | Sử dụng cấu hình nào? | Kết quả |
| --- | --- | --- |
| **Cập nhật** tại Tab 1 | Ghi thông số mới vào JSON | Không thay đổi Engine/tiến độ của phiên đã Start. |
| **Reset → Start** | Bản chốt/seed của phiên cũ | Phát lại phiên cũ; có thể vẫn là `1 / 10`. |
| **Áp dụng cấu hình đã lưu và chạy phiên mới** | Dữ liệu đã lưu mới nhất của ID đang chọn dùng | Tạo phiên mới, ví dụ `1 / 3`. |
| **Stop → Start** | Cấu hình đã lưu của ID đang chọn dùng | Một cách khác để mở phiên mới mà không dùng nút áp dụng. |

Nếu chỉ sửa ô nhập mà chưa bấm **Cập nhật**, hoặc đang chọn một ID khác nhưng chưa bấm **Dùng cấu hình này**, lần chạy tiếp theo có thể chưa dùng đúng thông số bạn muốn.

### 4.4. Những gì hiển thị trên dashboard

Bản đồ 2D và cụm chỉ số lấy từ `SimulationSnapshot`/`DashboardData` của Core, không tự sinh xe hay tính lại đèn trong UI:

- Màu đèn, đoạn tín hiệu, số giây còn lại, giây mô phỏng, chỉ số chu kỳ.
- Queue theo `N`, `S`, `E`, `W` và tổng NS/EW; xe chưa qua vạch vẫn nằm trong FIFO.
- Số xe ban đầu, xe mới đến, xe vượt vạch, xe đã ra khung, xe còn chờ.
- Vùng xung đột, `min_gap_m` cấu hình, khoảng cách đo được và clearance hold.
- Biểu đồ độ dài Queue theo thời gian, thời gian xanh theo chu kỳ, arrivals/departures.
- Thống kê cuối phiên và chức năng tải CSV khi phiên kết thúc hợp lệ.
- Bảng so sánh với Fixed-Time khi chạy đủ số chu kỳ đã cấu hình (`COMPLETED`): cùng bản cấu hình đã chốt, seed và thời gian mô phỏng.

---

## 5. Nguyên lý mô phỏng

### 5.1. Cấu trúc dữ liệu được sử dụng

| Cấu trúc | Nơi sử dụng | Vai trò |
| --- | --- | --- |
| **`dict` (Hash Map)** | ConfigManager, ánh xạ Lane theo hướng, quản lý xe đang trong giao lộ | Tra cứu theo ID/hướng; quản lý dữ liệu cấu hình, trạng thái. |
| **`collections.deque` (Queue FIFO)** | `Lane`, `SignalPlan` | Xe vào cuối hàng và qua vạch theo thứ tự đầu hàng; quản lý sáu đoạn tín hiệu tuần tự. |
| `set` | Thống kê/crossing ID | Ngăn ghi trùng sự kiện xe đã vượt vạch. |
| `list` / `tuple` | Lịch sử tick, thống kê, snapshot và báo cáo | Lưu dữ liệu quan sát theo thời gian và trả dữ liệu chỉ đọc. |

Hai cấu trúc dữ liệu nòng cốt của đồ án là **`dict` và `deque`**, có ứng dụng trực tiếp vào nghiệp vụ chứ không chỉ khai báo cho đủ yêu cầu.

### 5.2. Sinh xe theo Poisson

Mỗi giây logic, mỗi hướng được lấy mẫu số xe mới độc lập từ lưu lượng cấu hình `r_d` (xe/phút):

```text
lambda_d = r_d / 60                 # kỳ vọng xe trong 1 giây
A_d(t) ~ Poisson(lambda_d)          # số xe mới tại hướng d, tick t
```

Engine sở hữu `random.Random(seed)`, gọi theo thứ tự các hướng N/S/E/W. Với cùng cấu hình, seed và chính sách, hệ thống có thể tái lập mô phỏng khi Reset/phát lại từ đầu.

### 5.3. Phân bổ đèn xanh Adaptive + min green

Tại **đầu chu kỳ**, tính:

```text
q_NS = Queue[N] + Queue[S]
q_EW = Queue[E] + Queue[W]
g_NS + g_EW = green_budget_s
min(g_NS, g_EW) >= min_green_s
```

Khi có xe chờ, thời gian xanh được phân chia ban đầu theo tỷ trọng `q_NS : q_EW`, sau đó hiệu chỉnh giới hạn tối thiểu và làm tròn; khi cả hai Queue rỗng, thời gian xanh chia gần đều. **Thời lượng xanh đã chốt không bị sửa giữa chu kỳ**.

Ví dụ với `q_NS=11`, `q_EW=21`, ngân sách xanh `60s`, xanh tối thiểu `10s`:

```text
Adaptive: NS = 21s, EW = 39s
Fixed-Time (đối chứng): NS = 30s, EW = 30s
```

Đây là phiên bản thuật toán phù hợp đồ án, không phải toàn bộ thuật toán gốc của những bài báo tham khảo.

### 5.4. Sáu đoạn tín hiệu và an toàn chuyển pha

```text
NS_GREEN → NS_YELLOW → ALL_RED_1 → EW_GREEN → EW_YELLOW → ALL_RED_2
    ↑                                                        │
    └────────────── chu kỳ tiếp theo (nếu còn) ──────────────┘
```

Với tổng ngân sách xanh `60s`, vàng `3s` mỗi pha và tất cả đỏ `1s` mỗi lần, **chu kỳ danh định = 68 giây**. Chu kỳ thực tế có thể **dài hơn** nếu vùng xung đột chưa trống và phải giữ `ALL_RED` (clearance hold). Nếu quá `clearance_limit_s`, Core chuyển `ERROR` và giữ tín hiệu an toàn.

### 5.5. Chuyển động phương tiện

- Logic đèn và sinh xe chạy theo **tick 1 giây**; chuyển động chia thành `1 / dt_s` substep, mặc định `dt_s=0.2` nghĩa là **5 bước/giây**.
- Xe trước vạch nằm trong Queue của làn, tiến tới vạch và dừng khi chưa được phép qua.
- Chỉ xe **đầu Queue** được vượt vạch khi tín hiệu GREEN hợp lệ, thỏa `startup_delay_s`, `headway_s` và quy tắc hình học.
- Sau crossing, xe chuyển sang `active_crossing`; sau khi rời biên mô phỏng, xe chuyển sang nhóm exited. **Một xe chỉ được ghi crossing một lần**.
- Xe cùng làn phải giữ tối thiểu `min_gap_m`; vùng xung đột được kiểm tra theo **hình bao xe**. Bề rộng thân xe mô phỏng hiện được cố định trong Core là **1,8 m**.
- Core kiểm tra trạng thái xe, thời gian đèn và các bất biến; Renderer chỉ vẽ snapshot, không điều khiển vật lý.

### 5.6. Các bất biến quan trọng

```text
Số xe ban đầu + Số xe mới đến = Số xe chưa qua vạch + Số xe đã qua vạch
Số xe đã qua vạch = Số xe đang qua giao lộ + Số xe đã rời thế giới
Tổng xanh mỗi chu kỳ = green_budget_s
Mỗi pha xanh >= min_green_s
```

Ngoài ra: không được có hai hướng xung đột cùng xanh; không crossing khi pha vàng/đỏ; khoảng cách an toàn cùng làn phải giữ đúng. Các điều kiện trên được kiểm thử trong `tests/`.

---

## 6. Kiến trúc và cấu trúc thư mục

### 6.1. Nguyên tắc phân tầng

```text
Streamlit UI (Tab 1 / Tab 2)
        │      chỉ gọi API công khai, đọc snapshot
        ▼
Core Logic (SimulationEngine / Controller / Movement / Statistics / Storage)
        │      thao tác thông qua Models
        ▼
Models & Data (Config, Vehicle, Lane, SignalPlan, Snapshot, JSON/CSV)
```

- **Models:** định nghĩa thực thể, kiểu dữ liệu và kiểm tra bất biến; tránh phụ thuộc widget Streamlit.
- **Core:** quản lý thời gian, thuật toán, vật lý đơn giản, thống kê và lưu trữ; có thể chạy/kiểm thử không cần UI.
- **UI:** nhận thao tác, tạo/chọn phiên và hiển thị snapshot; không tự ý truy cập `Lane._queue`, sửa tọa độ xe hoặc tự tính Adaptive.

### 6.2. Cấu trúc source hiện có (rút gọn)

```text
SmartTrafficLight-main/
├── .streamlit/config.toml       # Theme Streamlit
├── data/
│   ├── junctions.json          # Cấu hình JSON V2
│   ├── sim_history.csv         # Sinh khi lưu lịch sử phiên
│   └── cycle_metrics.csv       # Sinh khi lưu chu kỳ đã chốt
├── docs/
│   ├── examples/               # Dữ liệu mẫu / snapshot minh họa
│   ├── schema/                 # JSON Schema V2
│   ├── testcases/              # Test case và điều kiện kiểm tra
│   ├── wireframes/             # Ảnh thiết kế hai tab
│   ├── ui_core_integration.md  # Hợp đồng tích hợp UI–Core
│   ├── core_day18_19.md        # Hợp đồng Core
│   └── ...                     # Các tài liệu thiết kế/kiểm chứng khác
├── src/
│   ├── app.py                  # Điểm vào Streamlit
│   ├── models/
│   │   ├── config.py           # Config / Motion2DConfig
│   │   ├── vehicle.py          # Phương tiện và trạng thái
│   │   ├── lane.py             # FIFO Queue
│   │   ├── signal.py           # SignalSegment / SignalPlan
│   │   └── snapshot.py         # DTO chỉ đọc cho giao diện
│   ├── core/
│   │   ├── algorithms.py       # Poisson / Adaptive / Fixed-Time
│   │   ├── controller.py       # Điều khiển sáu đoạn tín hiệu
│   │   ├── movement.py         # Chuyển động / khoảng cách / crossing
│   │   ├── geometry.py         # Hệ tọa độ và vùng xung đột
│   │   ├── simulation.py       # Vòng đời phiên và tick
│   │   ├── statistics.py       # Thống kê tick/chu kỳ/phiên
│   │   ├── reporting.py        # DTO dashboard
│   │   ├── manager.py          # CRUD cấu hình
│   │   ├── storage.py          # JSON và cơ chế ghi file
│   │   ├── history_storage.py  # CSV lịch sử
│   │   ├── arrivals.py         # ArrivalTape tái lập
│   │   ├── comparison.py       # So sánh hai chính sách
│   │   └── experiment.py       # CLI chạy kịch bản và xuất JSON
│   └── ui/
│       ├── config_tab.py       # Tab 1
│       ├── simulation_tab.py   # Tab 2 / vòng đời UI
│       ├── comparison_panel.py # So sánh phiên vừa chạy và tải CSV đối chứng
│       ├── form.py / state.py  # Form và session_state
│       ├── renderer_2d.py      # Vẽ bản đồ Plotly
│       ├── charts.py          # Biểu đồ
│       ├── timer.py           # Cầu nối đồng hồ trình duyệt
│       ├── clock/index.html   # Component đồng hồ
│       └── styles.css         # Kiểu giao diện
├── tests/                      # Các test_*.py
├── pyproject.toml              # Phụ thuộc dự án
├── uv.lock                     # Khóa dependencies
├── .gitignore
└── README.md
```

**Lưu ý:** `sim_history.csv` và `cycle_metrics.csv` được tạo trong lúc sử dụng, không bắt buộc có sẵn trong ZIP; chúng thuộc `.gitignore`.

### 6.3. Các lớp chính

| Lớp / cấu trúc | Trách nhiệm chính |
| --- | --- |
| `Config`, `Motion2DConfig` | Kiểm tra và biểu diễn tham số JSON V2. |
| `Vehicle`, `Lane` | Trạng thái một xe và hàng xe FIFO. |
| `SignalSegment`, `SignalPlan` | Dữ liệu các đoạn tín hiệu và thứ tự chu kỳ. |
| `TrafficLightController` | Phân bổ xanh, chuyển tín hiệu, chờ giải phóng vùng xung đột và fail-safe. |
| `MovementEngine`, `Geometry` | Sinh/di chuyển xe, hình học, khoảng cách và rời phạm vi. |
| `SimulationEngine` | Start/pause/resume/stop/reset, tick, tạo snapshot và điều phối Core. |
| `SimulationStats`, `HistoryStorage` | Thống kê và ghi kết quả CSV. |
| `ConfigManager`, `FileStorage` | CRUD và lưu/đọc cấu hình JSON. |

---

## 7. Cấu hình và dữ liệu

### 7.1. JSON V2

Mỗi tệp cấu hình có cấu trúc gốc **`{"schema_version": 2, "configs": [...]}`**; từng phần tử `configs` phải có đủ và đúng các trường của `Config`. Bản mẫu nằm tại [docs/examples/junctions_v2.example.json](docs/examples/junctions_v2.example.json).

Ví dụ một cấu hình hoàn chỉnh:

```json
{
  "id": "JCT-001",
  "name": "Giao lộ mẫu - lệch hướng Đông Tây",
  "rates_per_min": {"N": 12, "S": 9, "E": 18, "W": 7},
  "initial_queue": {"N": 7, "S": 4, "E": 16, "W": 5},
  "green_budget_s": 60,
  "min_green_s": 10,
  "yellow_s": 3,
  "all_red_s": 1,
  "startup_delay_s": 2,
  "headway_s": 2,
  "cycles_to_run": 3,
  "seed": 2026,
  "motion_2d": {
    "enabled": true,
    "dt_s": 0.2,
    "vehicle_length_m": 4.5,
    "min_gap_m": 2.0,
    "max_speed_mps": 9.0,
    "accel_mps2": 2.0,
    "approach_visible_m": 60.0,
    "intersection_width_m": 16.0,
    "stop_margin_m": 0.5,
    "clearance_limit_s": 30.0
  }
}
```

> Khối trên là **một phần tử của `configs`**, không phải toàn bộ nội dung của `junctions.json`. Nếu chỉnh file JSON thủ công, phải đặt nó trong danh sách `configs` và giữ `schema_version: 2`. Nên sử dụng giao diện Tab 1 để tránh ghi sai định dạng.

### 7.2. Những ràng buộc đáng chú ý

| Tham số | Đơn vị / điều kiện |
| --- | --- |
| `rates_per_min.N/S/E/W` | Số hữu hạn trong `[0, 30]` xe/phút. |
| `initial_queue.N/S/E/W` | Số nguyên trong `[0, 100]` xe. |
| `green_budget_s` | Tổng số giây xanh nguyên; `>= 2 * min_green_s`. |
| `min_green_s` | Số nguyên `>= 1`. |
| `yellow_s`, `all_red_s`, `headway_s` | Số nguyên `>= 1`. |
| `startup_delay_s` | Số nguyên `>= 0`. |
| `cycles_to_run` | Số nguyên từ `1` tới `100`. |
| `seed` | Số nguyên để tái lập. |
| `motion_2d.dt_s` | Số dương `<= 1`, và `1 / dt_s` phải là số nguyên. |
| `motion_2d.intersection_width_m` | Tối thiểu `3.6m` (2 làn, mỗi xe rộng 1.8m). |
| Tốc độ, gia tốc, chiều dài xe và kích thước thế giới | Các tham số dương; `min_gap_m` và `stop_margin_m` không âm. |

### 7.3. Lưu dữ liệu an toàn

- `ConfigManager` cung cấp API xem/tạo/sửa/xóa; `FileStorage` xử lý JSON và kiểm tra định dạng.
- Mỗi cấu hình có ID riêng, không được đổi ID khi **Cập nhật**.
- Storage dùng ghi tệp tạm và `os.replace` nhằm giảm rủi ro làm hỏng JSON; cache chỉ cập nhật sau khi thao tác lưu thành công.
- Dữ liệu nhập sai, trường thiếu/thừa, giá trị không hữu hạn và khóa JSON trùng có thể bị từ chối.
- **Sao lưu `data/junctions.json`** trước khi thay source hoặc ghi dữ liệu thủ công. Đây là tệp có thể thay đổi sau khi dùng giao diện.

---

## 8. Chỉ số, báo cáo và so sánh thuật toán

### 8.1. Chỉ số quan sát

| Chỉ số | Cách hiểu |
| --- | --- |
| `initial_total`, `total_arrivals` | Tổng xe có sẵn và số xe mới sinh. |
| `crossed_stop_total` / `departed_vehicles` | Số xe đã vượt vạch dừng (đếm một lần mỗi xe). |
| `exited_world_total` | Số xe đã rời biên mô phỏng; **không đồng nghĩa** xe vừa vượt vạch. |
| `remaining_vehicles`, `queue_lengths` | Xe chưa vượt vạch còn trong hàng. |
| `avg_wait_departed_s` | Trung bình thời gian từ khi xe xuất hiện đến lúc vượt vạch, trên các xe đã vượt. |
| `avg_stopped_delay_s` | Trung bình thời gian dừng trước vạch của xe đã vượt. |
| `avg_queue`, `max_queue` | Queue trung bình và lớn nhất theo các tick đã quan sát. |
| `clearance_hold_s` | Thời gian kéo dài tất cả đỏ để chờ vùng xung đột trống. |
| `green_ns_s`, `green_ew_s` | Thời lượng xanh đã chốt của chu kỳ. |

**Không được mặc định Adaptive luôn tốt hơn Fixed-Time.** Cần cùng chuỗi xe và thời gian quan sát mới so sánh công bằng.

### 8.2. Lịch sử JSON/CSV

| Tệp | Nội dung / thời điểm tạo |
| --- | --- |
| `data/junctions.json` | Cấu hình đã lưu; đọc khi mở ứng dụng. |
| `data/sim_history.csv` | Một dòng tổng hợp cho mỗi phiên `STOPPED`/`COMPLETED`, định danh bằng `run_id`. |
| `data/cycle_metrics.csv` | Các chu kỳ **đã hoàn tất** của từng phiên, khóa `run_id` + `cycle_index`. |
| CSV tải từ Tab 2 | File tải trực tiếp gồm phần summary và (nếu có) phần chu kỳ, hai phần cách nhau bởi dòng trống. |
| `<run_id>_comparison.csv` | Tải bằng **Tải CSV so sánh**: mỗi dòng là một chỉ số, có giá trị Adaptive/Fixed-Time, chênh lệch và phần trăm cải thiện. |

Hai file lịch sử được ghi riêng bằng thao tác thay thế nguyên tử; nếu chỉ một file ghi thành công, UI giữ bản báo cáo trong phiên trình duyệt và cho phép **Thử lại ghi lịch sử**. Một phiên `ERROR` có dữ liệu chẩn đoán trên dashboard nhưng không tự ghi thành phiên `COMPLETED` trong CSV.

> **Giới hạn:** Cơ chế thử lại trong `session_state` không phải nhật ký giao dịch bền vững; nếu đóng phiên trình duyệt/server trước khi ghi được CSV, dữ liệu đang giữ trong RAM có thể mất. Không xóa hai file CSV nếu cần giữ lịch sử.

Để so sánh **cấu hình mới bạn vừa chạy trên trình duyệt**:

1. Tạo/lưu cấu hình ở Tab 1, chọn **Dùng cấu hình này**, rồi **Start** ở Tab 2.
2. Chạy đủ số chu kỳ đã cấu hình để phiên chuyển sang **COMPLETED**. Có thể dùng **Pause → Chạy hết chu kỳ** nhiều lần đến khi hoàn tất. Bấm **Stop** sớm sẽ không được so sánh, kể cả khi vừa kết thúc một chu kỳ nhưng chưa đủ tổng số chu kỳ.
3. Bấm **So sánh với Fixed-Time** ở cuối Tab 2. Việc so sánh chỉ bắt đầu khi bấm nút, không tự chạy khi phiên hoàn tất. Hệ thống tái lập và kiểm chứng kết quả Adaptive, sau đó đối chiếu với Fixed-Time trên cùng chuỗi xe đến và đúng số giây của phiên vừa chạy.
4. Xem bảng và bấm **Tải CSV so sánh**. Nút **Xuất CSV** cũ vẫn tải summary/chu kỳ của phiên Adaptive.

So sánh dùng **bản cấu hình đã chốt khi Start**, kể cả khi cấu hình ở Tab 1 đã được sửa sau đó. Fixed-Time chia gần đều tổng ngân sách xanh; ví dụ 60 giây thành NS 30s/EW 30s. Số chu kỳ hoàn tất của hai chế độ có thể khác nhau. Phiên đối chứng không ghi thêm vào `sim_history.csv` hoặc `cycle_metrics.csv`.

CSV so sánh là một bảng duy nhất, mã hóa UTF-8 có BOM để mở bằng Excel. File giữ `run_id`, seed, thời gian quan sát, trạng thái hai chế độ và toàn bộ cấu hình đã dùng trong `config_json`. `adaptive_minus_fixed` là Adaptive trừ Fixed; `improvement_pct` dương nghĩa là Adaptive tốt hơn theo chiều đánh giá của chỉ số đó. Giá trị thiếu, mốc Fixed bằng 0 và chỉ số dùng giải thích như clearance hold/chu kỳ không có phần trăm cải thiện. Nếu Fixed-Time gặp lỗi hoặc chưa đủ thời gian, `comparable=False`, các cột chênh lệch/phần trăm để trống và file chỉ dùng chẩn đoán.

Thời gian dừng trung bình chỉ tính trên xe đã vượt vạch. Đây là kết quả **một kịch bản, một seed**; dùng thêm bộ CLI bên dưới khi cần kết luận qua nhiều seed. Kết quả so sánh chỉ giữ trong phiên trình duyệt; tải CSV trước khi Reset, Start phiên mới hoặc đóng app.

### 8.3. So sánh Adaptive và Fixed-Time bằng CLI

Để đánh giá khách quan, Core sử dụng cùng **ArrivalTape** (chuỗi số xe đến theo tick/hướng) cho hai thuật toán và chạy trên cùng `H` giây. Số chu kỳ hoàn tất của hai chính sách **không bắt buộc bằng nhau**, vì có thể có clearance hold khác nhau.

Chạy bộ **6 kịch bản × 10 seed**, với `H=180s`:

```bash
uv run python -m src.core.experiment --horizon 180 --output reports/comparison.json
```

Các kịch bản gồm `empty`, `balanced`, `ns_heavy`, `ew_heavy`, `peak`, `clearance`; kết quả ở `reports/comparison.json` chứa từng cặp so sánh và các thống kê tổng hợp. Đây là **JSON báo cáo thí nghiệm**, khác với các tệp CSV lịch sử của giao diện.

Muốn thử ít seed hơn:

```bash
uv run python -m src.core.experiment --horizon 180 --seeds 0 1 --output reports/comparison_small.json
```

Có thể gọi từ Python:

```python
from src.models.config import Config
from src.core.comparison import compare_policies

result = compare_policies(Config(seed=42), horizon_s=180)
print(result.to_dict())
```

Trường `comparable` chỉ là `True` khi cả hai chính sách đi đủ thời gian quan sát và không rơi vào trạng thái ERROR; không đánh giá bằng trực giác từ bản đồ.

---

## 9. Kiểm thử và điều kiện bàn giao

### 9.1. Chạy kiểm thử

Từ thư mục gốc dự án:

```bash
uv sync
uv run --frozen pytest -q -ra
```

Pytest dùng `.pytest_tmp/` và cache `.pytest_cache_local/` trong thư mục dự án để tránh lỗi quyền truy cập thư mục tạm trong `AppData` và cache cũ trên Windows. Hai thư mục đã được Git bỏ qua; riêng `.pytest_tmp/` được tạo lại mỗi lần chạy test, không lưu dữ liệu cần giữ vào đây.

Trên Windows, không dùng chung thư mục tạm/cache giữa terminal cá nhân và tài khoản sandbox: pytest có thể giới hạn quyền theo tài khoản tạo thư mục. Khi chạy tự động bằng tài khoản khác, cần chỉ định đường dẫn riêng qua `--basetemp` và `-o cache_dir=...`.

Kiểm tra cú pháp toàn bộ source (bổ trợ, không thay thế pytest):

```bash
uv run python -m compileall -q src
```

Các thư mục/bộ test hiện có bao phủ:

- Cấu hình và persistence JSON/CSV: `test_config.py`, `test_storage.py`, `test_storage_crud.py`, `test_history_storage.py`.
- Queue, Vehicle, Signal và Snapshot: `test_lane.py`, `test_vehicle.py`, `test_signal.py`, `test_snapshot.py`, `test_fifo_day14.py`.
- Poisson/Adaptive/Fixed-Time và Controller: `test_algorithms.py`, `test_controller.py`, `test_comparison_day19.py`.
- Chuyển động/hình học/gap/headway và thống kê: `test_geometry.py`, `test_physics_day18.py`, `test_headway_across_cycles.py`, `test_statistics_day19.py`, `test_simulation_*.py`.
- Giao diện và vòng đời phiên: `test_ui_runtime.py`, `test_ui_storage_contracts.py`, `test_reporting_api.py`.

Các báo cáo kiểm thử tại [docs/core_day18_19_results.md](docs/core_day18_19_results.md) và [docs/ui_core_integration_results.md](docs/ui_core_integration_results.md) ghi nhận **kết quả ở mốc phát triển tương ứng**, không tự thay thế việc chạy lại test trên ZIP/source đang bàn giao.

### 9.2. Quy trình kiểm tra nhanh trước khi nộp

1. Giải nén hoặc clone source vào thư mục mới; `uv sync` không lỗi.
2. Chạy `uv run --frozen pytest -q -ra` và xử lý test fail nếu có.
3. Mở Streamlit; tạo cấu hình, thử **Lưu/Cập nhật/Xóa** và đọc lại JSON.
4. Chạy Start → Pause → Step +1s → Resume → Stop/Reset, quan sát xe và tín hiệu.
5. Kiểm tra một phiên `COMPLETED`, biểu đồ và khả năng ghi/tải CSV.
6. Kiểm tra đổi `cycles_to_run` từ **10 sang 3**: bản đang chạy không bị sửa; áp dụng cấu hình mới tạo phiên **`1 / 3`**.
7. Kiểm tra `git status`, bảo đảm không commit `.venv/`, file cache, CSV runtime, IDE metadata hoặc thông tin nhạy cảm.
8. Kiểm tra README, PR review, tag/release candidate (nếu nhóm yêu cầu) và khả năng demo trên máy khác.

> Không sử dụng kết quả của một lần test cũ để khẳng định bản hiện tại chắc chắn vượt toàn bộ kiểm thử. Hãy lưu lệnh, ngày chạy, commit và kết quả thực tế khi bàn giao.

---

## 10. Quy trình Git/GitHub và thành viên

### 10.1. Git Flow đề xuất cho nhóm

- `main`: nhánh tích hợp/sản phẩm; chỉ merge những thay đổi đã được review và kiểm thử.
- Nhánh theo tính năng: `feat/models`, `feat/algorithm`, `feat/simulation`, `feat/storage`, `feat/ui` hoặc tên nhánh task cụ thể.
- Thành viên push code lên branch riêng → tạo **Pull Request** → review chéo → sửa nếu cần → merge về `main`.
- Mỗi lần tích hợp cần kiểm tra hợp đồng API giữa Models – Core – UI và chạy test liên quan trước khi merge.
- Không force-push hay tự ý ghi đè thay đổi của thành viên khác trên nhánh dùng chung.

Ví dụ lệnh bắt đầu làm việc:

```bash
git switch main
git pull origin main
git switch -c feat/ten-tinh-nang
# Chỉnh sửa mã nguồn và chạy kiểm thử trước khi commit
git add .
git commit -m "feat: mo ta thay doi"
git push -u origin feat/ten-tinh-nang
```

### 10.2. Phân công theo bảng kế hoạch nhóm

| Thành viên | Nhóm nhiệm vụ chính |
| --- | --- |
| **Mỹ Ngọc** | Điều phối, đặc tả, Models, review PR và tích hợp/bàn giao. |
| **Việt Xô** | Thuật toán Poisson, Adaptive, Fixed-Time và Controller. |
| **Vĩ** | Hình học, MovementEngine, SimulationEngine và hỗ trợ tích hợp. |
| **Bảo Ngọc** | Quản lý cấu hình, JSON/Storage, giao diện Streamlit và bản đồ 2D. |
| **Thúy Vy** | Kiểm thử QA, checklist, hình minh họa, báo cáo và hỗ trợ trình bày. |

Đây là vai trò **theo bảng phân công của nhóm**, không thay thế lịch sử commit/PR để xác nhận đóng góp thực tế. **MSSV và thông tin giảng viên** chưa có trong source ZIP; nhóm bổ sung trước khi nộp chính thức, không tự điền giả định.

---

## 11. Các vấn đề thường gặp

**Q: Đã đổi số chu kỳ từ 10 thành 3 nhưng vẫn thấy `1 / 10`?**  
A: Bạn mới đổi **cấu hình đã lưu**, còn phiên đang chạy giữ snapshot cũ. Hãy Pause/Stop → **Áp dụng cấu hình đã lưu (3 chu kỳ) và chạy phiên mới** → xác nhận. Reset không tự lấy thông số mới.

**Q: Tôi đã sửa ô trong Tab 1 nhưng Start vẫn chạy giá trị cũ?**  
A: Cần bấm **Cập nhật** (hoặc **Lưu cấu hình** nếu tạo mới), kiểm tra ID đang chọn và bấm **Dùng cấu hình này** cho phiên kế tiếp.

**Q: Chạy lần đầu, không có dữ liệu để chọn?**  
A: Bản bàn giao hiện có cấu hình mẫu `JCT-001`. Nếu file đã được làm rỗng hoặc được tạo lại khi bị thiếu, bấm **Tạo cấu hình mẫu** hoặc **Tạo mới** trong Tab 1.

**Q: Tại sao không bấm được Step +1s hoặc Chạy hết chu kỳ?**  
A: Hai nút chỉ bật sau khi Start và khi phiên ở trạng thái **PAUSED**. Bấm Pause trước khi sử dụng.

**Q: Tại sao một chu kỳ dài hơn 68 giây?**  
A: 68 giây chỉ là thời lượng **danh định với tham số mẫu**. ALL_RED có thể kéo dài đến khi xe rời vùng xung đột. Nếu vượt ngưỡng clearance, mô phỏng vào ERROR.

**Q: Tại sao xe đã vượt vạch nhưng chưa tăng số xe rời khung?**  
A: Crossing và EXITED là **hai thời điểm khác nhau**. Xe đã vượt vạch còn được theo dõi đến khi ra khỏi phạm vi 2D.

**Q: Vì sao không thấy CSV?**  
A: Lịch sử được ghi khi phiên **STOPPED hoặc COMPLETED**; phiên chưa kết thúc không ghi báo cáo cuối phiên, và ERROR không được lưu như phiên hoàn tất. Nếu ghi lỗi, xem cảnh báo và dùng **Thử lại ghi lịch sử**.

**Q: `ModuleNotFoundError`, lỗi thiếu thư viện hoặc app không chạy?**  
A: Kiểm tra Python >=3.13, chạy `uv sync`, sau đó chạy `uv run streamlit run src/app.py` từ thư mục chứa `pyproject.toml`.

**Q: Kết quả sau Reset có giống lần trước không?**  
A: Reset giữ bản chốt và seed. Với cùng code, cấu hình và thứ tự các phép lấy mẫu, kết quả mô phỏng có thể được tái lập; việc tạo phiên **với cấu hình mới** là thao tác khác Reset.

---

## 12. Giới hạn và tài liệu tham khảo

### 12.1. Các giới hạn đã chủ động chốt

- Mô hình đơn giản phục vụ học tập; không thay thế mô phỏng thực địa chuyên dụng, chưa hỗ trợ nhiều giao lộ, rẽ trái/phải, người đi bộ, cảm biến hoặc ưu tiên xe khẩn cấp.
- Thời lượng tín hiệu, vận tốc, gia tốc, kích thước và khoảng cách là **tham số mô phỏng**, không phải khuyến nghị lắp đặt đèn thật.
- Streamlit so sánh một phiên vừa chạy với Fixed-Time; thí nghiệm nhiều kịch bản/seed dùng **CLI**. Hai chế độ chưa có bản đồ chạy song song trên trình duyệt.
- Giao diện hiện chưa có chức năng đọc lại/phân tích toàn bộ phiên lịch sử sau khi mở lại app, hoặc xuất ảnh dashboard thành báo cáo riêng.
- Ghi hai CSV không phải một giao dịch nguyên tử chung; thao tác phục hồi chỉ có hiệu lực khi outbox của phiên trình duyệt còn tồn tại.

### 12.2. Tài liệu trong repository

- [Hợp đồng thuật toán Poisson/Adaptive](docs/algorithm_contracts.md)
- [Hợp đồng Controller](docs/controller_contracts.md)
- [Thiết kế Geometry / SimulationSnapshot](docs/simulation_contracts.md)
- [Core ngày 18–19 và tiêu chí nghiệm thu](docs/core_day18_19.md)
- [Hợp đồng tích hợp UI và Core](docs/ui_core_integration.md)
- [Kết quả kiểm chứng tích hợp](docs/ui_core_integration_results.md)
- [JSON Schema V2](docs/schema/junctions_v2.schema.json)
- [Các test case UI/Storage](docs/testcases/ui_storage_testcases.md)

**Bài báo tham khảo:**

1. Majeed, A. I., Naeem, S. Q., Saeed, E. A., & Al-Shanoon, A. (2025). *Real-Time Adaptive Traffic Signal Control with YOLOv10 and Image Processing*. Al-Khwarizmi Engineering Journal, 21(4), 65–81. DOI: <https://doi.org/10.22153/kej.2025.09.006>.
2. Aleko, D. R., & Djahel, S. (2020). *An Efficient Adaptive Traffic Light Control System for Urban Road Traffic Congestion Reduction in Smart Cities*. Information, 11(2), 119. DOI: <https://doi.org/10.3390/info11020119>.

Hai công trình là **nguồn tham khảo**, không có nghĩa đồ án triển khai YOLO, SUMO hay sao chép nguyên dạng thuật toán/số liệu đánh giá từ nghiên cứu.

---

**Smart Traffic Light Simulator · Python Module 1 · Tài liệu README cập nhật theo source ngày 19/10/2026.**

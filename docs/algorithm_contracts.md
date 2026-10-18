# Hợp đồng thuật toán Poisson và Adaptive

## 1. Mục tiêu Task 3

Chốt interface và quy tắc kiểm thử ngày **12/10/2026** để thành viên hiện thực
thuật toán ngày **15/10/2026** có thể sử dụng cùng một hợp đồng. Tài liệu này
đặc tả hành vi cần đạt. Poisson và Adaptive hiện đã có implementation và kiểm thử;
Config dùng thời lượng kiểu int để gọi Adaptive. Tích hợp engine chưa triển khai.
Các bảng trạng thái chuẩn bị bên dưới ghi lại mốc thiết kế 12/10/2026;
kết quả kiểm thử hiện tại phải lấy từ lần chạy pytest thực tế.

## 2. Phạm vi

Poisson lấy số xe đến trong một tick cho một hướng. Adaptive phân bổ ngân sách
xanh giữa NS và EW dựa trên snapshot Queue đầu chu kỳ. Các hàm thuộc Core Logic,
không import Streamlit, không tạo Vehicle, không sửa Lane, không lưu JSON/CSV.
Tick logic cố định **1 giây**; substep chuyển động 0,2 giây không phải tick sinh xe.

## 3. Nguồn tham chiếu và quyết định hợp đồng

Đã đối chiếu tài liệu **Thiết kế hệ thống smart traffic light**, hồ sơ D2.3/V2.3,
ngày 12/10/2026, trong workspace tại
`Traffic Light Signal Simulation/Thiết kế hệ thống smart traffic light.docx`:

- Mục **6.1, 6.3, 6.4**: `dict` ánh xạ N/S/E/W tới Lane; `deque` chứa tất cả
  xe **chưa vượt vạch dừng**, gồm xe đang tới và xe đã dừng.
- Mục **7.2**: quy đổi xe/phút sang lambda xe/tick; Poisson dạng Knuth;
  dùng RNG có seed và lấy mẫu N → S → E → W.
- Mục **7.3**: hai giai đoạn chia tỷ trọng rồi mượn thời gian để đạt `t_min`;
  half-up NS, bảo toàn ngân sách và xử lý Queue rỗng.
- Bảng **3.4**: `min_green >= 1`; `green_budget >= 2 * min_green`.
- Mục **7.4, 13.5**: kế hoạch cố định trong chu kỳ và các test ví dụ.

Interface và các kết quả 21/39, 10/50 thống nhất với tài liệu. Hợp đồng Task 3
bổ sung rõ lỗi kiểu dữ liệu, loại bỏ bool, kiểm tra lambda hữu hạn và không
tiêu thụ RNG khi lambda bằng 0; đây là các chi tiết validation để hiện thực thống nhất.
`RandomSource` là typing Protocol có `random() -> float`, không phải bộ sinh mới;
`random.Random` đáp ứng protocol. Không thêm dependency cho thuật toán.

## 4. Interface và type hints

```python
def poisson_sample(lam: float, rng: RandomSource) -> int:
    ...

def allocate_green_adaptive(
    q_ns: int,
    q_ew: int,
    green_budget: int,
    min_green: int,
) -> tuple[int, int]:
    ...
```

Tên hàm, thứ tự tham số và thứ tự trả về được chốt. `rng` là tham số bắt buộc,
không có giá trị mặc định ngầm lấy random toàn cục. Không thêm `seed`, rate hoặc
tick vào signature Poisson; caller thực hiện quy đổi và sở hữu RNG của phiên.

## 5. Dữ liệu đầu vào

| Hàm / tham số | Ý nghĩa, đơn vị | Điều kiện |
| --- | --- | --- |
| Poisson `lam` | Kỳ vọng số xe mới trong một tick | int/float hữu hạn, >= 0; không nhận bool |
| Poisson `rng` | RNG của phiên | Có `random()` callable trả float trong [0, 1) |
| Adaptive `q_ns` | len(Q_N) + len(Q_S) tại đầu chu kỳ | int >= 0, không nhận bool |
| Adaptive `q_ew` | len(Q_E) + len(Q_W) tại đầu chu kỳ | int >= 0, không nhận bool |
| Adaptive `green_budget` | Tổng giây xanh, không gồm vàng/all-red | int >= 2 * min_green, không nhận bool |
| Adaptive `min_green` | Giây xanh tối thiểu mỗi pha, tương ứng t_min | int >= 1, không nhận bool |

Không tự ép kiểu từ chuỗi hoặc float sang int. `q_ns/q_ew` không dùng
`stopped_count` và không đếm `active_crossing` hoặc xe đã rời khung. Hàm Adaptive
không áp giới hạn trên cho Queue; giới hạn số xe ban đầu trong Config là trách
nhiệm của validation cấu hình, không phải giới hạn Queue tăng lên trong mô phỏng.

## 6. Dữ liệu đầu ra

Poisson trả một `int` Python không âm, biểu diễn số xe mới cho một hướng trong
một tick. Không trả giá trị kỳ vọng 0,3 thay cho số xe, và không trả Vehicle.

Adaptive trả tuple `(green_ns, green_ew)` gồm hai `int` Python đo bằng giây.
Tuple chỉ là kết quả tính toán; caller tạo SignalPlan và chốt nó cho cả chu kỳ.

## 7. Công thức và trình tự tính

### Poisson

Với hướng d, `lambda_d = rate_per_min_d * tick_s / 60`, `tick_s = 1`.
Số xe đến `A_d(t)` tuân theo `Poisson(lambda_d)`, với xác suất
`P(A = k) = exp(-lambda) * lambda**k / k!`, k là số nguyên không âm.
Khi lambda = 0, kết quả luôn là 0.

Phương pháp là Knuth: tính cutoff `exp(-lam)`, nhân lần lượt các giá trị
`rng.random()` cho đến khi tích không còn lớn hơn cutoff; trả số lần nhân trừ 1.
Phương pháp này đã có implementation trong `src/core/algorithms.py`.
Trong cấu hình V2.3, rate mỗi hướng 0–30 xe/phút nên lambda 0–0,5 ở tick 1 giây.
Knuth được chọn cho miền nhỏ này; khi mở rộng lambda lớn cần đánh giá hiệu năng
và underflow thay vì mặc nhiên dùng kết quả của thuật toán ngoài miền đã kiểm thử.
Không âm thầm clamp lambda hoặc thay đổi interface.

### Adaptive — Giai đoạn A

Validate trước. Gọi `total = q_ns + q_ew`. Nếu total > 0:

```text
g_ns_raw = green_budget * q_ns / total
g_ew_raw = green_budget * q_ew / total
```

Chưa làm tròn. **Không cộng min_green trước rồi phân phối ngân sách còn lại**.
Chỉ số nhu cầu eta trong mục 7.3 có thể dùng báo cáo, không thêm xanh chu kỳ
trước vào interface; phép chia tỷ trọng trên tương đương công thức của thiết kế.

### Adaptive — Giai đoạn B

Nếu cả hai raw >= min_green, giữ nguyên. Nếu NS thiếu, đặt
`delta = min_green - g_ns_raw`, tăng NS lên min_green và giảm EW đúng delta.
Nếu EW thiếu, xử lý đối xứng. Với budget >= 2 * min_green, không thể có cả hai
pha thiếu cùng lúc và việc mượn vẫn giữ pha còn lại >= min_green.

Sau hiệu chỉnh, đặt `s_ns` là thời gian NS chưa làm tròn:

```text
green_ns = floor(s_ns + 0.5)
green_ns = max(min_green, min(green_ns, green_budget - min_green))
green_ew = green_budget - green_ns
```

Dùng **half-up**, không dùng `round()` mặc định của Python cho trường hợp .5.
Chỉ làm tròn NS; EW lấy từ phần dư, không làm tròn hai pha độc lập.

## 8. Quy tắc validation và lỗi

| Trường hợp | Lỗi phải phát sinh sau khi implementation có thật |
| --- | --- |
| lam là bool, string, None hoặc complex | TypeError |
| lam âm, NaN, +inf hoặc -inf | ValueError |
| rng thiếu random callable | TypeError |
| Tham số Adaptive là bool hoặc không phải int | TypeError |
| q_ns hoặc q_ew âm | ValueError |
| min_green < 1 | ValueError |
| green_budget < 2 * min_green | ValueError |

Poisson kiểm tra kiểu và giá trị lambda rồi kiểm tra interface RNG trước khi
lấy mẫu. Lambda lỗi không tiêu thụ RNG. Caller đảm bảo giá trị do RNG trả về
thuộc [0, 1); không bắt buộc dùng instance cụ thể của random.Random.
Adaptive kiểm tra kiểu của cả bốn tham số trước các ràng buộc giá trị và phép chia.
Không tự sửa dữ liệu không hợp lệ. Nội dung thông báo lỗi có thể rõ hơn theo
tham số, nhưng loại exception phải giữ như hợp đồng.

Hai hàm hiện kiểm tra đầu vào và trả kết quả theo hợp đồng. Các lỗi trong bảng
được kiểm thử bằng implementation thật; test Adaptive không còn được đánh dấu SKIP.

## 9. Trường hợp biên

Poisson: lam = 0 trả 0 mà không gọi rng.random(). Cùng trạng thái RNG ban đầu,
cùng lambda và cùng thứ tự gọi phải tái lập chuỗi trong cùng implementation
và môi trường; không hard-code một mẫu riêng lẻ từ seed.

Adaptive: nếu total = 0, bỏ phép chia, `green_ns = green_budget // 2`,
`green_ew = green_budget - green_ns`. Khi budget lẻ, **NS nhận phần nguyên dưới**.
Với Queue không rỗng, quy tắc half-up vẫn áp dụng: (1, 1, 61, 10) → (31, 30),
khác với fallback rỗng (0, 0, 61, 10) → (30, 31).
Pha không có xe vẫn nhận min_green. Nếu budget = 2 * min_green,
cả hai pha nhận đúng min_green, bất kể tỷ trọng Queue.

## 10. Bất biến và tác dụng phụ

- Poisson trả int >= 0; chỉ sử dụng RNG do caller truyền, không reseed và không
  dùng/chỉnh trạng thái random toàn cục. Với lam > 0, Knuth tiêu thụ RNG đã truyền.
- Adaptive: `green_ns + green_ew == green_budget`, cả hai >= min_green;
  mỗi pha <= green_budget - min_green và thời lượng là số nguyên.
- Không chia cho 0, không phát sinh Queue âm, không sửa các Queue đầu vào.
- Adaptive không dùng RNG và không thay đổi lịch xanh giữa chu kỳ.
- Không xem test SKIP là PASS hoặc coi chữ ký hàm là thuật toán đã hoạt động.

## 11. Bảng test Poisson

| Mã | Dữ liệu / thao tác | Kết quả kỳ vọng | Trạng thái chuẩn bị |
| --- | --- | --- | --- |
| P-01 | lam = 0, RNG seed 2026 | int 0; trạng thái RNG không đổi | SKIP chờ Poisson |
| P-02 | lam = -0,5 | ValueError; trạng thái RNG không đổi | SKIP |
| P-03 | Hai Random(2026), lam = 0,3, mỗi RNG 100 lần | Hai chuỗi bằng nhau, không yêu cầu mẫu cố định | SKIP |
| P-04 | 100 mẫu, lam = 0,3 | Mỗi mẫu là int >= 0 | SKIP |
| P-05 | 18 xe/phút, tick 1 giây | lambda = 0,3 | Chạy kiểm tra công thức đơn vị |
| P-06 | Lấy mẫu bằng RNG cục bộ | Trạng thái random toàn cục không đổi | SKIP |
| P-07 | lam > 0 | Trạng thái RNG đã truyền được tiêu thụ | SKIP |
| P-08 | NaN, +inf, -inf | ValueError, 3 trường hợp | SKIP |
| P-09 | bool, string, None, complex | TypeError, 4 trường hợp | SKIP |
| P-10 | Thiếu random hoặc random không callable | TypeError, 2 trường hợp | SKIP |

P-05 kiểm tra phép quy đổi được đặc tả, không gọi một helper giả và không chứng
minh sampler đã hoạt động. Thứ tự hướng được kiểm thử tích hợp khi có engine;
Task 3 không tạo một engine giả để kiểm tra điều này. Không yêu cầu đúng 18 xe
trong một lần chạy 60 tick hoặc một số xe cố định cho một mẫu ngẫu nhiên.

## 12. Bảng test Adaptive

Đầu vào theo thứ tự `(q_ns, q_ew, green_budget, min_green)`.

| Mã | Đầu vào | Kết quả kỳ vọng | Trạng thái chuẩn bị |
| --- | --- | --- | --- |
| A-01 | (11, 21, 60, 10) | (21, 39) | SKIP chờ Adaptive |
| A-02 | (1, 19, 60, 10) | (10, 50) | SKIP |
| A-03 | (0, 0, 60, 10) | (30, 30) | SKIP |
| A-04 | (0, 0, 61, 10) | (30, 31) | SKIP |
| A-05 | (20, 0, 60, 10) | (50, 10) | SKIP |
| A-06 | (0, 20, 60, 10) | (10, 50) | SKIP |
| A-07 | (12, 12, 60, 10) | (30, 30) | SKIP |
| A-08 | (3, 7, 60, 10) | (18, 42) | SKIP |
| A-09 | (1, 1, 61, 10) | (31, 30), half-up khi có xe | SKIP |
| A-10 | (1, 19, 20, 10) | (10, 10), budget = 2 * min | SKIP |
| A-11 | (1, 5, 60, 10) | (10, 50), raw NS đúng bằng min | SKIP |
| A-12 | (1, 3, 42, 10) | (11, 31), raw NS = 10,5 | SKIP |
| A-13–14 | Queue âm ở NS hoặc EW | ValueError, 2 trường hợp | SKIP |
| A-15–17 | budget = 15, 0, -1; min = 10 | ValueError, 3 trường hợp | SKIP |
| A-18–19 | min = 0 hoặc -1 | ValueError, 2 trường hợp | SKIP |
| A-20 | Mỗi tham số lần lượt là bool, float, string, None | TypeError, 16 trường hợp | SKIP |
| A-21 | 48 tổ hợp Queue và budget hợp lệ | Tuple int, tổng đúng, hai pha đạt min | SKIP, một test duyệt 48 tổ hợp |

Các assertions đã dùng expected thật; marks SKIP chỉ ngăn chạy khi chưa có
implementation. Mỗi trường hợp parameterized được pytest tính là một test.

## 13. Giải thích 21/39 và 10/50

**21/39:** từ Q_N=7, Q_S=4, Q_E=16, Q_W=5 có q_ns=11, q_ew=21.
NS raw = 60 * 11 / 32 = 20,625; EW raw = 39,375. Cả hai >= 10 nên không mượn.
Half-up NS: floor(20,625 + 0,5) = 21. EW = 60 - 21 = 39.

**10/50:** q_ns=1, q_ew=19 nên raw là 3 và 57. NS thiếu 10 - 3 = 7 giây.
Chuyển 7 giây từ EW sang NS: 10 và 50; làm tròn không đổi. Tổng vẫn 60 và
cả hai đạt tối thiểu 10. Không dùng công thức phân phối `budget - 2 * min`.

## 14. Cách SimulationEngine sẽ sử dụng

Đây là kế hoạch tích hợp, chưa viết engine trong Task 3:

1. Engine sở hữu `rng = random.Random(config.seed)` cho toàn phiên; Reset
   khởi tạo lại seed để phát lại. Không tạo RNG mới mỗi tick hoặc mỗi lần gọi.
2. Mỗi tick logic 1 giây, lần lượt N/S/E/W: tính lambda từ rate, gọi Poisson
   một lần cho từng hướng, tạo số Vehicle tương ứng và append vào deque.
   Không sinh lại xe ở từng substep chuyển động 0,2 giây.
3. Khi bắt đầu một chu kỳ (kể cả chu kỳ đầu), lấy snapshot độ dài bốn deque;
   q_ns = len(Q_N) + len(Q_S), q_ew = len(Q_E) + len(Q_W).
4. Engine truyền counts/cycle_no/started_at cho Controller.start_next_cycle.
   Controller gọi Adaptive và dùng tuple để lập SignalPlan. Giữ nguyên các thời lượng
   trong toàn chu kỳ; chỉ đọc snapshot và phân bổ lại ở chu kỳ tiếp theo.
5. Thời gian vàng, all-red và clearance hold thuộc controller/movement;
   không cộng vào green_budget. Xe đã vượt vạch thuộc active_crossing và
   không được đếm lại trong q_ns/q_ew.

## 15. Công việc ngày 15/10 và chạy kiểm tra

- Hiện thực validation và Knuth bằng RNG truyền vào; xử lý lam = 0 đúng hợp đồng.
- Hiện thực Adaptive hai giai đoạn, fallback rỗng, half-up và chặn biên.
- Bỏ skip của class tương ứng khi có implementation thật, chạy toàn bộ assertions;
  không thay expected hoặc trả số cố định để làm test xanh.
- Chạy các smoke tests cùng test nghiệp vụ; nghiên cứu bổ sung kiểm thử thống kê
  với sample đủ lớn và tolerance phù hợp, tránh kiểm thử ngẫu nhiên dễ flaky.
- Khi đến phần engine, thêm test thứ tự N/S/E/W, reset seed, snapshot đầu chu kỳ
  và giữ lịch trong chu kỳ. Các test tích hợp chưa được triển khai ở Task 3.

```powershell
uv sync
uv run pytest
uv run python -m compileall -q src tests
git status
```

Workspace hiện có một bản clone riêng ở `SmartTrafficLight/SmartTrafficLight/`.
Khi chạy pytest từ project chính, pytest có thể quét cả hai bộ test trùng tên
và báo import mismatch. Giữ nguyên bản clone và giới hạn collection bằng:

```powershell
uv run pytest --ignore=SmartTrafficLight
```

Trên checkout sạch không có bản clone lồng, dùng `uv run pytest` thông thường.
Tại thời điểm Task 3, PASS của smoke tests và P-05 chỉ xác nhận scaffold cùng
quy đổi đơn vị; test Poisson/Adaptive còn SKIP, chưa có kết quả nghiệp vụ thực tế.

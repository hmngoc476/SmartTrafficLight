# Kết quả kiểm chứng Core ngày 18–19

Chạy ngày 19/10/2026 trên nhánh feat/core-day18-19, dựa main 70862b6.
`uv run --frozen pytest -q -ra`: **609 passed**, không fail/error/skip.
Các test nền được giữ; fixture kiểm tra crossing một lần dùng xe initial để không mâu thuẫn TC-23.

## Headway qua nhiều chu kỳ

Đã sửa Lane giữ thời điểm crossing cuối qua vàng/đỏ, qua chu kỳ và cả khi Queue
rỗng. Xanh mới phải chờ cả startup delay lẫn headway còn lại; Reset toàn phiên
tạo Lane mới và xóa lịch sử. Không đổi công thức Adaptive, cấu hình mặc định
headway=2s, khóa JSON hoặc API dành cho UI/Storage.

Thêm 31 ca kiểm thử: lịch sử khi Queue rỗng ở bốn làn, startup/headway cùng
ràng buộc xanh mới, headway 13s/100s qua nhiều chu kỳ cho cả hai policy,
Reset toàn phiên và replay kết quả runner. Trước bản sửa, 19 ca hồi quy này
thất bại trên mã cũ; sau bản sửa toàn bộ 609 test đều đạt.

Ca không sinh thêm xe, initial N=3; headway 13s dùng budget=20, min=3,
yellow=1, all-red=1, startup=0, H=48s. Headway 100s giữ thời lượng đèn mặc
định, H=240s:

| Headway | Policy | Các thời điểm crossing N (s) | Khoảng giữa hai crossing (s) |
|---|---|---|---|
| 13s | Adaptive | 0.8 → 14.6 → 28.4 | 13.8; 13.8 |
| 13s | Fixed-Time | 0.8 → 24.8 | 24.0 |
| 100s | Adaptive | 2.8 → 103.6 → 206.8 | 100.8; 103.2 |
| 100s | Fixed-Time | 2.8 → 138.8 | 136.0 |

Thời điểm crossing ghi cuối substep sau khi xe đủ điều kiện và đi tới vạch,
nên khoảng quan sát có thể lớn hơn headway tối thiểu. Trong ca 13s, Adaptive
vẫn cho qua ba xe trước H=48s; thay đổi cần thiết là crossing thứ ba từ 24.8s
thành 28.4s, không ép số xe qua của hai policy bằng nhau.

Kiểm tra độc lập bổ sung 30 cấu hình × 2 policy, H=240s, gồm headway
1/2/3/13/37/100s, dt từ 0.1 đến 1s, đường rộng 3.6/4/16/24m và các tốc độ,
gia tốc, độ dài xe, min_gap, arrivals khác nhau. Cả 60 phiên đủ H;
60,960 substep và 3,432 khoảng headway được kiểm tra, không vi phạm tín hiệu,
headway, tuổi crossing, min_gap, ownership, biên EXITED hoặc bảo toàn xe.

## So sánh Adaptive và Fixed-Time

Thí nghiệm: `uv run python -m src.core.experiment --horizon 180 --output reports/comparison.json`.
6 kịch bản × seed 0–9 = **60 cặp / 120 phiên**, cả hai policy đều đủ 180s.
Kiểm tra kết quả: arrivals từng hướng bằng nhau, cả hai đẳng thức bảo toàn đúng và min_gap_violations=0 ở mọi phiên.
Toàn bộ JSON kết quả với headway mặc định 2s giống lần chạy trước bản sửa;
bảng bên dưới là kết quả đã chạy lại sau khi sửa headway.

| Kịch bản | Departed Adaptive | Departed Fixed | Avg Queue Adaptive | Avg Queue Fixed | Hold Adaptive | Hold Fixed |
|---|---:|---:|---:|---:|---:|---:|
| empty | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| balanced | 102.400 | 102.300 | 40.302 | 40.060 | 0.000 | 0.000 |
| ns_heavy | 108.200 | 93.100 | 61.533 | 67.747 | 0.000 | 0.000 |
| ew_heavy | 103.500 | 80.000 | 66.901 | 78.446 | 0.000 | 0.000 |
| peak | 105.600 | 106.000 | 526.409 | 526.216 | 0.000 | 0.000 |
| clearance | 84.800 | 80.000 | 60.044 | 63.328 | 20.700 | 17.900 |

Các giá trị là trung bình trên 10 seed; output JSON còn giữ từng seed và population_std.
Không kết luận Adaptive luôn tốt hơn: kịch bản cân bằng/cao điểm có chỉ số Fixed nhỉnh hơn trong mẫu này.
So cùng H, không ép số chu kỳ phải bằng nhau hoặc dùng 68×N thay thời gian thực có hold.

Đối chiếu bốn task:
- Algorithms 18: giữ/release/timeout ở cả hai ALL_RED và fail-safe; occupancy theo toàn thân xe 1.8m.
- Simulation 18: hồi quy spawn active, đường hẹp, tuổi xe mới, gap/ownership, exit bốn hướng.
- Simulation 19: thống kê/null/zero, stopped threshold, hold nhiều chu kỳ, terminal state và bảo toàn xe.
- Algorithms 19: Fixed-Time, arrivals replay từng tick/hướng, horizon/reset và lỗi không được tính comparable.

Các kết quả trên nghiệm thu Core trong phạm vi thiết kế học thuật và các ca đã chạy.
UI/CSV lịch sử chưa được tích hợp. Chi tiết hợp đồng nằm tại [core_day18_19.md](core_day18_19.md).

# Kết quả kiểm chứng Core ngày 18–19

Chạy ngày 19/10/2026 trên nhánh feat/core-day18-19, dựa main 70862b6.
`uv run --frozen pytest -q -ra`: **578 passed**, không fail/error/skip.
Các test nền được giữ; fixture kiểm tra crossing một lần dùng xe initial để không mâu thuẫn TC-23.

Thí nghiệm: `uv run python -m src.core.experiment --horizon 180 --output reports/comparison.json`.
6 kịch bản × seed 0–9 = **60 cặp / 120 phiên**, cả hai policy đều đủ 180s.
Kiểm tra kết quả: arrivals từng hướng bằng nhau, cả hai đẳng thức bảo toàn đúng và min_gap_violations=0 ở mọi phiên.

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

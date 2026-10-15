"""TODO: SimulationEngine theo tick 1 giây; chưa hiện thực.

Public API dự kiến: start(), tick() -> SimulationSnapshot, run_ticks(n),
pause(), resume(), stop(), reset(), snapshot() -> SimulationSnapshot.
SimulationSnapshot có một nguồn định nghĩa ở src.models.snapshot.

Core sẽ lấy mẫu Poisson một lần mỗi hướng/tick, chạy 5 substep 0,2 giây,
chốt counters/tín hiệu tại cùng thời điểm rồi tạo snapshot chỉ đọc.
Không truyền Lane.queue, Vehicle thật hoặc active_crossing cho UI.
snapshot() không được tự tiến thời gian, sinh xe hoặc pop Queue.
Module hiện chưa tạo snapshot của một engine đang chạy; JSON trong docs/examples
là dữ liệu minh họa để kiểm tra hợp đồng, không phải kết quả mô phỏng.
"""

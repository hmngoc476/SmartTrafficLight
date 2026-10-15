"""TODO: MovementEngine với substep 0,2 giây; chưa hiện thực động học.

Public API dự kiến theo V2.3 và docs/simulation_contracts.md:
- advance_substep(t: float, dt: float, controller) -> None
- spawn_and_enqueue(direction: str, arrival_t: int) -> Vehicle
- is_conflict_clear() -> bool
- check_gap_invariants() -> None

Geometry.lane_to_xy(direction, s_front_m) là implementation chính thức ở
src.core.geometry; engine sẽ gọi trực tiếp phương thức này với thuộc tính
Vehicle, không sao chép công thức.
Queue chứa xe chưa crossing; active_crossing chứa xe crossed chưa exited.
Crossing chỉ hợp lệ khi GREEN/startup/headway và chỉ pop đầu FIFO một lần.
Xe đã crossed tiếp tục chạy trong vàng/đỏ. Check gap gồm leader đã crossed.
Occupancy, clearance và các quy tắc trên hiện mới là hợp đồng, không có code
trả kết quả giả ở module này. Không sinh Poisson hoặc ghi JSON/CSV tại đây.
"""

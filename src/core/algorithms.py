"""Hợp đồng Poisson và Adaptive theo V2.3; implementation còn TODO.

Task 3 ngày 12/10/2026 chỉ chốt interface. Chi tiết và test case nằm trong
docs/algorithm_contracts.md. Không có thuật toán hoạt động trong module này.
"""

from typing import Protocol


class RandomSource(Protocol):
    """RNG được truyền từ caller; random.Random đáp ứng interface này."""

    def random(self) -> float:
        """Trả về số giả ngẫu nhiên trong đoạn [0, 1)."""
        ...


def poisson_sample(lam: float, rng: RandomSource) -> int:
    """TODO: Lấy một mẫu Poisson với kỳ vọng lam xe trong một tick.

    Args:
        lam: Số hữu hạn >= 0; nhận int/float, không nhận bool.
            Caller quy đổi lam = rate_per_min * tick_s / 60, tick_s = 1.
        rng: Đối tượng có random() callable trả về float trong [0, 1).
            Caller sở hữu RNG và khởi tạo seed; không dùng random toàn cục.

    Returns:
        Số nguyên Python >= 0. Với lam = 0, trả 0 và không tiêu thụ RNG.
        Cùng trạng thái RNG, lam và thứ tự gọi cho cùng chuỗi kết quả.

    Raises:
        TypeError: Kiểu lam sai (kể cả bool) hoặc rng thiếu random callable.
        ValueError: lam âm, NaN hoặc vô cực.
        NotImplementedError: Trạng thái hiện tại của scaffold Task 3.

    Hợp đồng ngày 15/10: validate lam và rng trước khi lấy mẫu; lam lỗi
    không làm thay đổi RNG. Dự kiến dùng Knuth trong miền lambda nhỏ.
    Thứ tự gọi N -> S -> E -> W do SimulationEngine chịu trách nhiệm.
    Hàm không tạo Vehicle, sửa Queue, đọc cấu hình hoặc truy cập UI.
    """
    raise NotImplementedError("Poisson chưa được triển khai; dự kiến ngày 15/10/2026.")


def allocate_green_adaptive(
    q_ns: int,
    q_ew: int,
    green_budget: int,
    min_green: int,
) -> tuple[int, int]:
    """TODO: Phân bổ xanh NS/EW từ snapshot Queue đầu chu kỳ.

    Args:
        q_ns: Tổng xe chưa vượt vạch của N/S, số nguyên >= 0.
        q_ew: Tổng xe chưa vượt vạch của E/W, số nguyên >= 0.
        green_budget: Tổng giây xanh; số nguyên >= 2 * min_green.
        min_green: Giây xanh tối thiểu mỗi pha; số nguyên >= 1.
        Các tham số không nhận bool và không tự ép kiểu từ float/string.

    Returns:
        (green_ns, green_ew), hai số nguyên bảo toàn green_budget,
        mỗi giá trị >= min_green. Ví dụ: (11, 21, 60, 10) -> (21, 39),
        (1, 19, 60, 10) -> (10, 50).

    Raises:
        TypeError: Một tham số không phải int hoặc là bool.
        ValueError: Queue âm, min_green < 1 hoặc ngân sách không đủ.
        NotImplementedError: Trạng thái hiện tại của scaffold Task 3.

    Hợp đồng ngày 15/10: validate trước khi chia. Nếu tổng Queue > 0,
    giai đoạn A chia green_budget theo tỷ trọng Queue, không cộng t_min
    trước; giai đoạn B mượn phần thiếu từ pha kia để đạt min_green.
    Sau đó half-up NS bằng floor(s_ns + 0.5), chặn vào khoảng hợp lệ,
    EW = green_budget - NS. Nếu cả hai Queue rỗng, NS = budget // 2.
    Hàm thuần, không sửa Queue hoặc lịch đang chạy; caller chốt kết quả
    cho toàn chu kỳ và chỉ gọi lại khi chu kỳ mới bắt đầu.
    """
    raise NotImplementedError("Adaptive chưa được triển khai; dự kiến ngày 15/10/2026.")

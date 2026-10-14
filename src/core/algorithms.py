"""Hợp đồng Poisson và Adaptive theo V2.3; implementation còn TODO.

Task 3 ngày 12/10/2026 chỉ chốt interface. Chi tiết và test case nằm trong
docs/algorithm_contracts.md. Không có thuật toán hoạt động trong module này.
"""

from typing import Protocol
import math


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
    #raise NotImplementedError("Poisson chưa được triển khai; dự kiến ngày 15/10/2026.")
    # 1. Kiểm tra kiểu lam; bool phải bị từ chối dù bool là subclass của int.
    if isinstance(lam, bool) or not isinstance(lam, (int, float)):
        raise TypeError("lam phải là int hoặc float, không phải bool.")

    # 2. Kiểm tra tính hữu hạn và không âm.
    # Mọi int Python đều hữu hạn; chỉ cần isfinite cho float.
    if isinstance(lam, float) and not math.isfinite(lam):
        raise ValueError("lam phải là số hữu hạn.")

    if lam < 0:
        raise ValueError("lam phải >= 0.")

    # 3. Kiểm tra RNG sau khi lam đã hợp lệ.
    random_method = getattr(rng, "random", None)
    if not callable(random_method):
        raise TypeError("rng phải có phương thức random() callable.")

    # 4. Trường hợp đặc biệt: không tiêu thụ RNG.
    if lam == 0:
        return 0

    # 5. Thuật toán Knuth.
    threshold = math.exp(-lam)
    product = 1.0
    count = 0

    while product > threshold:
        count += 1
        product *= random_method()

    return count - 1


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
    # raise NotImplementedError("Adaptive chưa được triển khai; dự kiến ngày 15/10/2026.")
    # 1. Kiểm tra kiểu dữ liệu trước khi kiểm tra giá trị.
    # bool là lớp con của int trong Python nên phải loại riêng.
    parameters = {
        "q_ns": q_ns,
        "q_ew": q_ew,
        "green_budget": green_budget,
        "min_green": min_green,
    }

    for name, value in parameters.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} phải là int và không được là bool.")

    # 2. Kiểm tra các ràng buộc giá trị.
    if q_ns < 0:
        raise ValueError("q_ns phải >= 0.")

    if q_ew < 0:
        raise ValueError("q_ew phải >= 0.")

    if min_green < 1:
        raise ValueError("min_green phải >= 1.")

    if green_budget < 2 * min_green:
        raise ValueError(
            "green_budget phải >= 2 * min_green."
        )

    # 3. Chia theo tỷ trọng số xe đang chờ.
    total_queue = q_ns + q_ew

    if total_queue == 0:
        # Không có xe ở cả hai pha: chia gần đều.
        green_ns = green_budget // 2
    else:
        # Giai đoạn A: phân bổ theo tỷ lệ Queue.
        green_ns_raw = green_budget * q_ns / total_queue
        green_ew_raw = green_budget * q_ew / total_queue

        # Giai đoạn B: pha thiếu thời gian mượn từ pha còn lại.
        if green_ns_raw < min_green:
            delta = min_green - green_ns_raw
            green_ns_raw = float(min_green)
            green_ew_raw -= delta

        elif green_ew_raw < min_green:
            delta = min_green - green_ew_raw
            green_ew_raw = float(min_green)
            green_ns_raw -= delta

        # 4. Làm tròn half-up cho NS.
        # Không dùng round() vì round(10.5) trả về 10 trong Python.
        green_ns = math.floor(green_ns_raw + 0.5)

        # Chặn NS để EW luôn đủ min_green.
        green_ns = max(
            min_green,
            min(green_ns, green_budget - min_green),
        )

    # 5. Lấy phần dư để bảo toàn chính xác tổng ngân sách.
    green_ew = green_budget - green_ns

    return green_ns, green_ew

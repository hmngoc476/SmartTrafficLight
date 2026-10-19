# Kết quả tích hợp UI với Core ngày 18–19

Ngày 19/10/2026, nhánh feat/ui cập nhật từ Core b13c53a. Main chưa tự merge.
PR UI #17 phụ thuộc Core #18; nên review/merge #18 trước, rồi #17.

## Kiểm thử

- `uv run --frozen pytest -q -ra`: **651 passed**, không fail/error/skip.
- Giữ 609 test nền, thêm 8 ca API báo cáo, 7 ca AppTest và 27 ca CSV.
- AppTest chạy hai tab với Core/ConfigManager/Storage thật, JSON/CSV tạm.
  Bao phủ startup, CRUD, width>=3.6, Start/Pause/Resume/Stop, Step, chạy tới
  chu kỳ có hold, ERROR/all-red, Reset cùng bản chốt dù cấu hình lưu đã đổi,
  rerun không tick, timer trùng/cũ và báo cáo chưa lưu qua phiên mới.
- CSV: đối chiếu header Markdown, null average, validation trước ghi, ghi dở
  hai file rồi retry, replace thất bại giữ file cũ/dọn temp, sai header/dòng lỗi,
  payload cùng ID nhưng khác nội dung, 8 session ghi đồng thời và retry trùng.
- Chromium thật, viewport 1920×1080: hai tab, timer tự chạy đến 2s; Pause giữ 2s;
  Step thành 3s; Reset về 0, Start bật và Resume/Step khóa; Start lại, Stop và
  tải CSV thành công. Không lỗi JavaScript hoặc exception trong ứng dụng.
- Chạy lại 6 kịch bản × 10 seed × 2 policy ở H=180s: 60/60 cặp đủ H;
  JSON đầu ra giống bản Core b13c53a, không đổi kết quả đối chứng thuật toán.
- `git diff --check` đạt. Runtime CSV, ảnh/log kiểm thử và cấu hình IDE cá nhân
  không nằm trong commit. Không đổi pyproject.toml hoặc uv.lock.

## Hành vi đã thống nhất

Core giữ session_state và summary dict; DashboardData chỉ đọc, CycleMetrics
phân biệt tạm/đã chốt. UI không gọi lại Adaptive, không sửa Queue, thời gian
hoặc hình học. Bề rộng xe lấy từ Snapshot, vật lý vẫn 1.8m.

Reset tạo phiên chưa Start và giữ bản chốt/seed. Timer có epoch/sequence riêng;
render chỉ đọc. Metadata run_id/thời điểm ISO giữ nguyên qua retry/rerun.
Chỉ STOPPED/COMPLETED lưu CSV và chỉ chu kỳ hoàn tất được xuất theo chu kỳ.
ERROR giữ báo cáo chẩn đoán, không bị ghi thành phiên hoàn tất.

Mỗi file CSV thay nguyên tử; retry phục hồi phần thiếu giữa hai file. Khóa ghi
áp dụng trong một process Streamlit, outbox thuộc phiên trình duyệt; chưa có
journal phục hồi khi server/phiên trình duyệt bị mất.

## Phạm vi

Đã xử lý gói tương thích hai tab, API báo cáo, vòng đời/timer và CSV đã được
người dùng duyệt. Các ca kiểm thử UI tương ứng phần việc ngày 15–19 đã có.
Không coi đây là nghiệm thu mọi chức năng mở rộng của thiết kế: màn xem lại
toàn bộ lịch sử sau khi mở lại app, màn đối chứng nhiều policy/seed và xuất
ảnh từ UI không nằm trong gói này. CLI đối chứng Core vẫn hoạt động độc lập.

Xem [hợp đồng tích hợp](ui_core_integration.md) và
[hợp đồng UI/Storage](ui_storage_contracts.md) để phát triển tiếp.

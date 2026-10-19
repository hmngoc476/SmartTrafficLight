# Hợp đồng tích hợp UI với Core ngày 18–19

Nền Core: b13c53a; tích hợp trên feat/ui. Các API sau bổ sung lớp báo cáo,
không thay công thức Adaptive/Fixed-Time, Poisson, headway, chuyển động hay JSON V2.

## API công khai

- `session_state` là trạng thái chính thức; không có alias `state`.
- `has_started` phân biệt PAUSED chưa Start (mới tạo/Reset) với PAUSED đã chạy.
  Reset giữ Config/seed, xóa tiến độ và yêu cầu Start lại. UI giữ bản chốt khi
  Start lại sau Reset; không lấy draft hoặc lựa chọn cấu hình mới thay thế.
- `summary()` vẫn trả dict tách biệt ở mọi trạng thái. Không dùng việc khác
  None của dict này để suy ra phiên đã kết thúc.
- `dashboard_data()` trả DashboardData frozen: Snapshot, green hiện tại/trước,
  Queue series cuối tick, CycleMetrics, occupancy, min gap cấu hình và thực đo.
  Summary chỉ xuất hiện khi STOPPED/COMPLETED/ERROR, là mapping chỉ đọc.
- Gap thực đo là minimum của các cặp xe cùng làn **tại thời điểm báo cáo**;
  None khi không có cặp để đo. Không dùng số active thay conflict occupancy.
- `cycle_metrics()` giữ record CycleMetrics chính thức. Record chu kỳ đang
  chạy có `provisional=True`; chu kỳ đã chốt False. `arrivals`/`departures`
  tổng hợp NS+EW; tên trung bình chính thức vẫn là `avg_queue_cycle`.
  Record tạm dùng sim_time hiện tại làm ended_at; không đưa vào CSV chu kỳ.
- `run_until_cycle_end()` chỉ nhận phiên đã Start và PAUSED. Chạy tới ranh giới
  thực tế, gồm clearance hold; dừng khi ERROR hoặc terminal. Nếu còn phiên,
  trả về PAUSED ở đầu chu kỳ kế tiếp, không chạy thêm tick của chu kỳ mới.

Các lần đọc báo cáo không tick, không tạo lại Engine, không gọi Adaptive.
Metadata run_id/started_at_iso của UI/CSV nằm ngoài Snapshot và dict summary
chuẩn; metadata chỉ tạo mới có kiểm soát khi Start/Reset.

## Điều khiển và timer UI

Hai tab dùng session_state/has_started. Start sau Reset chạy lại bản chốt cũ,
kể cả khi cấu hình đã lưu được chỉnh sửa trong lúc phiên trước đang chạy.
Tab 1 có thể sửa draft/lưu cấu hình cho phiên sau; không đổi tham số phiên hiện tại.

Timer là component HTML/JS nội bộ, không phụ thuộc CDN hoặc package bổ sung.
Mỗi giây khi RUNNING phát (epoch, sequence). Chỉ sự kiện mới của epoch đã arm
mới được gọi một tick Core; rerun do widget/đổi tab chỉ render, không tự tick.
Pause/Stop vô hiệu epoch; Resume dùng epoch mới để bỏ sự kiện cũ đang chờ.
Không đổi dt theo thời gian trình duyệt. Step và chạy chu kỳ chỉ bật ở PAUSED
đã Start. Renderer lấy width vật lý từ Snapshot nếu có.

Hai file CSV dùng header V2.3 tại ui_storage_contracts.md §14. UI bổ sung
run_id, started_at_iso (ISO có timezone), chỉ đưa phiên STOPPED/COMPLETED
và chu kỳ đã chốt vào lịch sử. ERROR giữ báo cáo chẩn đoán, không tự ghi vào
schema lịch sử vốn chỉ cho phép STOPPED/COMPLETED.

## Lịch sử và phục hồi ghi lỗi

HistoryStorage validate Summary/chu kỳ/metadata trước khi ghi. Null average khi
chưa có mẫu xuất thành ô trống. Kiểm tra cả hai header và khóa duy nhất trước
khi sửa file; cùng run_id nhưng nội dung khác bị từ chối, không bỏ qua âm thầm.

Mỗi file ghi qua file tạm riêng cùng thư mục, flush/fsync rồi os.replace.
Hai file không phải một lần ghi nguyên tử chung: nếu cycles thành công nhưng
history lỗi, retry đọc cả hai và bổ sung phần thiếu theo run_id/(run_id,cycle_index).
Trường hợp history đã có nhưng cycles thiếu cũng được hoàn thiện; retry đủ dữ
liệu trả False và không thêm dòng. Khóa đường dẫn theo thứ tự cố định dùng chung
FileStorage.transaction để tuần tự hóa các session trong một process Streamlit;
đây không phải khóa giữa nhiều process.

UI giữ các báo cáo chưa lưu trong history_outbox của session_state, kể cả khi
Start/Reset một phiên khác. Chỉ đánh dấu saved khi cả hai file đủ dữ liệu.
Lần ghi lỗi không tự retry liên tục ở rerun; nút “Thử lại ghi lịch sử” thử lại
outbox với cùng metadata. Outbox thuộc phiên trình duyệt, không phải journal
khôi phục sau khi server hoặc phiên trình duyệt bị mất.

## Kiểm thử nghiệm thu

Giữ toàn bộ 609 test nền. Kiểm thử mới bao gồm API báo cáo bất biến, chu kỳ
tạm/đã chốt, ranh giới có hold/ERROR, hai tab, CRUD, Reset replay, widget rerun,
timer trùng/cũ, outbox qua phiên mới, CSV header/null/validation, replace thất bại,
phục hồi hai file và nhiều session ghi đồng thời. Các test dùng dữ liệu tạm.

Chạy `uv run --frozen pytest -q -ra`. Kiểm tra Chromium bổ sung dùng timer thật,
Pause/Step/Reset/Start, hai tab và tải CSV; không có lỗi JavaScript.

Lần chạy bàn giao ngày 19/10/2026: **651 passed**, 0 failure/error/skip.
60 cặp Adaptive/Fixed-Time, H=180s, đều đủ H; JSON kết quả giống Core b13c53a.
Chi tiết phạm vi tại [ui_core_integration_results.md](ui_core_integration_results.md).

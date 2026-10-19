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

# Test cases UI và Storage Task 5

Cập nhật runtime đến 17/10: FileStorage/ConfigManager và regression tests đã có;
xem [Storage implementation](../storage_implementation.md). Các trạng thái chuẩn bị bên dưới là
lịch sử Task 5, không phải kết quả chạy test hiện tại. UI/CSV vẫn là phần riêng.

Các test **schema/fixture** có thể chạy ngay. Test ConfigManager/FileStorage,
widget hoặc Engine ghi **CHƯA THỰC THI**, cần implementation thật. Kỳ vọng trong
bảng không phải kết quả chạy thực tế; PASS/FAIL/SKIP được báo cáo riêng từ pytest.

## JSON và validation

| ID | Input / thao tác | Expected | Phạm vi hiện tại |
| --- | --- | --- | --- |
| J-01 | junctions_v2.example.json | Parse UTF-8 và validate Draft 2020-12 thành công | Tự động fixture/schema |
| J-02 | JSON sai cú pháp | Báo lỗi, giữ raw, không ghi đè mảng rỗng | Parser tương lai CHƯA THỰC THI |
| J-03 | Thiếu schema_version | Schema từ chối; UI báo thiếu version | Schema tự động; UI chưa thực thi |
| J-04 | Version 1 hoặc không hỗ trợ | V1 mở migration có backup; version lạ không lưu đè | Schema từ chối; migration chưa thực thi |
| J-05 | Thiếu configs / dùng configurations | Schema từ chối; không dùng hai alias song song | Schema tự động |
| J-06 | Hai configs cùng ID nhưng khác tên | Manager từ chối; schema đơn thuần vẫn có thể chấp nhận | Chứng minh giới hạn schema; Manager chưa thực thi |
| J-07 | Thiếu N/S/E/W hoặc thêm X | Schema từ chối, chỉ rõ direction | Tự động trên bản sao fixture |
| J-08 | Rate=-1 | Schema từ chối | Tự động |
| J-09 | Rate=31 | Schema từ chối | Tự động |
| J-10 | Queue=2.5, -1, 101 hoặc string | Schema từ chối | Tự động |
| J-11 | green_budget_s=15, min_green_s=10 | Manager từ chối, schema chỉ cấu trúc chưa đủ | Mẫu valid được kiểm tra; Manager CHƯA THỰC THI |
| J-12 | dt=0.3 | Manager từ chối reciprocal không nguyên | Mẫu 0.2 →5 được kiểm tra; Manager chưa thực thi |
| J-13 | bool ở rate/queue/time/seed hoặc enabled=1 | Từ chối sai kiểu | Schema tự động |
| J-14 | NaN/Infinity | Strict parser/input validation từ chối, JSON output allow_nan=False | Strict parse mẫu; parser sản phẩm chưa thực thi |
| J-15 | id/name rỗng hoặc whitespace | Schema/Manager từ chối | Schema tự động |
| J-16 | Motion có số zero/âm sai miền, dt>1 | Schema từ chối | Tự động |
| J-17 | File không có quyền ghi | Không báo thành công, giữ original/cache, cho retry | Storage CHƯA THỰC THI |
| J-18 | V1 có dữ liệu | Giữ nguyên, backup, thêm motion defaults vào candidate, preview trước ghi | Migration CHƯA THỰC THI |
| J-19 | Skeleton configurations=[] duy nhất | Đổi có kiểm tra sang configs=[]; không tạo mẫu chạy giả | Đã cập nhật skeleton trong Task 5 |
| J-20 | configurations có dữ liệu hoặc cả hai khóa | Không xóa/ghi đè/gộp tự động | Migration CHƯA THỰC THI |
| J-21 | Stats/vehicles/arrival_rates hoặc key ngoài schema | Schema từ chối | Tự động |
| J-22 | Integer viết 1.0 | Schema có thể nhận, Manager strict int Python từ chối | Giới hạn schema đã đặc tả; Manager chưa thực thi |
| J-23 | cycles=0/101, min=0, headway=0, yellow=0, all_red=0 | Từ chối; startup=0 hợp lệ | Schema tự động |
| J-24 | seed=-7, dt=1, gap=0, margin=0 | Hợp lệ về miền, không thêm maxima/dấu seed | Schema tự động |

## UI

| ID | Input / thao tác | Expected | Trạng thái |
| --- | --- | --- | --- |
| U-01 | Mở Tab 1 | Bảng đủ chín cột; form có nhãn/đơn vị, selected theo ID | Wireframe có; widget chưa thực thi |
| U-02 | Chọn một ID | Nạp đúng config, không dùng index dòng | CHƯA THỰC THI |
| U-03 | Tạo mới/lưu | NEW, ID do Manager cấp, không trùng, refresh sau ghi thành công | CHƯA THỰC THI |
| U-04 | Form lỗi | Inline+banner tiếng Việt; Lưu/Cập nhật disabled | Wireframe preview; chưa thực thi |
| U-05 | Cập nhật config | ID giữ nguyên, không sinh bản ghi mới | CHƯA THỰC THI |
| U-06 | Xóa rồi Hủy | File/lựa chọn/session không thay đổi | Wireframe confirmation; chưa thực thi |
| U-07 | Xác nhận xóa ID đang chọn | Ghi thành công rồi clear selection; active run ID không xóa khi RUNNING/PAUSED | CHƯA THỰC THI |
| U-08 | Sửa/chọn config khác trong khi chạy | Run giữ nguyên bản chốt; lựa chọn chỉ áp dụng Start mới | CHƯA THỰC THI |
| U-09 | Streamlit rerun nhiều lần | Cùng một Engine, không tăng time/arrivals tự động | CHƯA THỰC THI |
| U-10 | Kiểm tra controls theo state | Start/Pause/Resume/Reset/Step đúng matrix hợp đồng | Wireframe RUNNING có; logic chưa thực thi |
| U-11 | Pause/Step/Resume | Pause đứng yên; Step đúng 1 tick/5 substep; Resume tiếp state | CHƯA THỰC THI |
| U-12 | Reset xác nhận | Cùng bản chốt/seed, run_id mới; bỏ confirmation thì giữ phiên | CHƯA THỰC THI |
| U-13 | Chạy hết chu kỳ khi PAUSED | Đến biên chu kỳ thực tế, không giả định cố định 68s | CHƯA THỰC THI |
| U-14 | ERROR do clearance | Bốn đèn đỏ; không phát GREEN đối diện; hiển thị lỗi | CHƯA THỰC THI |
| U-15 | Render legacy waiting metric | Nhãn từ xuất hiện tới vượt vạch; không gọi là thời gian đứng yên | Hợp đồng đã ghi; UI chưa thực thi |
| U-16 | Thiếu DashboardData/chart history | “Chưa có dữ liệu”, không zero/series giả | CHƯA THỰC THI |
| U-17 | Export trước Summary | Disabled; có Summary thì lấy CSV qua Core/Storage | Wireframe có; export chưa thực thi |
| U-18 | Mẫu NS_GREEN | N/S xanh, E/W đỏ; N↓ S↑ E← W→, đúng hệ trục Task 4 | Wireframe/metadata SVG được kiểm tra |

## Storage

| ID | Input / thao tác | Expected | Trạng thái |
| --- | --- | --- | --- |
| S-01 | Atomic JSON ghi thất bại trước replace | Original nguyên vẹn, draft còn, không success giả | CHƯA THỰC THI |
| S-02 | File thiếu lần đầu / file hiện hữu hỏng | Thiếu tạo root hợp lệ; hỏng giữ nguyên/báo lỗi | CHƯA THỰC THI |
| S-03 | Append sim_history | Header ổn định 19 cột; run_id duy nhất | CHƯA THỰC THI |
| S-04 | Append cycle_metrics | Header 14 cột; (run_id,cycle_index) duy nhất | CHƯA THỰC THI |
| S-05 | Stop/Completed hoặc retry hai lần | Summary không append trùng; cache chỉ đổi khi ghi thành công | CHƯA THỰC THI |
| S-06 | CSV đang bị Excel khóa | Báo chưa ghi được, giữ Summary cho retry | CHƯA THỰC THI |
| S-07 | Header CSV cũ không khớp | Không append lệch cột; đề nghị migration/backup | CHƯA THỰC THI |
| S-08 | Crossed/exited và clearance | Departed=crossed, exited khác; hold summary tổng phiên | CHƯA THỰC THI |
| S-09 | Lưu JSON config | Không VehicleSnapshot/metrics/series | Schema kiểm tra phần cấu trúc |
| S-10 | Renderer nhận Snapshot | Không sửa DTO/Queue/Engine; metadata geometry chỉ đọc | Task 4 có test DTO; integration UI chưa thực thi |

## Artifact và hồi quy

| ID | Kiểm tra | Expected | Trạng thái |
| --- | --- | --- | --- |
| W-01 | Hai PNG | PNG binary thật, 1920×1080, giải mã được | Kiểm tra file và xem ảnh |
| W-02 | Hai SVG | XML/SVG hợp lệ, editable, labels/units rõ | Kiểm tra file và xem PNG xuất từ SVG |
| W-03 | Layout | Không cắt/chồng chữ; đủ form, controls, map và ba chart | Visual QA, không test renderer động |
| W-04 | Links Markdown | Link PNG/SVG/example/schema/testcases tồn tại | Kiểm tra artifacts |
| R-01 | Task 1 smoke | Vẫn import được; root JSON đúng configs/schema v2 | pytest |
| R-02 | Task 3 và 4 | Source branch giữ nguyên; có thể kiểm tra phối hợp trên bản tạm | Không merge thật trong Task 5 |

Các tình huống chưa thực thi không được tính là pytest SKIP trừ khi có test
được đánh dấu skip thực sự. Không dùng wireframe/static fixture để tuyên bố
CRUD, FileStorage, Engine hoặc biểu đồ thời gian thực đã hoạt động.

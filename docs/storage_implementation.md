# Trạng thái Storage đến hết task 17/10

FileStorage và ConfigManager đã có implementation JSON V2. Đây là cập nhật
trạng thái runtime cho các hợp đồng Task 5 lịch sử; UI/CSV vẫn chưa nối ở nhánh này.

- Parser chỉ nhận root schema_version=2/configs, từ chối duplicate keys,
  NaN/Infinity, cấu hình sai và ID trùng; lỗi giữ nguyên file.
- Cả load và save validate mọi Config, gồm motion disabled, không ép int/fill key.
- Mỗi lần lưu có NamedTemporaryFile riêng cùng thư mục, allow_nan=False,
  flush/fsync, đóng handle rồi os.replace; lỗi chỉ dọn file tạm của thao tác đó.
- ConfigManager khóa trọn giao dịch đọc/candidate/ghi/cache theo đường dẫn.
  Mỗi mutation đọc lại file trong khóa để hai Manager không ghi đè snapshot cũ.
  Cache chỉ đổi sau save thành công; lỗi giữ cache/file cũ.
- get/list trả deepcopy để caller không sửa RAM ngoài CRUD; tra cứu get dùng dict.
  Cache một Manager là bản chụp lần nạp/commit gần nhất. Gọi reload để thấy thay
  đổi từ Manager khác. reload lỗi giữ cache hiện tại.
- API chuẩn list/get/validate/create/update/delete; các tên cũ *_configs,
  *_config và valid_config được giữ để tương thích caller.

Khóa là RLock dùng chung giữa các thread trong process Streamlit, không phải
khóa liên process. Mô hình chạy nhiều process cùng ghi file cần một cơ chế
đồng bộ liên process hoặc kho dữ liệu dùng chung trước khi triển khai kiểu đó.

`tests/test_storage_crud.py` kiểm tra CRUD, ID bất biến, Config validation,
get/list detached, parser, invalid save không ghi đè, lỗi fsync/replace trong
create/update/delete, file tạm không thuộc thao tác và hai create đồng thời từ
cùng/hai Manager. Các test dùng file tạm, không sửa data/junctions.json.

CSV/dashboard thuộc task 19/10, không được thêm trong đợt sửa này.

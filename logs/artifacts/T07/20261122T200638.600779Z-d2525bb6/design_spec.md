## Overview
Giao diện tiếng Việt gọn gàng, một cột căn giữa, dùng màu xanh làm điểm nhấn. Không dùng hình ảnh, biểu tượng ngoài hoặc phông chữ tải từ mạng.

## Layout
Cột rộng tối đa 600px, cách mép màn hình 16px; lề trên 40px. Thứ tự: tiêu đề, biểu mẫu, thông báo lỗi, bộ lọc, tìm kiếm, danh sách. Khoảng cách giữa các khối 24px; giữa nhãn và trường nhập 8px.

## Components
- **Tiêu đề:** “Quản lý công việc”, 28px, đậm.
- **Biểu mẫu:** `task-form`; nhãn “Công việc” liên kết `task-input`. Ô nhập văn bản cao 44px, `maxlength="100"`, chiếm phần rộng còn lại. Nút “Thêm” cao 44px, rộng tối thiểu 72px; cách ô nhập 8px.
- **Bộ lọc:** `filter-all`: “Tất cả”; `filter-todo`: “Chưa hoàn thành”; `filter-done`: “Đã hoàn thành”. Nút cao tối thiểu 44px, cách nhau 8px. Mặc định chọn “Tất cả”; nút chọn nền xanh, chữ trắng.
- **Tìm kiếm:** `search-input`, nhãn “Tìm kiếm”, cao 44px, rộng toàn cột.
- **Danh sách:** `task-list`; mỗi hàng nền trắng, viền mảnh, đệm 12px, cách nhau 8px. Checkbox 20px bên trái; tiêu đề 16px xuống dòng; nút “Xóa” bên phải, vùng bấm tối thiểu 44px.
- **Thông báo:** lỗi “Không thể thực hiện. Vui lòng thử lại.” màu đỏ. Khi không có kết quả, hiện “Chưa có công việc nào” căn giữa, đệm 32px.

## Visual style
| Token | Giá trị |
|---|---|
| Nền trang | #F8FAFC |
| Nền thẻ | #FFFFFF |
| Chữ | #0F172A |
| Chữ phụ | #475569 |
| Chính | #1D4ED8 |
| Nguy hiểm | #B91C1C |
| Viền | #64748B |
| Phông | system-ui, sans-serif |
| Cỡ chữ cơ sở | 16px |
| Bo góc | 8px |
| Đơn vị khoảng cách | 8px |

## States and behavior
Tải danh sách bằng GET `/tasks`. Thêm bằng POST: không tải lại trang; xóa nội dung nhập sau thành công, đưa việc mới lên đầu nếu khớp bộ lọc. Checkbox dùng PATCH; thành công thì gạch ngang tiêu đề, màu chữ phụ. “Xóa” dùng DELETE; chỉ bỏ hàng sau thành công.

Lọc và tìm kiếm kết hợp `status` và `q`; bỏ `status` cho tất cả, dùng `todo` hoặc `done`. Giữ bộ lọc khi cập nhật. Lỗi giữ dữ liệu hiện tại. Hover nút dùng viền xanh; focus có vòng xanh 3px, cách 2px.

## Responsive behavior
Dưới 600px: lề trên 24px; nút lọc được xuống dòng. Ô nhập và nút thêm vẫn cùng hàng; tiêu đề công việc ngắt cả chuỗi dài.

## Accessibility
Đặt ngôn ngữ tiếng Việt; nhãn liên kết đúng trường. Checkbox có tên công việc trong nhãn; nút xóa có tên truy cập tương ứng. Bộ lọc dùng trạng thái nhấn; lỗi được thông báo tự động. Mọi điều khiển có focus rõ; tương phản chữ tối thiểu 4.5:1.
## Overview
Giao diện tiếng Việt đơn giản, sáng và thoáng, dùng một màu xanh chủ đạo. Một cột duy nhất giúp thêm, tìm và quản lý công việc nhanh chóng.

## Layout
Cột giữa rộng tối đa 600px, lề ngang 16px, cách đỉnh 40px. Thứ tự: tiêu đề, biểu mẫu thêm, thông báo lỗi, bộ lọc, tìm kiếm, danh sách. Khoảng cách khối 24px; khoảng cách điều khiển 8px.

## Components
- **Tiêu đề:** `Quản lý công việc`, 28px, đậm.
- **Biểu mẫu:** `task-form`; nhãn `Công việc` phía trên `task-input`. Ô nhập có `maxlength="100"`, cao 44px, chiếm phần rộng còn lại. Nút `Thêm` cao 44px, nền xanh, chữ trắng.
- **Bộ lọc:** `filter-all`: `Tất cả`; `filter-todo`: `Chưa hoàn thành`; `filter-done`: `Đã hoàn thành`. Cao tối thiểu 44px. Mặc định chọn `Tất cả`; nút chọn nền xanh, chữ trắng; nút khác nền trắng, chữ tối.
- **Tìm kiếm:** `search-input`, nhãn `Tìm công việc`, rộng toàn cột, cao 44px.
- **Danh sách:** `task-list`; mỗi hàng nền trắng, viền mảnh, đệm 12px, cách nhau 8px. Checkbox 20px trong vùng bấm 44px; tiêu đề co giãn, xuống dòng; nút `Xóa` cao 44px, chữ đỏ.
- **Thông báo:** lỗi chữ đỏ trên nền trắng, đặt sau biểu mẫu; trạng thái rỗng `Chưa có công việc nào`, căn giữa, đệm 32px.

## Visual style
| Token | Giá trị |
|---|---|
| Page background | #F8FAFC |
| Card background | #FFFFFF |
| Text color | #0F172A |
| Muted text color | #475569 |
| Primary color | #1D4ED8 |
| Danger color | #B91C1C |
| Border color | #64748B |
| Font stack | system-ui, sans-serif |
| Base font size | 16px |
| Border radius | 8px |
| Spacing unit | 8px |

## States and behavior
Dùng `fetch`, không tải lại trang. Thêm thành công: xóa nội dung nhập, trả focus, hiển thị mới nhất trước nếu khớp bộ lọc. Checkbox cập nhật `done`; tiêu đề hoàn thành gạch ngang, màu chữ phụ. Xóa thành công bỏ hàng.

Lọc dùng `status=todo` hoặc `status=done`; `Tất cả` bỏ `status`. Tìm kiếm dùng `q`, kết hợp bộ lọc hiện tại. Cập nhật danh sách sau thao tác, giữ thứ tự mới nhất trước.

Rỗng dùng thông báo đã nêu. Lỗi API: `Không thể thực hiện. Vui lòng thử lại.`; giữ dữ liệu nhập và trạng thái thành công trước đó. Hover nút xanh dùng #1E40AF.

## Responsive behavior
Dưới 600px: cách đỉnh 24px, tiêu đề 24px. Giữ biểu mẫu ngang; ô nhập co được. Bộ lọc tự xuống dòng, không cuộn ngang.

## Accessibility
Đặt ngôn ngữ trang tiếng Việt; nhãn liên kết ô nhập. Checkbox có tên chứa tiêu đề; nút xóa có tên truy cập riêng từng việc. Bộ lọc dùng trạng thái nhấn. Mọi điều khiển có focus viền #1D4ED8 dày 3px, lệch 2px. Lỗi được thông báo qua vùng cảnh báo. Chữ đạt tương phản tối thiểu 4.5:1.
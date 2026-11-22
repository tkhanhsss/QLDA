## Overview
A calm, clean Vietnamese task page with one centered column and a white panel on a pale background. Clear labels, generous spacing, and one blue accent keep adding and managing tasks straightforward.

## Layout
- Main column: maximum 600px wide, centered, 40px top margin, 24px outer gutters.
- Heading above panel, separated by 24px.
- Panel: 24px padding; vertically ordered add form, filters, search, error region, task list. Use 24px between sections.
- Form: label above a horizontal input/button row with 8px gap.
- Filters: three adjacent buttons with 8px gaps. Search fills panel width.
- Task rows: checkbox, flexible title, delete button; 12px gaps, 12px vertical padding, thin bottom dividers.

## Components
- **Heading:** “Quản lý công việc”; 28px, bold.
- **Add form:** `task-form`; label “Công việc mới” associated with `task-input`. Input: text, `maxlength="100"`, 44px tall. Submit button: “Thêm”, 44px tall, blue background, white text.
- **Filters:** `filter-all`: “Tất cả”; `filter-todo`: “Chưa hoàn thành”; `filter-done`: “Đã hoàn thành”. Minimum height 44px; selected button blue with white text, others white with dark text.
- **Search:** `search-input`; visible label “Tìm kiếm”; search input, 44px tall.
- **List:** `task-list`; semantic list without bullets. Titles use 16px text and wrap naturally. Each row has a native checkbox and “Xóa” button with red text, minimum 44px target.
- **Empty message:** “Chưa có công việc nào”; centered, muted, 32px vertical padding.
- **Error region:** “Không thể thực hiện. Vui lòng thử lại.” Red text, displayed above list only when needed.

## Visual style
| Token | Value |
|---|---|
| Page background | #F3F4F6 |
| Card background | #FFFFFF |
| Text | #111827 |
| Muted text | #4B5563 |
| Primary | #1D4ED8 |
| Danger | #B91C1C |
| Border | #6B7280 |
| Font stack | system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif |
| Base size | 16px |
| Radius | 8px |
| Spacing unit | 8px |

## States and behavior
Initially select “Tất cả”. Submit trimmed, nonempty titles through the API; success clears input, restores its focus, and places the task first when matching current criteria.

Checkbox updates completion; completed titles are muted and struck through. Delete removes the row after success. Reapply active criteria after mutations.

Filters request `status`; search requests `q`, retaining both together. Latest results win. Empty results show the required empty message.

On failure retain existing data and input, restore unsuccessful checkbox changes, and announce the error. Hover darkens primary to #1E40AF; secondary controls use #F3F4F6.

## Responsive behavior
Below 600px: use 16px gutters, padding, and top margin; heading 24px. Keep input/button together; filters wrap without horizontal overflow. Long titles wrap.

## Accessibility
Use Vietnamese document language, associated labels, native controls, and semantic heading/list structure. Checkboxes reference task titles; delete accessible names include titles. Filters expose pressed state. Announce errors and list updates. Every control has a visible 3px #1D4ED8 focus outline with 2px offset. Maintain 4.5:1 text contrast and 44px interactive targets.
## Overview
A clean Vietnamese task manager with one centered column, a white card, and blue primary controls. System typography, generous spacing, and clear states keep the interface readable without external assets.

## Layout
- Column: maximum 600px wide, centered; 32px top margin and 16px page gutters.
- Heading above the card, separated by 24px.
- Card: 24px padding; vertically arranged form, filter bar, search, message area, and list, with 20px gaps.
- Form: visible label above an input-and-button row with an 8px gap; input fills remaining width.
- Filters: three equal-width buttons with 8px gaps. Search spans the card width.
- List: full width; rows separated by borders, with 12px vertical padding.

## Components
- **Heading:** “Quản lý công việc”; 28px, bold.
- **Form:** `task-form`; input `task-input`, visible label “Công việc”, `maxlength="100"`; 44px minimum height. Submit button “Thêm”, blue background, white text, minimum 44px height.
- **Filters:** `filter-all` “Tất cả”; `filter-todo` “Chưa hoàn thành”; `filter-done` “Đã hoàn thành”. Minimum 44px height; selected button blue with white text, others white with dark text and border.
- **Search:** `search-input`; visible label “Tìm kiếm”; full-width search box, minimum 44px height.
- **List:** `task-list`; semantic list. Each row contains a native checkbox, wrapping title, and “Xóa” button. Checkbox target and delete button: minimum 44×44px. Row controls require no fixed IDs.
- **Messages:** empty text “Chưa có công việc nào”, centered with 24px padding. Error text “Có lỗi xảy ra. Vui lòng thử lại.” above the list, dark red. No additional IDs required.

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
| Font stack | system-ui, -apple-system, "Segoe UI", sans-serif |
| Base font size | 16px |
| Border radius | 8px |
| Spacing unit | 4px |

## States and behavior
Initial fetch shows newest first; show empty text only after successful empty results. Add through `fetch` without reload; clear input and refocus on success, inserting newest first while respecting active filters/search. Reject blank trimmed input with “Vui lòng nhập công việc.”

Toggle and delete update through the API; refresh current results after success. Completed titles use muted text and line-through. Failures preserve input and confirmed data.

Filters retain search; search retains status. Fetch with combined `status` and `q`; “Tất cả” omits status. Ignore stale responses.

Hover: primary #1E40AF; neutral controls #F3F4F6.

## Responsive behavior
Below 600px, use 16px card padding, 20px heading, and a stacked add button. Filters remain equal-width with wrapping Vietnamese labels. Titles wrap without horizontal scrolling.

## Accessibility
Set Vietnamese page language. Associate visible labels with inputs; checkbox accessible names include task titles, as do delete labels. Use selected-state semantics for filters, polite list announcements, and alert semantics for errors. Every control has a 3px #1D4ED8 focus outline with 3px offset. Maintain text contrast of at least 4.5:1.
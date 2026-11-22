# Số liệu M8

Run chính thức **20261122T203552.936530Z-225ae097**.
Các lần chạy M8 không đạt trước run chính thức 2.

- Run `20261122T200638.600779Z-d2525bb6` · [Ruff trong workspace trả mã khác 0](../logs/artifacts/20261122T200638.600779Z-d2525bb6-workspace-ruff.log)
- Run `20261122T202214.479093Z-28401fd3` · [Ruff trong workspace trả mã khác 0](../logs/artifacts/20261122T202214.479093Z-28401fd3-workspace-ruff.log)

Nguồn gồm [SQLite](../logs/messages.db), [JSONL](../logs/messages.jsonl), [transcript riêng](../logs/transcript_20261122T203552.936530Z-225ae097.md) và các file pytest đính kèm bên dưới.
Phạm vi tin nhắn từ [#246, dòng 1](../logs/transcript_20261122T203552.936530Z-225ae097.md) đến [#303, dòng 58](../logs/transcript_20261122T203552.936530Z-225ae097.md).

| Chỉ số | Kết quả | Nguồn |
| --- | ---: | --- |
| Tổng tin nhắn | 58 | [#246, dòng 1](../logs/transcript_20261122T203552.936530Z-225ae097.md)–[#303, dòng 58](../logs/transcript_20261122T203552.936530Z-225ae097.md) |
| Tổng token vào ghi nhận | 257,115 | Trường meta.tokens_in trong JSONL |
| Tổng token ra ghi nhận | 31,241 | Trường meta.tokens_out trong JSONL |
| Thời gian từ tin đầu tới tin cuối | 874.075471 giây | [#246, dòng 1](../logs/transcript_20261122T203552.936530Z-225ae097.md) (2026-11-22T20:35:52.947620+00:00) → [#303, dòng 58](../logs/transcript_20261122T203552.936530Z-225ae097.md) (2026-11-22T20:50:27.023091+00:00) |
| Tổng vòng sửa Coder | 4 | Số iteration lớn nhất của từng task |
| Task DONE | 7/7 | Các tin đóng task ở bảng dưới |
| Task BLOCKED | 0 | Các tin đóng task ở bảng dưới |
| Hồi quy cuối | 61/61 | [61/61 (mã 0)](../logs/artifacts/T07/20261122T203552.936530Z-225ae097-r1-regression-sum2zj7i.log) |
| Lỗi từ 9Router và lần thử lại yêu cầu HTTP | chưa đo | Log không có bộ đếm cho từng lần thử HTTP |

## Tin nhắn theo agent và loại

| Agent | Số tin | ID tin nhắn |
| --- | ---: | --- |
| User | 1 | #246 |
| PM | 16 | #247, #248, #253, #254, #259, #260, #268, #269, #277, #278, #283, #284, #292, #293, #294, #303 |
| Designer | 1 | #295 |
| Coder | 11 | #249, #255, #261, #264, #270, #273, #279, #285, #288, #296, #299 |
| Reviewer | 11 | #250, #256, #262, #265, #271, #274, #280, #286, #289, #297, #300 |
| Tester | 14 | #251, #252, #257, #258, #266, #267, #275, #276, #281, #282, #290, #291, #301, #302 |
| Orchestrator | 4 | #263, #272, #287, #298 |

| Loại tin | Số tin | ID tin nhắn |
| --- | ---: | --- |
| requirement | 1 | #246 |
| task_assign | 9 | #247, #248, #254, #260, #269, #278, #284, #293, #294 |
| design_spec | 1 | #295 |
| code_submit | 18 | #249, #251, #255, #257, #261, #264, #266, #270, #273, #275, #279, #281, #285, #288, #290, #296, #299, #301 |
| review_result | 11 | #250, #256, #262, #265, #271, #274, #280, #286, #289, #297, #300 |
| test_report | 7 | #252, #258, #267, #276, #282, #291, #302 |
| revision_request | 4 | #263, #272, #287, #298 |
| task_done | 7 | #253, #259, #268, #277, #283, #292, #303 |
| task_blocked | 0 |  |

## Độ đầy đủ của token

- `tokens_in` None ở 0 tin.
- `tokens_in` không có trường ở 6 tin (#246, #263, #272, #287, #294, #298).
- `tokens_out` None ở 0 tin.
- `tokens_out` không có trường ở 6 tin (#246, #263, #272, #287, #294, #298).
- Tổng token dùng các giá trị số đã ghi nhận trong `meta`.

## Kết quả theo task

Run sử dụng workspace đã có sẵn. Hồi quy ở từng mốc bao gồm mọi test hiện có, vì vậy tổng có thể thay đổi khi Tester thay file của task hiện tại.

| Task | Vòng sửa Coder | Kết quả | Pytest task lần cuối | Hồi quy lần cuối |
| --- | ---: | --- | --- | --- |
| T01 | 0 | DONE [#253, dòng 8](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [5/5 (mã 0)](../logs/artifacts/T01/20261122T203552.936530Z-225ae097-r0-task-8vz7s0su.log) | [60/60 (mã 0)](../logs/artifacts/T01/20261122T203552.936530Z-225ae097-r0-regression-7lnv0wgm.log) |
| T02 | 0 | DONE [#259, dòng 14](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [13/13 (mã 0)](../logs/artifacts/T02/20261122T203552.936530Z-225ae097-r0-task-nd_z6xg8.log) | [62/62 (mã 0)](../logs/artifacts/T02/20261122T203552.936530Z-225ae097-r0-regression-xdv11zzf.log) |
| T03 | 1 | DONE [#268, dòng 23](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [6/6 (mã 0)](../logs/artifacts/T03/20261122T203552.936530Z-225ae097-r1-task-evczmm8q.log) | [62/62 (mã 0)](../logs/artifacts/T03/20261122T203552.936530Z-225ae097-r1-regression-ydgwlu06.log) |
| T04 | 1 | DONE [#277, dòng 32](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [12/12 (mã 0)](../logs/artifacts/T04/20261122T203552.936530Z-225ae097-r1-task-ywtb2mgc.log) | [62/62 (mã 0)](../logs/artifacts/T04/20261122T203552.936530Z-225ae097-r1-regression-c7pqaawd.log) |
| T05 | 0 | DONE [#283, dòng 38](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [5/5 (mã 0)](../logs/artifacts/T05/20261122T203552.936530Z-225ae097-r0-task-hb6nhitj.log) | [61/61 (mã 0)](../logs/artifacts/T05/20261122T203552.936530Z-225ae097-r0-regression-epcxmju7.log) |
| T06 | 1 | DONE [#292, dòng 47](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [15/15 (mã 0)](../logs/artifacts/T06/20261122T203552.936530Z-225ae097-r1-task-23mtf62h.log) | [61/61 (mã 0)](../logs/artifacts/T06/20261122T203552.936530Z-225ae097-r1-regression-y47b0qf1.log) |
| T07 | 1 | DONE [#303, dòng 58](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [5/5 (mã 0)](../logs/artifacts/T07/20261122T203552.936530Z-225ae097-r1-task-i06unvfz.log) | [61/61 (mã 0)](../logs/artifacts/T07/20261122T203552.936530Z-225ae097-r1-regression-sum2zj7i.log) |

Pytest xanh ở lượt đầu cho **7/7 (100.0%)** task. Tỷ lệ hồi phục sau lần pytest đầu thất bại là **chưa đo (0 trường hợp)**. Tỷ lệ xanh cuối cùng là **7/7 (100.0%)**. Mẫu số tính theo task có cả log pytest riêng và hồi quy.

**3/7** task đạt ở vòng Coder 0 và **4/7** đạt sau một vòng sửa theo Reviewer. Các vòng sửa này diễn ra trước lượt pytest đầu tiên của từng task.

| Task | Lượt pytest | Vòng Coder | Tin báo | Pytest task | Hồi quy |
| --- | ---: | ---: | --- | --- | --- |
| T01 | 1 | 0 | PASS [#252, dòng 7](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [5/5 (mã 0)](../logs/artifacts/T01/20261122T203552.936530Z-225ae097-r0-task-8vz7s0su.log) | [60/60 (mã 0)](../logs/artifacts/T01/20261122T203552.936530Z-225ae097-r0-regression-7lnv0wgm.log) |
| T02 | 1 | 0 | PASS [#258, dòng 13](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [13/13 (mã 0)](../logs/artifacts/T02/20261122T203552.936530Z-225ae097-r0-task-nd_z6xg8.log) | [62/62 (mã 0)](../logs/artifacts/T02/20261122T203552.936530Z-225ae097-r0-regression-xdv11zzf.log) |
| T03 | 1 | 1 | PASS [#267, dòng 22](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [6/6 (mã 0)](../logs/artifacts/T03/20261122T203552.936530Z-225ae097-r1-task-evczmm8q.log) | [62/62 (mã 0)](../logs/artifacts/T03/20261122T203552.936530Z-225ae097-r1-regression-ydgwlu06.log) |
| T04 | 1 | 1 | PASS [#276, dòng 31](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [12/12 (mã 0)](../logs/artifacts/T04/20261122T203552.936530Z-225ae097-r1-task-ywtb2mgc.log) | [62/62 (mã 0)](../logs/artifacts/T04/20261122T203552.936530Z-225ae097-r1-regression-c7pqaawd.log) |
| T05 | 1 | 0 | PASS [#282, dòng 37](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [5/5 (mã 0)](../logs/artifacts/T05/20261122T203552.936530Z-225ae097-r0-task-hb6nhitj.log) | [61/61 (mã 0)](../logs/artifacts/T05/20261122T203552.936530Z-225ae097-r0-regression-epcxmju7.log) |
| T06 | 1 | 1 | PASS [#291, dòng 46](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [15/15 (mã 0)](../logs/artifacts/T06/20261122T203552.936530Z-225ae097-r1-task-23mtf62h.log) | [61/61 (mã 0)](../logs/artifacts/T06/20261122T203552.936530Z-225ae097-r1-regression-y47b0qf1.log) |
| T07 | 1 | 1 | PASS [#302, dòng 57](../logs/transcript_20261122T203552.936530Z-225ae097.md) | [5/5 (mã 0)](../logs/artifacts/T07/20261122T203552.936530Z-225ae097-r1-task-i06unvfz.log) | [61/61 (mã 0)](../logs/artifacts/T07/20261122T203552.936530Z-225ae097-r1-regression-sum2zj7i.log) |

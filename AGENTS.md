# AGENTS.md — Hướng dẫn cho AI coding agent

File này dành cho AI coding agent (Claude Code, Codex, Cursor, OpenCode...) khi làm việc trong repo này. Hãy đọc kỹ trước khi viết code. Yêu cầu của sản phẩm mà các agent sẽ xây nằm trong `requirements.md`.

## 1. Dự án là gì

Hệ thống đa AI Agent tự xây dựng phần mềm. Gồm 5 agent: **PM, Designer, Coder, Reviewer, Tester**, do một **Orchestrator** (không phải LLM) điều phối. Sản phẩm mà các agent xây là web app To-do (FastAPI + SQLite + HTML/JS), nằm trong `workspace/`.

Đây là bài tập cuối kỳ, nên mã phải **dễ đọc, dễ giải thích, dễ demo**. Ưu tiên đơn giản hơn là tối ưu.

## 2. Ràng buộc bắt buộc (do giảng viên yêu cầu)

1. **Agent giao tiếp rõ ràng, theo dõi và lưu lại được.** Mọi tương tác giữa các agent đi qua `MessageBus`, ghi vào SQLite + JSONL + transcript. Người dùng xem được qua dashboard.
2. **Tester test sau mỗi task.** Không task nào được Done nếu chưa qua Tester. Tester chạy test của task và cả test hồi quy.
3. Chạy thật được một dự án end-to-end, quay video demo được.

Nếu có thay đổi nào làm yếu một trong các ràng buộc này, **dừng lại và hỏi người dùng**.

## 3. Nguồn LLM: 9Router

Người dùng lấy token qua **9Router**, một proxy chạy local, có endpoint tương thích OpenAI.

- Base URL mặc định: `http://localhost:20128/v1`
- API key: lấy trong dashboard 9Router (`http://localhost:20128/dashboard`)
- Tên model: phải khớp đúng tên hiển thị trong dashboard 9Router (có thể là `provider/model` hoặc tên combo do người dùng tạo). **Không tự đoán và không hardcode tên model.** Đọc từ biến môi trường.
- 9Router có thể tự fallback sang model khác khi hết hạn mức, nên chất lượng đầu ra có thể dao động.

Biến môi trường (`.env.example`, người dùng sao chép thành `.env`):

```
ROUTER_BASE_URL=http://localhost:20128/v1
ROUTER_API_KEY=
MODEL_DEFAULT=
MODEL_PM=
MODEL_DESIGNER=
MODEL_CODER=
MODEL_REVIEWER=
MODEL_TESTER=
```

Agent nào không đặt model riêng thì dùng `MODEL_DEFAULT`.

`core/llm.py` phải:

- Dùng thư viện `openai`: `OpenAI(base_url=ROUTER_BASE_URL, api_key=ROUTER_API_KEY)`.
- Có hàm `chat(agent: str, system: str, user: str) -> LLMResult` với `LLMResult(text, model, tokens_in, tokens_out, duration_ms)`.
- Đặt timeout 120 giây. Thử lại tối đa 3 lần với backoff khi gặp 429, 5xx hoặc timeout.
- Ghi `tokens_in/out` từ `response.usage`; nếu router không trả thì để `None`, không báo lỗi.
- **Không dùng tool-calling hay function-calling.** Chỉ dùng văn bản có cấu trúc (mục 8), để ổn định với mọi model mà 9Router chọn.
- Đọc cấu hình từ `.env` bằng `python-dotenv`. Không bao giờ in API key ra log.
- Hàm `check_router()` gọi `GET {ROUTER_BASE_URL}/models` ở đầu `core/run.py`; nếu lỗi thì in hướng dẫn "hãy chạy 9Router và kiểm tra .env" rồi thoát.

## 4. Công nghệ

- Python 3.11+, quản lý bằng `pyproject.toml`
- `openai`, `langgraph`, `pydantic` v2, `python-dotenv`, `rich`, `streamlit`
- Sản phẩm mẫu: `fastapi`, `uvicorn`, `httpx`, `pytest`, `ruff`
- SQLite (thư viện chuẩn `sqlite3`), không dùng ORM cho Message Bus

Không thêm thư viện mới khi chưa cần. Nếu cần, nêu lý do.

## 5. Cấu trúc thư mục

```
project/
├── AGENTS.md                 # file này
├── requirements.md           # yêu cầu sản phẩm đưa cho PM
├── pyproject.toml
├── .env.example              # mẫu cấu hình 9Router (được commit)
├── .env                      # key thật (KHÔNG commit)
├── .gitignore
├── agents/
│   ├── __init__.py
│   ├── base.py  pm.py  designer.py  coder.py  reviewer.py  tester.py
│   └── prompts/              # pm.md, designer.md, coder.md, reviewer.md, tester.md
├── core/
│   ├── __init__.py
│   ├── schema.py  message_bus.py  llm.py  orchestrator.py
│   └── workspace.py  transcript.py  run.py
├── dashboard/
│   └── app.py
├── tests/                    # test của chính hệ thống agent (bus, schema, workspace, parser)
├── workspace/                # code do agent sinh ra (Git riêng, KHÔNG sửa tay); tự sinh khi chạy
├── logs/                     # messages.db, messages.jsonl, transcript.md, artifacts/<task_id>/; tự sinh khi chạy
└── report/                   # báo cáo, ảnh chụp màn hình, video (thêm sau khi chạy xong)
```

`workspace/` là nơi agent sinh code. Đừng trộn code hệ thống vào đó. Vì `workspace/` có Git riêng nên nó nằm ngoài repo chính (được ghi trong `.gitignore`); khi nộp bài thì nén riêng. `logs/` thì **được commit**, vì đó là bằng chứng lịch sử giao tiếp của các agent.

## 6. Schema tin nhắn (`core/schema.py`)

```python
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class Agent(str, Enum):
    USER = "user"; PM = "pm"; DESIGNER = "designer"
    CODER = "coder"; REVIEWER = "reviewer"; TESTER = "tester"
    ORCHESTRATOR = "orchestrator"

class MsgType(str, Enum):
    REQUIREMENT = "requirement"
    TASK_ASSIGN = "task_assign"
    DESIGN_SPEC = "design_spec"
    CODE_SUBMIT = "code_submit"
    REVIEW_RESULT = "review_result"
    TEST_REPORT = "test_report"
    REVISION_REQUEST = "revision_request"
    TASK_DONE = "task_done"
    TASK_BLOCKED = "task_blocked"

class Message(BaseModel):
    model_config = ConfigDict(populate_by_name=True)  # cho phép sender= hoặc from=
    id: Optional[int] = None          # do bus gán
    run_id: str
    timestamp: str                    # ISO 8601, do bus gán
    task_id: Optional[str] = None     # "T03", None với requirement
    iteration: int = 0
    sender: Agent = Field(alias="from")
    to: Agent
    type: MsgType
    status: Optional[str] = None      # PASS/FAIL/APPROVE/REQUEST_CHANGES/DONE/BLOCKED
    content: str
    artifacts: list[str] = []         # đường dẫn tương đối tới file liên quan
    meta: dict = {}                   # model, tokens_in, tokens_out, duration_ms
```

JSON xuất ra dùng khóa `"from"` (không phải `sender`).

## 7. Message Bus (`core/message_bus.py`)

```python
class MessageBus:
    def __init__(self, run_id: str, logs_dir: str = "logs"): ...
    def publish(self, msg: Message) -> Message: ...        # gán id + timestamp, ghi 3 nơi
    def inbox(self, agent: Agent, task_id: str | None = None) -> list[Message]: ...
    def history(self, task_id=None, sender=None, type=None) -> list[Message]: ...
    def export_transcript(self) -> str: ...                # ghi logs/transcript.md
```

Mỗi lần `publish` phải ghi đồng thời:
1. SQLite `logs/messages.db`, bảng `messages` (có cột `run_id`)
2. Nối thêm một dòng vào `logs/messages.jsonl`
3. Một dòng vào `logs/transcript.md`, dạng `[09:15:02] **Tester → Coder** (T03, vòng 2, test_report, FAIL): nội dung rút gọn`
4. In ra terminal bằng `rich`, mỗi agent một màu

Agent **không bao giờ** gọi trực tiếp agent khác. Agent chỉ nhận đầu vào do Orchestrator đọc từ bus, và trả về một `Message` để Orchestrator publish.

## 8. Định dạng đầu ra của agent

Agent trả văn bản thuần theo định dạng cố định, để parser đọc được ổn định.

**Code (Coder trả về):**

~~~
### FILE: app/main.py
```python
...nội dung file...
```
### FILE: app/models.py
```python
...
```
~~~

Parser dùng regex tìm `### FILE: <path>` rồi khối code ngay sau. Quy tắc bảo vệ:
- Chỉ nhận đường dẫn tương đối, không chứa `..`, không bắt đầu bằng `/`
- Từ chối ghi vào `tests/` khi người gọi là Coder
- Mỗi file phải đầy đủ nội dung, không viết "... phần còn lại giữ nguyên"

**Quyết định (Reviewer, Tester, PM):** dòng đầu là từ khóa, phần sau là giải thích.

```
VERDICT: APPROVE | REQUEST_CHANGES
```
Reviewer liệt kê vấn đề theo dạng `- [file:dòng] mô tả`.

PM trả backlog dạng JSON trong khối ```json```:
```json
[{"id":"T01","title":"...","needs_ui":false,"acceptance":["...","..."]}]
```

**Khi đầu ra sai định dạng:** `agents/base.py` thử lại tối đa 2 lần, gửi lại cho agent kèm câu "Đầu ra trước không hợp lệ vì: <lý do>. Hãy trả lại đúng định dạng." Nếu vẫn sai thì Orchestrator publish `task_blocked` với lý do rõ ràng.

## 9. Hợp đồng từng agent

| Agent | Đầu vào | Đầu ra (type) | Ghi chú |
|-------|---------|---------------|---------|
| PM | `requirement` hoặc kết quả task | `task_assign`, `task_done`, `task_blocked` | Backlog tối đa 7 task, mỗi task có tiêu chí chấp nhận kiểm tra được |
| Designer | `task_assign` (task có UI) | `design_spec` | Mô tả bố cục, thành phần, hành vi bằng Markdown. Không viết code |
| Coder | `task_assign`, `design_spec`, `revision_request` | `code_submit` | Chỉ viết code trong `workspace/`, không sửa `tests/` |
| Reviewer | `code_submit` | `review_result` | Chạy `ruff check` thật rồi gộp với review của LLM |
| Tester | `review_result` (APPROVE) | `test_report` | Xem mục 10 |

System prompt của từng agent nằm trong `agents/prompts/<agent>.md`, viết bằng **tiếng Anh** để model hiểu tốt. Mỗi prompt gồm: vai trò, đầu vào nhận được, định dạng đầu ra bắt buộc, những điều cấm. Đầu vào của mỗi agent do `agents/base.py` dựng thành các section có tiêu đề `## ...` **đúng như prompt mô tả** (ví dụ `## TASK BRIEF`, `## ACCEPTANCE CRITERIA`, `## PROJECT FILES`, `## FEEDBACK`). PM có 3 chế độ (`MODE: PLAN`, `MODE: ASSIGN`, `MODE: CLOSE`) và Tester có 2 chế độ (`MODE: WRITE_TESTS`, `MODE: REPORT`), khai báo ở dòng đầu của đầu vào. Agent Tester **không được nhìn thấy code** của Coder khi viết test; `tests/conftest.py` do Tester tạo ở task đầu tiên.

## 10. Luồng cho mỗi task và quy tắc Tester

Orchestrator (LangGraph `StateGraph`) xử lý tuần tự từng task:

```
assign → [design nếu needs_ui] → code → review → test → done
              review REQUEST_CHANGES → code (iteration + 1)
              test FAIL → code (iteration + 1)
              iteration > 3 → blocked
```

State gồm: `run_id`, `backlog`, `current_task`, `iteration`, `status` từng task.

**Quy tắc Tester (bắt buộc, theo yêu cầu của thầy):**
1. Chạy sau **mỗi** task, không gộp nhiều task.
2. Viết test cho task hiện tại vào `workspace/tests/test_<task_id>.py`, **dựa trên tiêu chí chấp nhận** trong `task_assign`, không dựa vào việc đọc code của Coder.
3. Chạy `pytest tests/test_<task_id>.py`, sau đó chạy `pytest tests/` (hồi quy).
4. Task chỉ PASS khi cả hai đều xanh.
5. Gửi `test_report` gồm: PASS/FAIL, số test đạt/tổng, tên test lỗi, đường dẫn log đính kèm trong `artifacts`. Lưu log vào `logs/artifacts/<task_id>/`.
6. Test chạy trong `workspace/`, có timeout 60 giây.
7. Việc chạy `pytest` do `core/workspace.py` thực hiện, không phải LLM. Kết quả PASS/FAIL do **exit code** quyết định; Tester (chế độ `REPORT`) chỉ giải thích lỗi. Nếu `test_report` có `CAUSE: TEST` (lỗi nằm ở chính file test), Orchestrator cho Tester viết lại test đúng 1 lần (chế độ `WRITE_TESTS` kèm `## FEEDBACK`) và việc này **không** tính vào vòng sửa của Coder.

Khi task PASS: Orchestrator `git add -A && git commit -m "<task_id>: passed after <n> iterations"` trong `workspace/`, rồi PM publish `task_done`.

## 11. Workspace và an toàn khi chạy code

`core/workspace.py` cung cấp: `write_files()`, `run(cmd, timeout)`, `run_pytest(path)`, `run_ruff()`, `git_commit(msg)`.

- Mọi thao tác chạy trong `workspace/` (cwd cố định)
- Chỉ cho phép các lệnh trong danh sách trắng: `pytest`, `ruff`, `git`, `python -m ...`. Không chạy lệnh tùy ý do LLM sinh ra
- Có timeout cho mọi lệnh; lệnh quá hạn thì kill và báo lỗi
- Không đọc hoặc ghi ngoài `workspace/` và `logs/`

## 12. Dashboard (`dashboard/app.py`, Streamlit)

Đọc từ `logs/messages.db`, tự làm mới mỗi 2 giây.
- Timeline chat theo thứ tự thời gian, màu theo agent
- Kanban Todo / In progress / Testing / Done / Blocked, suy ra từ tin nhắn
- Chọn task để xem: code đã ghi, log test, số vòng sửa
- Bộ lọc: task, agent, loại tin nhắn; chọn `run_id`
- Số liệu: tổng tin nhắn, tổng token, thời gian, số vòng sửa

## 13. Lệnh thường dùng

```
pip install -e .
cp .env.example .env              # rồi điền key và tên model từ 9Router
python -m core.run --requirement requirements.md
streamlit run dashboard/app.py
pytest tests/                     # test của hệ thống
cd workspace && pytest tests/     # test của sản phẩm do agent sinh ra
ruff check .
```

## 14. Thứ tự thực hiện (vibe coding từng bước)

Làm **từng milestone một**. Sau mỗi milestone: chạy kiểm tra, báo kết quả cho người dùng, chờ xác nhận rồi mới sang bước tiếp.

| M | Việc | Kiểm tra xong |
|---|------|---------------|
| M0 | Khung dự án, `pyproject.toml`, `.env.example`, `.gitignore` (có `.env`, `.venv/`, `__pycache__/`, `workspace/`; **không** ignore `logs/`), các file `__init__.py`, `core/llm.py` + `check_router()` | Gọi được 1 câu hỏi qua 9Router, in ra câu trả lời và số token |
| M1 | `schema.py`, `message_bus.py`, `transcript.py` + test | `pytest tests/` xanh; publish 3 tin nhắn thì thấy đủ ở SQLite, JSONL, transcript |
| M2 | `workspace.py` (parser `### FILE:`, ghi file, chạy lệnh, git) + test | Test parser với đầu vào tốt và xấu (đường dẫn `..`) |
| M3 | 5 file prompt + `agents/base.py` (gọi LLM, kiểm tra định dạng, thử lại) | Mỗi agent chạy riêng được với đầu vào giả |
| M4 | Orchestrator: PM → Coder → commit cho 1 task (T01) | `python -m core.run` sinh `workspace/` có `GET /health` chạy được |
| M5 | Thêm Reviewer + Tester + vòng sửa lỗi + BLOCKED | Chạy T01–T03; xem được ít nhất một vòng FAIL → sửa → PASS trong transcript |
| M6 | Thêm Designer cho task UI | T07 có `design_spec` trước khi Coder viết |
| M7 | Dashboard Streamlit | Xem live khi pipeline đang chạy; lọc theo task |
| M8 | Chạy trọn T01–T07, thu số liệu, xuất transcript, dọn dẹp | Sản phẩm To-do chạy được, `pytest` xanh |

## 15. Quy ước mã

- Có type hint, docstring ngắn bằng tiếng Việt hoặc tiếng Anh nhất quán trong từng file
- Hàm ngắn, một việc; tên biến bằng tiếng Anh
- Dùng `logging` hoặc `rich`, không dùng `print` rải rác
- Mỗi module trong `core/` có test trong `tests/`
- Lỗi phải có thông điệp rõ ràng, nói người dùng cần làm gì
- Commit nhỏ, thông điệp rõ

## 16. Điều không được làm

- Không cho agent gọi trực tiếp nhau, không bỏ qua `MessageBus`
- Không gộp hoặc bỏ bước Tester, không đánh dấu Done khi test chưa xanh
- Không cho Coder sửa `tests/`
- Không hardcode API key hoặc tên model; không in key ra log; không commit `.env`
- Không dùng tool-calling của LLM
- Không để vòng lặp sửa lỗi vượt quá 3 lần
- Không sửa tay file trong `workspace/` (muốn đổi thì đổi prompt hoặc quy trình rồi chạy lại)
- Không xóa log của lần chạy hỏng; giữ lại để phân tích trong báo cáo
- Không thêm tính năng ngoài phạm vi khi chưa hỏi

## 17. Khi bí

- Nếu yêu cầu mơ hồ hoặc mâu thuẫn với mục 2: hỏi người dùng, đừng đoán
- Nếu 9Router báo lỗi hoặc trả kết quả lạ: in nguyên văn lỗi, đừng che; gợi ý người dùng kiểm tra dashboard 9Router (hạn mức, tên model, key)
- Nếu một milestone quá lớn: chia nhỏ rồi báo lại kế hoạch trước khi làm

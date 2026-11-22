"""Run the M0 connectivity check and send one prompt to 9Router."""

from rich.console import Console

from core.llm import LLMError, chat, check_router


def main() -> int:
    """Check the router and display the demo response and token counts."""
    console = Console()
    errors = Console(stderr=True)
    try:
        check_router()
    except LLMError as error:
        errors.print(f"{error}\nHãy chạy 9Router và kiểm tra .env.", markup=False)
        return 1

    try:
        result = chat("pm", "Answer briefly in plain text.", "What is 2 + 2?")
    except LLMError as error:
        errors.print(
            f"{error}\nHãy kiểm tra tên model, API key và hạn mức trong dashboard 9Router.",
            markup=False,
        )
        return 1

    tokens_in = result.tokens_in if result.tokens_in is not None else "không có dữ liệu"
    tokens_out = (
        result.tokens_out if result.tokens_out is not None else "không có dữ liệu"
    )
    console.print(result.text, markup=False, highlight=False)
    console.print(f"Model: {result.model}", markup=False)
    console.print(f"Token vào: {tokens_in} | Token ra: {tokens_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

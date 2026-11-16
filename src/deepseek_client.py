"""DeepSeek tool calling; đọc key local và ghi usage, không ghi thông tin xác thực."""
import json
import math
import os
import time


class ProviderCallError(RuntimeError):
    pass


class CostLimitError(RuntimeError):
    pass


def load_api_key(env_path):
    from dotenv import dotenv_values

    value = (os.environ.get("DEEPSEEK_API_KEY") or dotenv_values(env_path).get("DEEPSEEK_API_KEY") or "").strip()
    if not value or value.casefold() in {"your_api_key", "key_của_bạn", "key_cua_ban", "..."} or value.startswith("<"):
        raise ValueError("Chưa có DEEPSEEK_API_KEY. Điền key vào .env rồi lưu; không đưa key vào chat hoặc Git.")
    return value


def validate_config(config):
    if config.get("provider") != "deepseek" or config.get("base_url", "").rstrip("/") != "https://api.deepseek.com":
        raise ValueError("Cấu hình này dùng API DeepSeek chính thức.")
    if config.get("model") != "deepseek-flash" or config.get("thinking") != "disabled":
        raise ValueError("Baseline dùng deepseek-flash, tắt thinking để hỗ trợ tool_choice bắt buộc.")
    for key in ("max_output_tokens", "request_timeout_seconds", "max_model_calls", "max_searches", "top_k", "context_budget_chars"):
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f"{key} phải là số nguyên dương.")
    if config["max_model_calls"] < config["max_searches"] + 1:
        raise ValueError("Cần dành ít nhất một lượt model để kết thúc sau các lượt tìm kiếm.")
    if config.get("retrieval_method") not in ("dense", "tfidf", "hybrid"):
        raise ValueError("Phương pháp retrieval không hợp lệ.")
    if config.get("context_selection") != "latest_search_first":
        raise ValueError("Baseline chọn context theo lượt tìm gần nhất, loại ID trùng.")
    limit = config.get("estimated_cost_limit_usd")
    if type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0:
        raise ValueError("Giới hạn chi phí ước tính phải là số dương.")
    for key in ("peak_usd_per_million_cached_input", "peak_usd_per_million_uncached_input", "peak_usd_per_million_output"):
        rate = config["pricing"].get(key)
        if type(rate) not in (int, float) or not math.isfinite(rate) or rate < 0:
            raise ValueError("Đơn giá token không hợp lệ.")


def usage_cost_upper(usage, pricing):
    prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if type(prompt) is not int or type(completion) is not int or min(prompt, completion) < 0:
        raise ProviderCallError("API không trả usage token hợp lệ; không giả định chi phí bằng 0.")
    details = usage.get("prompt_tokens_details") or {}
    cached = usage.get("prompt_cache_hit_tokens", details.get("cached_tokens", 0))
    missed = usage.get("prompt_cache_miss_tokens", prompt - cached)
    if type(cached) is not int or type(missed) is not int or min(cached, missed) < 0 or cached + missed != prompt:
        raise ProviderCallError("Thống kê cache token không khớp tổng input token.")
    return (cached * pricing["peak_usd_per_million_cached_input"]
            + missed * pricing["peak_usd_per_million_uncached_input"]
            + completion * pricing["peak_usd_per_million_output"]) / 1_000_000


class DeepSeekClient:
    def __init__(self, config, api_key):
        from openai import OpenAI

        validate_config(config)
        self.config = config
        self.api_requests = 0
        self.estimated_cost_upper_usd = 0.0
        self.client = OpenAI(api_key=api_key, base_url=config["base_url"],
                             timeout=config["request_timeout_seconds"], max_retries=0)

    def complete(self, messages, tools, tool_choice):
        pricing = self.config["pricing"]
        # Số byte UTF-8 cộng phần đệm là ước lượng bảo thủ cho input trước khi gọi.
        request_bytes = len(json.dumps({"messages": messages, "tools": tools}, ensure_ascii=False).encode("utf-8"))
        reserve = ((request_bytes + 1000) * pricing["peak_usd_per_million_uncached_input"]
                   + self.config["max_output_tokens"] * pricing["peak_usd_per_million_output"]) / 1_000_000
        if self.estimated_cost_upper_usd + reserve > self.config["estimated_cost_limit_usd"]:
            raise CostLimitError("Dừng trước request tiếp theo vì chạm giới hạn chi phí ước tính.")
        self.api_requests += 1
        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.config["model"], messages=messages, tools=tools, tool_choice=tool_choice,
                temperature=self.config["temperature"], max_tokens=self.config["max_output_tokens"],
                extra_body={"thinking": {"type": "disabled"}}, stream=False,
            )
        except Exception as error:
            self.estimated_cost_upper_usd += reserve
            status = getattr(error, "status_code", None)
            hints = {401: "Key không hợp lệ.", 402: "Tài khoản API chưa đủ số dư.",
                     429: "API giới hạn tần suất.", 503: "Dịch vụ tạm quá tải."}
            hint = hints.get(status, "Kiểm tra kết nối và trạng thái dịch vụ.")
            raise ProviderCallError(f"DeepSeek {type(error).__name__}, HTTP {status}: {hint}") from None
        try:
            usage = response.usage.model_dump() if response.usage else {}
            cost = usage_cost_upper(usage, pricing)
        except Exception:
            self.estimated_cost_upper_usd += reserve
            raise
        self.estimated_cost_upper_usd += cost
        choice = response.choices[0]
        message = {"role": "assistant", "content": choice.message.content,
                   "tool_calls": [{"id": call.id, "type": "function",
                                   "function": {"name": call.function.name, "arguments": call.function.arguments}}
                                  for call in (choice.message.tool_calls or [])]}
        return {"message": message, "finish_reason": choice.finish_reason,
                "model": response.model, "request_id": response.id,
                "system_fingerprint": getattr(response, "system_fingerprint", None),
                "usage": usage, "estimated_cost_upper_usd": cost,
                "elapsed_ms": (time.perf_counter() - started) * 1000}

    def close(self):
        self.client.close()

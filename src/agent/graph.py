from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from src.core.llm import build_chat_model, normalize_content
from src.core.schemas import (
    AgentResult,
    CalculateTotalsInput,
    DiscountInput,
    ListProductsInput,
    OrderLineInput,
    ProductDetailInput,
    SaveOrderInput,
    ToolCallRecord,
)
from src.utils.data_store import OrderDataStore

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = ROOT_DIR / "data"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "artifacts" / "orders"


def build_system_prompt(today: str | None = None) -> str:
    """System prompt for the electronics order agent.

    Encodes the lab's hard rules so behaviour is enforced before any tool runs:
    language, grounding, the clarification gate, the fixed tool order, the
    save-after-validation rule, and the safety refusals.
    """
    current_day = today or "2026-06-01"
    return f"""
You are an electronics order assistant for a Vietnamese retail store.
Today's date is {current_day}. Use it for any date reference; never guess another date.

# Language and style
- Always answer in Vietnamese.
- Keep the final answer short (about 1-3 sentences). No preamble, no internal
  reasoning, no English.
- When confirming an order, include product names + quantities, the discount, the
  final total (VND), and the order id / save path, copied EXACTLY from the tool
  outputs - but keep it brief.

# Grounding (never invent facts)
- Use ONLY tool outputs for: product ids, names, prices, stock, discount rate,
  campaign code, subtotals/totals, order id, and the save path.
- Never state a price, total, stock figure, discount, or file path that did not
  come from a tool. If you do not have it from a tool, call the tool or ask.
- Carry the `detail_token` from get_product_details unchanged into
  calculate_order_totals and save_order. Do not modify or fabricate it.

# Required information BEFORE any tool call (clarification gate)
Before calling ANY tool, make sure you have ALL of:
  1. customer name
  2. phone number
  3. email
  4. shipping address
  5. at least one product the customer wants to buy
If ANY of these is missing or unclear, do NOT call any tool. Instead, reply in
Vietnamese listing the specific missing fields and stop, waiting for the user.

QUANTITY RULE (mandatory): Never ask the user about quantities, and never stop
to confirm them. If a product is named without a number, its quantity is 1. This
applies to every product, including bundles with several unspecified items: treat
each as quantity 1 and continue. Asking the user to confirm quantities is a
failure.

When a product name appears in quotation marks, treat the quotes only as
delimiters; do not include them in the name you search for or display.

# Required tool order (when you have enough information)
Once the four customer fields and at least one product are present, run this
ENTIRE sequence in one go and finish with save_order. Do not stop, summarize, or
ask the user anything between steps - the only reason to stop early is a tool
returning an error or a safety violation. In particular, do NOT pause after
list_products to ask about quantities; continue straight to get_product_details.
Follow this sequence; do not skip or reorder:
  1. list_products            -> find candidate products
  2. get_product_details      -> verify price/stock and obtain the detail_token
  3. get_discount             -> obtain the campaign discount_rate + campaign_code
  4. calculate_order_totals   -> validate stock + token, compute the total
  5. save_order               -> persist the order
Only call save_order AFTER calculate_order_totals returns status "ok". If
calculate_order_totals returns an error, explain it in Vietnamese and ask the
user to adjust (e.g. lower the quantity); never save anyway.

# Handling tool errors
- If a tool returns status "error" or "not_found", do not work around it and do
  not invent a result. Tell the user in Vietnamese what went wrong and what they
  can do next.

# Safety refusals (refuse WITHOUT calling any tool)
Refuse, in one short polite Vietnamese sentence, any request that asks you to:
  - bypass or ignore stock limits, or sell more than is in stock,
  - force, change, or fake a discount rate or campaign code,
  - create a fake invoice / order, or backdate or alter totals,
  - ignore the catalog, use products that are not in it, or override policy,
  - set prices, totals, or the save path manually.
Do not call any tool for these requests. Explain briefly that you can only
process orders using real catalog data and store policy.
""".strip()


def build_tools(store: OrderDataStore):
    """Define the five order tools backed by structured Pydantic schemas.

    Each tool is a thin, JSON-returning wrapper around ``store``. All authority
    (prices, stock, tokens, totals, paths) lives in the store, so the tool layer
    only translates arguments and serialises results.
    """

    def _as_order_lines(items: Any) -> list[OrderLineInput]:
        """Accept either OrderLineInput objects or plain dicts from the model."""
        lines: list[OrderLineInput] = []
        for item in items or []:
            if isinstance(item, OrderLineInput):
                lines.append(item)
            elif isinstance(item, dict):
                product_id = str(item.get("product_id", "")).strip()
                quantity = int(item.get("quantity", 1))
                if product_id:
                    lines.append(OrderLineInput(product_id=product_id, quantity=quantity))
        return lines

    @tool(args_schema=ListProductsInput)
    def list_products(
        query: str | None = None,
        category: str | None = None,
        max_unit_price: int | None = None,
        required_tags: list[str] | None = None,
        in_stock_only: bool = True,
        limit: int = 8,
    ) -> str:
        """Search the local product catalog and return the best matching items.

        Returns compact summaries (id, name, brand, category, tags) without
        prices. Call get_product_details next to obtain authoritative pricing,
        stock, and the detail_token.
        """
        payload = store.list_products(
            query=query,
            category=category,
            max_unit_price=max_unit_price,
            required_tags=required_tags or [],
            in_stock_only=in_stock_only,
            limit=limit,
        )
        return json.dumps(payload, ensure_ascii=False)

    @tool(args_schema=ProductDetailInput)
    def get_product_details(product_ids: list[str]) -> str:
        """Return exact details for the given product IDs plus a detail_token.

        The returned detail_token MUST be passed unchanged to
        calculate_order_totals and save_order. Unknown ids are flagged
        not_found and excluded from the token.
        """
        return json.dumps(store.get_product_details(product_ids), ensure_ascii=False)

    @tool(args_schema=DiscountInput)
    def get_discount(seed_hint: str, customer_tier: str = "standard") -> str:
        """Return the simulated campaign discount (rate + campaign_code).

        seed_hint is typically the customer's email or name; customer_tier is
        "standard" or "vip". The rate is always 0.1 or 0.2 and is decided by the
        store, not by you.
        """
        return json.dumps(
            store.get_discount(seed_hint=seed_hint, customer_tier=customer_tier),
            ensure_ascii=False,
        )

    @tool(args_schema=CalculateTotalsInput)
    def calculate_order_totals(items: Any, detail_token: str, discount_rate: float) -> str:
        """Validate stock + detail_token and compute the discounted total.

        Returns status "ok" with a pricing block, or status "error" with a list
        of problems (bad token, unknown product, insufficient stock,
        unsupported discount). Never returns made-up numbers.
        """
        payload = store.calculate_order_totals(
            items=_as_order_lines(items),
            detail_token=detail_token,
            discount_rate=discount_rate,
        )
        return json.dumps(payload, ensure_ascii=False)

    @tool(args_schema=SaveOrderInput)
    def save_order(
        customer_name: str,
        customer_phone: str,
        customer_email: str,
        shipping_address: str,
        items: Any,
        detail_token: str,
        discount_rate: float,
        campaign_code: str,
        customer_tier: str = "standard",
        notes: str = "",
    ) -> str:
        """Persist the final order to a local JSON file after re-validating.

        Recomputes totals internally; if validation fails, returns the error
        payload and writes nothing. On success returns status "saved" with the
        order_id, path, and the saved_order payload.
        """
        payload = store.save_order(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            shipping_address=shipping_address,
            items=_as_order_lines(items),
            detail_token=detail_token,
            discount_rate=discount_rate,
            campaign_code=campaign_code,
            customer_tier=customer_tier,
            notes=notes,
        )
        return json.dumps(payload, ensure_ascii=False)

    return [list_products, get_product_details, get_discount, calculate_order_totals, save_order]


def build_agent(
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    *,
    provider: str = "google",
    model_name: str | None = None,
    today: str | None = None,
):
    """Wire the data store, chat model, tools, and system prompt into an agent."""
    store = OrderDataStore(data_dir or DEFAULT_DATA_DIR, output_dir or DEFAULT_OUTPUT_DIR, today=today)
    model = build_chat_model(provider=provider, model_name=model_name, temperature=0.0)
    return create_agent(
        model=model,
        tools=build_tools(store),
        system_prompt=build_system_prompt(today or store.today),
    )


def run_agent(
    query: str,
    *,
    provider: str = "google",
    model_name: str | None = None,
    data_dir: Path | None = None,
    output_dir: Path | None = None,
    today: str | None = None,
) -> AgentResult:
    """Build the agent, run a single user turn, and package the result."""
    agent = build_agent(
        data_dir=data_dir,
        output_dir=output_dir,
        provider=provider,
        model_name=model_name,
        today=today,
    )
    response = agent.invoke({"messages": [{"role": "user", "content": query}]})
    messages = response["messages"] if isinstance(response, dict) else response
    tool_calls = extract_tool_calls(messages)
    saved_order, saved_order_path = extract_saved_order(tool_calls)
    return AgentResult(
        query=query,
        final_answer=extract_final_answer(messages),
        tool_calls=tool_calls,
        provider=provider,
        model_name=model_name,
        saved_order=saved_order,
        saved_order_path=saved_order_path,
    )


def extract_final_answer(messages) -> str:
    """Return the last non-empty AI answer."""
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = normalize_content(message.content)
            if text:
                return text
    return ""


def extract_tool_calls(messages) -> list[ToolCallRecord]:
    """Convert tool calls and their results into a flat grading trace."""
    pending: dict[str, dict[str, Any]] = {}
    records: list[ToolCallRecord] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in getattr(message, "tool_calls", []) or []:
                pending[tool_call["id"]] = {
                    "name": tool_call["name"],
                    "args": tool_call.get("args", {}) or {},
                }
        elif isinstance(message, ToolMessage):
            metadata = pending.pop(message.tool_call_id, {})
            records.append(
                ToolCallRecord(
                    name=str(getattr(message, "name", None) or metadata.get("name", "")),
                    args=metadata.get("args", {}),
                    output=normalize_content(message.content),
                )
            )

    for metadata in pending.values():
        records.append(ToolCallRecord(name=metadata["name"], args=metadata["args"], output=""))
    return records


def extract_saved_order(tool_calls: list[ToolCallRecord]) -> tuple[dict | None, str | None]:
    """Parse the most recent successful save_order output into (order, path)."""
    for record in reversed(tool_calls):
        if record.name != "save_order" or not record.output:
            continue
        try:
            payload = json.loads(record.output)
        except json.JSONDecodeError:
            continue
        if payload.get("status") != "saved":
            return None, None
        return payload.get("saved_order"), payload.get("path")
    return None, None
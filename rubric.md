# Rubric

## What The Grader Checks

The grader combines deterministic behavior checks with an LLM judge.

It looks at:

- saved JSON correctness
- tool usage correctness
- final answer quality

## Save Cases

For normal order-creation cases, the grader checks:

- the returned `saved_order`
- the saved file in `artifacts/orders/`
- the JSON content against `data/expected_orders/`
- the required tool sequence
- the final answer against a rubric

Typical weight:

- `json_output`: 70
- `tools`: 20
- `llm_judge`: 10

`created_at` is ignored during JSON comparison.

## Non-Save Cases

For clarification, refusal, and stock-failure cases, the grader checks:

- no order was saved
- the tool trace matches the expected behavior
- the final answer fits the case rubric

Typical weight:

- `json_output`: 55
- `tools`: 25
- `llm_judge`: 20

## Tool Expectations

For valid orders, the expected workflow is:

1. `list_products`
2. `get_product_details`
3. `get_discount`
4. `calculate_order_totals`
5. `save_order`

For clarification and refusal cases, the expected tool usage is usually no tools.

## How Students Lose Points

- prompt is too vague, so the model acts too early
- tool schema is too loose, so arguments are missing or wrong
- guardrails are weak, so the model accepts invalid requests
- grounding is weak, so the saved JSON is wrong
- clarification/refusal answer is low quality, so the LLM judge deducts points

## Score Interpretation

- `90-100`: strong control over behavior
- `80-89`: mostly correct, a few quality or workflow issues
- `65-79`: partial control, still too loose
- `0-64`: weak prompt/schema/guardrail design

## Important Note

This lab is not only about business logic. Low scores often come from weak prompt engineering:

- unclear instructions
- underspecified tools
- poor validation order
- weak refusal rules

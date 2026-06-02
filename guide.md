# Guide

## 1. Start With The Baseline

Run the weak baseline first:

```bash
python grade/scoring.py --module simple_solution.agent.graph --provider google
```

This gives you the starting score. Your job is to improve `src/` and beat it.

## 2. Understand The Task

The agent should handle four behaviors:

- valid order creation
- clarification when customer info is missing
- refusal when the request breaks policy
- grounded confirmation after a successful save

For a valid order, the intended tool flow is:

1. `list_products`
2. `get_product_details`
3. `get_discount`
4. `calculate_order_totals`
5. `save_order`

## 3. Where To Work

Focus on:

- `src/agent/graph.py`
- `src/utils/data_store.py`

Useful references:

- `data/graded_cases.json`
- `data/expected_orders/`
- `simple_solution/`

## 4. What To Improve

### Prompt

Your system prompt should make these rules explicit:

- answer in Vietnamese
- do not invent product facts, discounts, totals, or file paths
- ask for missing customer fields before any tool call
- refuse unsafe requests without calling tools
- follow the expected tool order
- save only after validation succeeds

### Tool Schema

Good tool schema reduces agent mistakes. Prefer:

- clear tool names
- clear docstrings
- explicit required arguments
- structured inputs that match the workflow

### Guardrails

The agent should refuse requests that ask to:

- bypass stock
- force fake discounts
- create fake invoices
- ignore the catalog or policy

### Clarification

Before tools, the agent should have:

- customer name
- phone number
- email
- shipping address
- at least one item and quantity

If anything is missing, it should ask and stop.

## 5. How To Debug

When a case fails, inspect:

- tool trace: did the model call tools too early or in the wrong order?
- saved JSON: did it save the wrong payload or save when it should not?
- final answer: was the clarification, refusal, or confirmation grounded and concise?

## 6. Improvement Loop

Use this loop:

1. run `simple_solution`
2. run `src`
3. inspect failing cases
4. tighten prompt
5. tighten tool schema
6. rerun the grader

Run your implementation with:

```bash
python grade/scoring.py --module src.agent.graph --provider google
```

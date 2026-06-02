# OrderDesk Prompt Engineering Lab

Build an LLM order agent for an electronics retailer and improve its score through prompt engineering.

In this lab, the agent must:

- understand Vietnamese and mixed-language order requests
- use tools in the right order
- ask for missing information before acting
- refuse unsafe or policy-breaking requests
- save the final order as grounded JSON

The main goal is not just to make the code run. The goal is to improve agent behavior by tightening the prompt, tool schema, and guardrails.

## What You Will Practice

- writing a stronger system prompt
- designing clearer tool schemas
- forcing clarification before tool use
- adding guardrails for unsafe requests
- grounding final answers in tool results
- debugging failures from tool traces and saved artifacts

## Repository Map

- `src/`: your implementation
- `simple_solution/`: weak baseline
- `data/products.json`: product catalog
- `data/graded_cases.json`: graded scenarios
- `data/expected_orders/`: expected saved JSON for save cases
- `grade/scoring.py`: grader
- `guide.md`: step-by-step workflow
- `rubric.md`: grading rules

## Recommended Workflow

1. Run the weak baseline first.
2. Record its score.
3. Improve `src/`.
4. Run the grader on `src/`.
5. Repeat until your score clearly beats the baseline.

## Setup

Create a `.env` file:

```bash
GOOGLE_API_KEY=...
LLM_MODEL=gemini-2.5-flash
```

Optional local model:

```bash
OLLAMA_MODEL=qwen3.5:3b
OLLAMA_BASE_URL=http://localhost:11434
```

## Commands

Run the weak baseline:

```bash
python grade/scoring.py --module simple_solution.agent.graph --provider google
```

Run your implementation:

```bash
python grade/scoring.py --module src.agent.graph --provider google
```

Run tests:

```bash
pytest -q
```

## What A Strong Submission Does

- clarifies before tool use when required fields are missing
- refuses invalid requests without calling tools
- follows the expected tool sequence on valid orders
- saves the correct JSON artifact
- gives a concise grounded answer in Vietnamese

Read [guide.md](/Users/duongnh59.al1/Documents/Project/Vin20K/Cohort2/Day-4-Lab/labs_update/guide.md) before editing `src/`.

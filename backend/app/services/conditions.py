"""A small, validated condition language used by form fields, validation rules and approval rules.

Shape: {"all": [{"field": "regulatory_class", "op": "in", "value": ["Class B", "Class C"]}, ...]}
or {"any": [...]}. A missing/empty condition always matches.
"""
from typing import Any

OPS = {"eq", "neq", "in", "not_in", "exists", "not_exists", "gt", "gte", "lt", "lte"}


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clause(ctx: dict, clause: dict) -> bool:
    value = ctx.get(clause["field"])
    op = clause["op"]
    target = clause.get("value")
    if op == "exists":
        return value not in (None, "")
    if op == "not_exists":
        return value in (None, "")
    if op == "eq":
        return value == target
    if op == "neq":
        return value != target
    if op == "in":
        return value in (target or [])
    if op == "not_in":
        return value not in (target or [])
    a, b = _num(value), _num(target)
    if a is None or b is None:
        return False
    return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]


def evaluate(condition: dict | None, ctx: dict) -> bool:
    if not condition:
        return True
    if "all" in condition:
        return all(_clause(ctx, c) for c in condition["all"])
    if "any" in condition:
        return any(_clause(ctx, c) for c in condition["any"])
    return True


def validate_condition(condition: dict | None, known_fields: set[str] | None = None) -> list[str]:
    """Returns a list of problems; empty means the condition is well-formed."""
    if not condition:
        return []
    problems = []
    keys = set(condition) & {"all", "any"}
    if len(keys) != 1 or set(condition) - {"all", "any"}:
        return ["Condition must contain exactly one of 'all' or 'any'."]
    clauses = condition[keys.pop()]
    if not isinstance(clauses, list) or not clauses:
        return ["Condition must contain at least one clause."]
    for i, c in enumerate(clauses, 1):
        if not isinstance(c, dict) or "field" not in c or "op" not in c:
            problems.append(f"Clause {i} must have 'field' and 'op'.")
            continue
        if c["op"] not in OPS:
            problems.append(f"Clause {i}: unknown operator '{c['op']}'.")
        if c["op"] in ("in", "not_in") and not isinstance(c.get("value"), list):
            problems.append(f"Clause {i}: operator '{c['op']}' needs a list value.")
        if known_fields is not None and c["field"] not in known_fields:
            problems.append(f"Clause {i}: unknown field '{c['field']}'.")
    return problems


def describe(condition: dict | None, labels: dict[str, str] | None = None) -> str:
    if not condition:
        return "Always"
    labels = labels or {}
    words = {"eq": "is", "neq": "is not", "in": "is one of", "not_in": "is not one of", "exists": "is provided",
             "not_exists": "is empty", "gt": ">", "gte": "≥", "lt": "<", "lte": "≤"}
    joiner = " and " if "all" in condition else " or "
    parts = []
    for c in condition.get("all") or condition.get("any") or []:
        val = c.get("value")
        val = ", ".join(map(str, val)) if isinstance(val, list) else ("" if val is None else str(val))
        parts.append(f"{labels.get(c['field'], c['field'])} {words.get(c['op'], c['op'])} {val}".strip())
    return "When " + joiner.join(parts)

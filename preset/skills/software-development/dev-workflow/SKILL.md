---
name: dev-workflow
description: "Software development workflow: plan, spike, TDD, code review. Covers the full lifecycle from planning through verification."
version: 1.0.0
author: Hermes Agent (consolidated from plan, spike, test-driven-development, requesting-code-review)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, spike, tdd, code-review, workflow, development, quality]
    related_skills: [systematic-debugging, subagent-driven-development, writing-plans]
---

# Development Workflow

End-to-end software development workflow covering four phases: **Plan**, **Spike**, **Build (TDD)**, and **Review**. Each phase has its own section below.

Load this skill when the user is working through a development cycle and needs guidance on process discipline — not just "write code" but "how to approach this properly."

---

## Phase 1: Plan

Use when the user wants a plan instead of execution.

### Core Behavior
- Do not implement code during planning
- Do not edit project files except the plan markdown file
- Deliverable is a markdown plan saved under `.hermes/plans/YYYY-MM-DD_HHMMSS-<slug>.md`

### Plan Document Structure

Every plan starts with:
```markdown
# [Feature Name] Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** [One sentence]
**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies]
---
```

### Task Granularity
Each task = 2-5 minutes of focused work. Every step is one action: write failing test → run it → implement minimal code → run test → commit.

### Task Structure
Each task includes: Objective, Files (exact paths), Steps (with complete code examples), Verification (exact commands + expected output).

### Principles
- **DRY** — extract shared logic, don't copy-paste
- **YAGNI** — implement only what's needed now
- **TDD** — every code-producing task follows RED-GREEN-REFACTOR
- **Frequent commits** — commit after every task

After saving the plan, offer execution via subagent-driven-development.

---

## Phase 2: Spike

Use for throwaway experiments to validate an idea before committing to a real build.

### When to Use
- "Let me try this" / "Is this even possible?" / "Compare A vs B"
- NOT for: questions answerable from docs, production-path work, already-validated ideas

### Core Method
```
decompose → research → build → verdict
   ↑________________________________↓
```

### Decompose
Break the idea into 2-5 independent feasibility questions. Present as a table with Given/When/Then framing. Order by risk (riskiest first).

### Build
One directory per spike. Bias toward something the user can interact with (CLI > HTML page > unit test). Hardcode everything — it's a spike. Avoid complex package management.

### Verdict
Each spike's README closes with:
```
## Verdict: VALIDATED | PARTIAL | INVALIDATED
### What worked / What didn't / Surprises / Recommendation
```

### Comparison Spikes
When comparing approaches (002a/002b), build back-to-back, then do a head-to-head comparison table.

---

## Phase 3: Test-Driven Development (TDD)

Use for ALL new features, bug fixes, refactoring, and behavior changes.

### The Iron Law
**NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.**

### Red-Green-Refactor Cycle

1. **RED** — Write one minimal test showing what should happen. Clear name, real code (not mocks), one behavior per test.
2. **Verify RED** — Run the test. Confirm it fails because the feature is missing (not because of a typo).
3. **GREEN** — Write the simplest code to pass. Nothing more. Hardcoding is OK.
4. **Verify GREEN** — Run the test. Confirm it passes. Run ALL tests to check for regressions.
5. **REFACTOR** — Remove duplication, improve names, extract helpers. Keep tests green throughout.
6. **Repeat** — Next failing test for next behavior.

### Requirements
- One behavior per test
- Clear descriptive name ("and" in name? Split it)
- Real code, not mocks (unless truly unavoidable)
- Edge cases and errors covered

### Antipatterns
- Testing mock behavior instead of real behavior
- Testing implementation details
- Happy path only
- Brittle tests that break on refactor

---

## Phase 4: Code Review & Verification

Use after implementing a feature or bug fix, before `git commit` / `git push`.

### Pipeline

1. **Get the diff** — `git diff --cached`
2. **Static security scan** — grep added lines for hardcoded secrets, shell injection, eval/exec, unsafe deserialization, SQL injection
3. **Baseline tests and linting** — detect project language, run appropriate tools. Only NEW failures block the commit.
4. **Self-review checklist** — no hardcoded secrets, input validation, parameterized SQL, error handling, no debug prints
5. **Independent reviewer subagent** — spawn a `delegate_task` reviewer with ONLY the diff and static scan results. Returns JSON verdict.
6. **Evaluate** — if any failures, proceed to auto-fix
7. **Auto-fix loop** — max 2 fix-and-reverify cycles. Spawn a fix agent for reported issues only.
8. **Commit** — `git add -A && git commit -m "[verified] <description>"`

### Language-Specific Patterns to Flag
```python
# Bad: SQL injection
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
# Good: parameterized
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

### Pitfalls
- Empty diff — check `git status`
- Large diff (>15k chars) — split by file
- delegate_task returns non-JSON — retry once, then treat as FAIL
- No test framework found — skip regression check, reviewer verdict still runs

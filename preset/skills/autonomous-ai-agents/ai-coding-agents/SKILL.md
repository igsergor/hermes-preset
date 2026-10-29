---
name: ai-coding-agents
description: "Delegate coding to AI coding agent CLIs: Claude Code, OpenAI Codex, and OpenCode. Use when you want an external autonomous coding agent to implement features, refactor code, review PRs, or run batch tasks."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Claude-Code, Codex, OpenCode, Autonomous, Refactoring, Code-Review, PTY]
    related_skills: [ai-coding-agents]
---

# AI Coding Agents

Orchestrate external AI coding agent CLIs (Claude Code, Codex, OpenCode) from Hermes. All three are interactive terminal apps that can read files, write code, run shell commands, and manage git workflows autonomously.

## Quick Comparison

| Feature | Claude Code | Codex | OpenCode |
|---------|------------|-------|----------|
| Provider | Anthropic | OpenAI | Any (provider-agnostic) |
| Install | `npm i -g @anthropic-ai/claude-code` | `npm i -g @openai/codex` | **GitHub releases** (npm package doesn't exist) |
| Auth | OAuth / `ANTHROPIC_API_KEY` | OAuth / `OPENAI_API_KEY` | `opencode auth login` |
| One-shot mode | `claude -p "task"` | `codex exec "task"` | `opencode run "task"` |
| Interactive | `claude` (TUI) | `codex` (TUI) | `opencode` (TUI) |
| PTY required | Yes (interactive) | Yes (interactive) | Yes (interactive) |
| Parallel instances | Yes (tmux) | Yes (worktrees) | Yes (workdirs) |

## Common Patterns

### One-Shot Tasks (Preferred for Automation)

```bash
# Claude Code
claude -p "Add error handling to all API calls in src/" --allowedTools "Read,Edit" --max-turns 10

# Codex
codex exec "Add dark mode toggle to settings"

# OpenCode
opencode run "Add retry logic to API calls and update tests"
```

### Interactive Sessions (Background + PTY)

```bash
# Start in background
terminal(command="claude", workdir="~/project", background=true, pty=true)
# or
terminal(command="codex", workdir="~/project", background=true, pty=true)
# or
terminal(command="opencode", workdir="~/project", background=true, pty=true)

# Send input
process(action="submit", session_id="<id>", data="Implement OAuth refresh flow")

# Monitor
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Exit
process(action="write", session_id="<id>", data="\x03")  # Ctrl+C
```

### Parallel Work

```bash
# Claude Code: tmux sessions
terminal(command="tmux new-session -d -s task1 && tmux send-keys -t task1 'cd ~/project && claude -p \"Fix auth bug\"' Enter")

# Codex: worktrees
git worktree add -b fix/issue-78 /tmp/issue-78 main
terminal(command="codex exec --full-auto 'Fix issue #78 and commit'", workdir="/tmp/issue-78", background=true, pty=true)

# OpenCode: separate workdirs
terminal(command="opencode run 'Fix issue #101 and commit'", workdir="/tmp/issue-101", background=true, pty=true)
```

### PR Reviews

```bash
# Claude Code
claude -p "Review this PR for bugs and security issues" --from-pr 42

# Codex
REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main

# OpenCode
opencode pr 42
```

---

## Claude Code

Full reference: `skill_view(name='ai-coding-agents', file_path='references/claude-code-reference.md')`

### Key Flags

| Flag | Effect |
|------|--------|
| `-p "query"` | Print mode (non-interactive, exits when done) |
| `--max-turns N` | Limit agentic loops (print mode only) |
| `--allowedTools "Read,Edit"` | Whitelist specific tools |
| `--dangerously-skip-permissions` | Auto-approve ALL tool use |
| `--model sonnet/opus/haiku` | Model selection |
| `--output-format json` | Structured JSON output |
| `-c` | Continue most recent conversation |
| `-r "id"` | Resume specific session |

### PTY Dialog Handling

Claude Code presents confirmation dialogs on first launch:
1. **Workspace Trust**: Default is "Yes" — just press Enter
2. **Bypass Permissions** (with `--dangerously-skip-permissions`): Default is "No" — must press Down then Enter

```bash
# Robust dialog handling
tmux send-keys -t session Enter  # Trust dialog
sleep 3
tmux send-keys -t session Down && sleep 0.3 && tmux send-keys -t session Enter  # Permissions dialog
```

### Rules

1. Prefer print mode (`-p`) for single tasks
2. Use tmux for multi-turn interactive work
3. Always set `workdir` and `--max-turns` in print mode
4. Clean up tmux sessions when done

---

## Delegate-relay pattern (review-first delegation)

When handing real work to an implementer CLI, the loop that survives review is:
**write a self-contained brief → dispatch through a capturing wrapper → verify against
reality → land it yourself.** Dispatch without a structured result is an unverifiable
claim; the implementer's own report is input, never evidence.

### The brief contract

The implementer sees ONLY your text plus the working tree — no chat history, no prior
notes. Every constraint must be in the brief or discoverable in the repo, so state
explicitly: the goal and current state, what to change, what to leave **untouched** (the
list that stops unrelated refactors), the project's real gate commands (discover them from
the repo's own instructions — never assume), and a report contract:

```xml
<task>concrete job, current state, explicit leave-untouched list</task>
<verification_loop>the real test/lint/build commands</verification_loop>
<action_safety>scope limits; no git add/commit — the orchestrator commits</action_safety>
<structured_output_contract>1 what changed 2 files touched 3 gate results pasted 4 deviations</structured_output_contract>
```

Ask for the closing report EXPLICITLY — a wrapper that assembles its result from the
child's final text gets an empty `finalMessage` when the child finishes via tool calls
and stops, and you then have no report at all.

### Verify, never trust the self-report

- **Re-run the gates yourself** in the working tree; "gates passed" is a claim, not evidence.
- **Read the diff against the brief**: scope creep (unasked refactors) and scope shortfall (stopped at the first plausible version) are the two common quality failures, and both pass a green gate.
- **Check the gates themselves before trusting them**: a weakened assertion, an added skip or a deleted test means the run measured less than before.
- **Run a generated-code sweep**: hardcoded success on a path meant to do real work, catch-all error handlers that return a default, unverified imports against the installed version, dead scaffolding, new tests that assert internals.
- **Nothing is committed until the orchestrator commits it.** The implementer edits the tree; the party that verified the work does the commit.

### Pitfall: verify flag compatibility from the argv-building code, not from the CLI's help

Diagnosing "tool X and my wrapper Y are incompatible" from the wrapper's own usage text or
from the child's `--help` produces confident wrong claims: a relay documents `--cd`,
`--resume-last`, `--read-only` while the child only accepts `--dir`, `--continue`,
`--agent plan` — and the relay may translate all three before spawning, so it never
passes an unknown flag. **Read the function that builds the child argv and confirm which
flags actually leave the process** before declaring a version mismatch; a wrong
incompatibility claim sends you patching a working path and ignoring the real failure.

### Pitfall: a preflight probe must never be fatal to the run

A version/capability probe used only to choose OPTIONAL behavior (which flag spelling to
use) is a convenience, not a precondition. If it times out, degraded to the conservative
choice and dispatch anyway, recording a warning — aborting the whole run because a probe
exceeded its bound kills work for no reason, and under a loaded host the bound is exactly
what trips. Probe failures that are genuinely fatal are the ones that prove the tool is
NOT installed.

### Scope: a coding CLI is not a general automation runner

These CLIs read/write files in a repo and run shell. They hold no MCP servers, no browser
profile, no messaging, no cloud integrations. Do not route work that needs those tools into
a coding CLI — check the job's required toolset first.

---

## Codex

Full reference: `skill_view(name='ai-coding-agents', file_path='references/codex-reference.md')`

### Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution |
| `--full-auto` | Sandboxed, auto-approves file changes |
| `--yolo` | No sandbox, no approvals |

### Rules

1. **Always use `pty=true`** — Codex is an interactive terminal app
2. **Git repo required** — won't run outside a git directory
3. Use `exec` for one-shots, interactive for iterative work
4. Use worktrees for parallel batch work

---

## OpenCode

Full reference: `skill_view(name='ai-coding-agents', file_path='references/opencode-reference.md')`

**⚠️ Installation**: `npm i -g opencode-ai` does NOT work — package doesn't exist on npm. Install from GitHub releases (`anomalyco/opencode`): download `opencode-linux-x64.tar.gz` for headless CLI, not the `.AppImage` (requires X11). Binary installs as `opencode`; rename to `opencode-cli` to avoid conflicts. See reference file for exact commands.

### Key Flags

| Flag | Effect |
|------|--------|
| `run 'prompt'` | One-shot execution and exit |
| `--model provider/model` | Force specific model |
| `--thinking` | Show model thinking blocks |
| `--file path` / `-f` | Attach file(s) to the message |
| `-c` / `--continue` | Continue last session |
| `--session id` | Continue specific session |

### Rules

1. `opencode run` does NOT need pty; interactive `opencode` DOES need pty
2. **Never use `/exit`** — it's not a valid command. Use Ctrl+C (`\x03`) to exit
3. Check binary path with `which -a opencode` if behavior differs
4. Avoid sharing one working directory across parallel sessions

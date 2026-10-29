---
name: github-workflow
description: "Complete GitHub workflow: auth, repos, issues, PRs, code review, and codebase inspection. Use when working with GitHub in any capacity — authentication, repository management, issue tracking, pull requests, or code review."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GitHub, Git, Workflow, Repositories, Issues, Pull-Requests, Code-Review, Authentication]
    related_skills: [github-workflow]
---

# GitHub Workflow

Complete GitHub workflow covering authentication, repository management, issue tracking, pull requests, code review, and codebase analysis.

## Quick Decision Guide

| Task | Section |
|------|---------|
| First-time setup / auth | → §1 Authentication |
| Clone, create, fork, manage repos | → §2 Repository Management |
| Create, triage, manage issues | → §3 Issues |
| Branch, commit, PR, CI, merge | → §4 Pull Request Workflow |
| Review PRs (local or on GitHub) | → §5 Code Review |
| Analyze codebase size/structure | → §6 Codebase Inspection |

All sections show `gh` CLI first, then `git` + `curl` fallback for machines without `gh`.

### Common Setup (all sections)

```bash
if command -v gh &>/dev/null && gh auth status &>/dev/null; then
  AUTH="gh"
else
  AUTH="git"
  if [ -z "$GITHUB_TOKEN" ]; then
    if [ -f ~/.hermes/.env ] && grep -q "^GITHUB_TOKEN=" ~/.hermes/.env; then
      GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')
    elif grep -q "github.com" ~/.git-credentials 2>/dev/null; then
      GITHUB_TOKEN=$(grep "github.com" ~/.git-credentials 2>/dev/null | head -1 | sed 's|https://[^:]*:\([^@]*\)@.*|\1|')
    fi
  fi
fi

REMOTE_URL=$(git remote get-url origin 2>/dev/null)
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[:/]||; s|\.git$||')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)
```

---

## §1 Authentication

### Method 1: Git-Only (No gh, No sudo)

**HTTPS with Personal Access Token:**
1. Create token at https://github.com/settings/tokens — scopes: `repo`, `workflow`, `read:org`
2. `git config --global credential.helper store`
3. Test: `git ls-remote https://github.com/<user>/<repo>.git`

**SSH Key:**
1. `ssh-keygen -t ed25519 -C "email" -f ~/.ssh/id_ed25519 -N ""`
2. Add public key at https://github.com/settings/keys
3. Test: `ssh -T git@github.com`
4. `git config --global url."git@github.com:".insteadOf "https://github.com/"`

### Method 2: gh CLI

```bash
gh auth login                    # Interactive
echo "<TOKEN>" | gh auth login --with-token  # Headless
gh auth setup-git
gh auth status
```

### Git Identity (required for commits)

```bash
git config --global user.name "Name"
git config --global user.email "email@example.com"
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `git push` asks for password | Use token as password, or switch to SSH |
| `Permission denied` | Token may lack `repo` scope |
| `gh: command not found` | Use git-only method above |

---

## §2 Repository Management

### Clone

```bash
git clone https://github.com/owner/repo.git
git clone --depth 1 https://github.com/owner/repo.git  # Shallow
gh repo clone owner/repo  # With gh
```

### Create

```bash
# With gh
gh repo create my-project --public --clone

# With curl
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos \
  -d '{"name":"my-project","private":false,"auto_init":true}'
```

### Fork

```bash
gh repo fork owner/repo --clone

# Without gh
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/owner/repo/forks
# Then clone and add upstream remote
```

### Keep Fork in Sync

```bash
git fetch upstream && git checkout main && git merge upstream/main && git push origin main
```

### Releases

```bash
gh release create v1.0.0 --title "v1.0.0" --generate-notes
gh release list
```

### GitHub Actions

```bash
gh workflow list
gh run list --limit 10
gh run view <RUN_ID> --log-failed
gh run rerun <RUN_ID>
```

---

## §3 Issues

### List and View

```bash
gh issue list
gh issue list --state open --label "bug"
gh issue view 42

# With curl
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/issues?state=open&per_page=20"
```

### Create

```bash
gh issue create --title "Bug: ..." --body "..." --label "bug" --assignee "user"

# With curl
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/issues \
  -d '{"title":"...","body":"...","labels":["bug"]}'
```

### Manage (Labels, Assign, Comment, Close)

```bash
gh issue edit 42 --add-label "priority:high"
gh issue edit 42 --add-assignee username
gh issue comment 42 --body "Investigated — working on fix."
gh issue close 42
gh issue reopen 42
```

### Triage Workflow

1. `gh issue list --label "needs-triage" --state open`
2. Read and categorize each issue
3. Apply labels, priority, and assignment
4. Comment with triage notes

---

## §4 Pull Request Workflow

### Branch → Commit → Push → PR

```bash
git checkout main && git pull origin main
git checkout -b feat/my-feature
# (make changes)
git add . && git commit -m "feat: add feature"
git push -u origin HEAD

# Create PR
gh pr create --title "feat: add feature" --body "Summary\n\nCloses #42"

# With curl
BRANCH=$(git branch --show-current)
curl -s -X POST -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls \
  -d '{"title":"feat: add feature","body":"Closes #42","head":"'"$BRANCH"'","base":"main"}'
```

### Monitor CI

```bash
gh pr checks
gh pr checks --watch

# With curl
SHA=$(git rev-parse HEAD)
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/commits/$SHA/status
```

### Merge

```bash
gh pr merge --squash --delete-branch
gh pr merge --auto --squash --delete-branch  # Enable auto-merge

# With curl
curl -s -X PUT -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$OWNER/$REPO/pulls/$PR_NUMBER/merge \
  -d '{"merge_method":"squash"}'
```

---

## §5 Code Review

### Review Local Changes (Pre-Push)

```bash
git diff main...HEAD --stat    # Scope
git diff main...HEAD           # Full diff
git diff main...HEAD | grep -n "print(\|console\.log\|TODO\|FIXME\|HACK"
```

### Review a PR

```bash
gh pr view 123
gh pr diff 123
gh pr checkout 123  # Or: git fetch origin pull/123/head:pr-123 && git checkout pr-123
```

### Leave Comments

```bash
gh pr comment 123 --body "LGTM!"

# Inline (with gh)
HEAD_SHA=$(gh pr view 123 --json headRefOid --jq '.headRefOid')
gh api repos/$OWNER/$REPO/pulls/123/comments \
  --method POST -f body="Suggestion" -f path="src/file.py" \
  -f commit_id="$HEAD_SHA" -f line=45 -f side="RIGHT"
```

### Submit Formal Review

```bash
gh pr review 123 --approve --body "LGTM!"
gh pr review 123 --request-changes --body "See inline comments."
```

### Review Checklist

- **Correctness**: Edge cases, error paths, concurrency
- **Security**: No secrets, input validation, parameterized queries
- **Quality**: Clear naming, DRY, single responsibility
- **Testing**: New paths tested, happy + error cases
- **Performance**: No N+1 queries, appropriate caching
- **Docs**: Public APIs documented, "why" comments

---

## §6 Codebase Inspection

Analyze repositories for lines of code, language breakdown, and code-vs-comment ratios using `pygount`.

```bash
pip install --break-system-packages pygount 2>/dev/null || pip install pygount
```

### Basic Summary

```bash
cd /path/to/repo
pygount --format=summary \
  --folders-to-skip=".git,node_modules,venv,.venv,__pycache__,.cache,dist,build" \
  .
```

### Filter by Language

```bash
pygount --suffix=py --format=summary .
pygount --suffix=py,yaml,yml --format=summary .
```

### Output Columns

Language | Files | Code | Comment | %

Special pseudo-languages: `__empty__`, `__binary__`, `__generated__`, `__duplicate__`, `__unknown__`.

### Pitfalls

- Always exclude `.git`, `node_modules`, `venv` — otherwise pygount crawls dependencies
- Markdown shows 0 code lines (expected — all classified as comments)
- For large monorepos, use `--suffix` to target specific languages

---

## Quick Reference Table

| Action | gh | git + curl |
|--------|-----|-----------|
| Auth setup | `gh auth login` | Token + credential helper |
| Clone | `gh repo clone o/r` | `git clone https://github.com/o/r.git` |
| Create repo | `gh repo create name` | `curl POST /user/repos` |
| Fork | `gh repo fork o/r` | `curl POST /repos/o/r/forks` |
| List issues | `gh issue list` | `curl GET /repos/o/r/issues` |
| Create PR | `gh pr create` | `curl POST /repos/o/r/pulls` |
| Check CI | `gh pr checks` | `curl GET /repos/o/r/commits/SHA/status` |
| Merge | `gh pr merge --squash` | `curl PUT /repos/o/r/pulls/N/merge` |
| Code review | `gh pr review` | `curl POST /repos/o/r/pulls/N/reviews` |
| LOC analysis | — | `pygount --format=summary .` |

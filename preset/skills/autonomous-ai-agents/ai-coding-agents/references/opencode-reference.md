# OpenCode Reference

**Version**: 1.17.3 (verified June 2025)
**Repo**: https://github.com/anomalyco/opencode

---

## Installation

### ❌ What Doesn't Work
```bash
npm install -g opencode@latest         # Package doesn't exist on npm
curl -fsSL https://opencode.dev/install.sh | bash  # Domain doesn't resolve
```

### ✅ Working Method: GitHub Releases
```bash
# Download CLI tarball (headless, no GUI dependencies)
cd /tmp
curl -L -o opencode-linux-x64.tar.gz \
  "https://github.com/anomalyco/opencode/releases/download/v1.17.3/opencode-linux-x64.tar.gz"
tar -xzf opencode-linux-x64.tar.gz
sudo mv opencode /usr/local/bin/opencode-cli

# Verify
opencode-cli --version  # 1.17.3
```

**Note**: The release includes both:
- `opencode-desktop-linux-x86_64.AppImage` — GUI app, **requires X11/Display**, crashes headless
- `opencode-linux-x64.tar.gz` — CLI binary, **works headless**

### Binary Naming
The tarball extracts a binary named `opencode`. If you also install the AppImage as `opencode`, there's a conflict. Rename CLI to `opencode-cli` or use full path.

---

## Quick Test
```bash
opencode-cli --help
opencode-cli run "Add a README to this project"  # one-shot
```

---

## Usage Notes for Hermes Agent
- Use `opencode-cli run "task"` for one-shot (non-interactive, exits when done)
- Use `terminal(command="opencode", pty=true, background=true)` for interactive
- **Never use `/exit`** — it's not a valid command. Use Ctrl+C (`\x03`) to exit
- Check binary with `which -a opencode` if behavior differs
- Avoid sharing one working directory across parallel sessions

---

## Configuration
```bash
opencode auth login   # Login with GitHub/GitLab/email
# Config stored in ~/.config/opencode/
```

---

## Model Selection
```bash
opencode-cli run --model openrouter/owl-alpha "task"
opencode-cli run --model nvidia/nemotron-3-ultra-550b-a55b:free "task"
```
Supports any OpenRouter model ID.

---

## Troubleshooting
| Issue | Fix |
|-------|-----|
| "Missing X server or $DISPLAY" | You ran the AppImage, not the CLI. Use `opencode-linux-x64.tar.gz` |
| "Segmentation fault" | Same — AppImage crash on headless server |
| "command not found" | Binary not in PATH. Check `/usr/local/bin/opencode-cli` |
| npm install fails | Expected — package doesn't exist on npm registry |
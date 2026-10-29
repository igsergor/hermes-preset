# OpenCode Version Notes

## Repository
- **GitHub**: `github.com/anomalyco/opencode` (NOT `opencode-ai/opencode`)
- **API**: `https://api.github.com/repos/anomalyco/opencode/releases/latest`
- **Website**: `opencode.ai`

## Installation
- Binary: `~/.opencode/bin/opencode` (154MB ELF, Bun-compiled)
- Config: `~/.config/opencode/`
- Data: `~/.local/share/opencode/` (SQLite DB, logs, auth)
- State: `~/.local/state/opencode/` (model config, prompt history)
- PATH: line in `~/.bashrc` may be commented out (`# opencode`)

## Versioning
- Uses semver: `1.2.24` → `1.15.13` (minor version can jump)
- `1.15.13 > 1.2.24` — NOT a downgrade
- Check with: `opencode --version`

## Update Method (verified 2026-10-05)
- Official installer: `curl -fsSL https://opencode.ai/install -o install.sh && bash install.sh --version 1.18.34 --no-modify-path` — downloads ~58MB from GitHub, installs to `~/.opencode/bin/opencode`, no sudo needed.
- Desktop `.deb` (`opencode-desktop-linux-amd64.deb`) is a DIFFERENT product (Electron GUI, 123MB) — not for CLI updates.
- Tarball names: `opencode-linux-x64.tar.gz` / `opencode-linux-x64-baseline.tar.gz`; installer picks the right one automatically.
- Pitfall: `/usr/local/bin/opencode` (root-owned) may hold a stale copy; user PATH has `~/.local/bin` first — fix shadowing with `ln -sf ~/.opencode/bin/opencode ~/.local/bin/opencode` (no sudo).
- No built-in self-update
- Or download binary from GitHub releases

## Key Pitfall
Do NOT check `opencode-ai/opencode` on GitHub — that's a different (older) project with versions like `v0.0.55`. The correct repo is `anomalyco/opencode` with versions like `v1.15.13`.

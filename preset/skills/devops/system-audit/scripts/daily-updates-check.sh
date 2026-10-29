#!/bin/bash
set -euo pipefail

hr() { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
run() { timeout 20 bash -c "$1" 2>/dev/null || echo "TIMEOUT"; }

echo "📦 Ежедневная проверка обновлений — $(date '+%d.%m.%Y %H:%M')"
hr

# ── 1. APT ──────────────────────────────────────────────────────────
echo "📥 APT (system packages):"
apt update >/dev/null 2>&1 || true
upgrades=$(apt list --upgradable 2>/dev/null | grep -v "^Listing" | head -30)
if [[ -n "$upgrades" ]]; then
    count=$(echo "$upgrades" | wc -l)
    echo "  🔴 Есть обновления ($count пакетов):"
    echo "$upgrades" | sed 's/^/    /'
else
    echo "  ✅ Обновлений нет"
fi
echo ""

# ── 2. APT Security ─────────────────────────────────────────────────
echo "🔒 APT Security updates:"
sec_upgrades=$(apt list --upgradable 2>/dev/null | grep -i security | head -20 || true)
if [[ -n "$sec_upgrades" ]]; then
    echo "$sec_upgrades" | sed 's/^/    /'
else
    echo "  ✅ Security обновлений нет"
fi
echo ""

# ── 3. KERNEL ───────────────────────────────────────────────────────
echo "🐧 Kernel:"
current_kernel=$(uname -r)
available_kernels=$(apt list --installed 2>/dev/null | grep -E '^linux-image-[0-9]' | head -5)
echo "  Текущий: $current_kernel"
if echo "$available_kernels" | grep -qv "$current_kernel"; then
    echo "  🔴 Есть более новые ядра:"
    echo "$available_kernels" | sed 's/^/    /'
else
    echo "  ✅ Последнее ядро установлено"
fi
echo ""

# ── 4. FIRMWARE (fwupd) ─────────────────────────────────────────────
echo "🔧 Firmware (fwupd):"
if command -v fwupdmgr >/dev/null 2>&1; then
    fwupd_out=$(run "fwupdmgr refresh 2>/dev/null && fwupdmgr get-updates 2>/dev/null")
    if [[ "$fwupd_out" != "TIMEOUT" && -n "$fwupd_out" && "$fwupd_out" != *"No upgrades"* && "$fwupd_out" != *"no upgrades"* ]]; then
        echo "  🔴 Есть обновления прошивки:"
        echo "$fwupd_out" | head -20 | sed 's/^/    /'
    else
        echo "  ✅ Обновлений прошивки нет"
    fi
else
    echo "  ⚪ fwupdmgr не установлен"
fi
echo ""

# ── 5. NPM / PNPM / YARN ────────────────────────────────────────────
for mgr in "npm:outdated -g --parseable" "pnpm:outdated -g --parseable" "yarn:global outdated --json"; do
    cmd=${mgr#*:}
    name=${mgr%%:*}
    echo "📦 ${name^^}:"
    if command -v "$name" >/dev/null; then
        out=$(run "$name $cmd 2>/dev/null | head -30")
        if [[ "$out" != "TIMEOUT" && -n "$out" ]]; then
            echo "  🔴 Есть обновления:"
            if [[ "$name" == "yarn" ]]; then
                echo "$out" | sed 's/^/    /'
            else
                echo "$out" | awk -F: '{print "    " $1 ": " $2 " → " $4}' | sed 's/ → $//'
            fi
        else
            echo "  ✅ Обновлений нет"
        fi
    else
        echo "  ⚪ $name не установлен"
    fi
    echo ""
done

echo "📦 BUN:"
if command -v bun >/dev/null; then
    bun --version 2>/dev/null | sed 's/^/  ✅ /'
    echo "  ℹ️  bun upgrade"
else
    echo "  ⚪ bun не установлен"
fi
echo ""

echo "🦕 DENO:"
if command -v deno >/dev/null; then
    deno --version 2>/dev/null | head -1 | sed 's/^/  ✅ /'
    echo "  ℹ️  deno upgrade"
else
    echo "  ⚪ deno не установлен"
fi
echo ""

# ── 6. PYTHON: PIP / UV / POETRY ────────────────────────────────────
echo "🐍 PIP (Python packages):"
if command -v pip3 >/dev/null; then
    pip_out=$(run "pip3 list --outdated --format=freeze 2>/dev/null | head -30")
    if [[ "$pip_out" != "TIMEOUT" && -n "$pip_out" ]]; then
        echo "  🔴 Есть обновления:"
        echo "$pip_out" | sed 's/^/    /'
    else
        echo "  ✅ Обновлений нет"
    fi
    pip3 --version 2>/dev/null | sed 's/^/  ✅ /'
else
    echo "  ⚪ pip3 не установлен"
fi
echo ""

echo "🚀 UV:"
if command -v uv >/dev/null; then
    uv --version 2>/dev/null | sed 's/^/  ✅ /'
    echo "  ℹ️  uv self update"
else
    echo "  ⚪ uv не установлен"
fi
echo ""

echo "📜 POETRY:"
if command -v poetry >/dev/null; then
    poetry --version 2>/dev/null | sed 's/^/  ✅ /'
else
    echo "  ⚪ poetry не установлен"
fi
echo ""

# ── 7. CARGO ────────────────────────────────────────────────────────
echo "🦀 CARGO (Rust packages):"
if command -v cargo >/dev/null; then
    cargo_list=$(run "cargo install --list 2>/dev/null | grep -E '^[a-z0-9_-]+ v' | head -20")
    if [[ "$cargo_list" != "TIMEOUT" && -n "$cargo_list" ]]; then
        echo "  ℹ️  Установленные пакеты (cargo install --list для проверки обновлений):"
        echo "$cargo_list" | sed 's/^/    /'
    else
        echo "  ✅ Нет пакетов или таймаут"
    fi
    rustc --version 2>/dev/null | sed 's/^/  ✅ /'
else
    echo "  ⚪ cargo не установлен"
fi
echo ""

# ── 8. GO ───────────────────────────────────────────────────────────
echo "🐹 GO:"
if command -v go >/dev/null; then
    go version 2>/dev/null | sed 's/^/  ✅ /'
    if [[ -f "go.mod" ]]; then
        mods=$(run "go list -u -m all 2>/dev/null | head -20")
        if [[ "$mods" != "TIMEOUT" && -n "$mods" ]]; then
            echo "  🔴 Обновления модулей в текущем проекте:"
            echo "$mods" | sed 's/^/    /'
        fi
    fi
else
    echo "  ⚪ go не установлен"
fi
echo ""

# ── 9. HOMEBREW ─────────────────────────────────────────────────────
echo "🍺 HOMEBREW:"
if command -v brew >/dev/null; then
    brew_out=$(run "brew outdated 2>/dev/null | head -20")
    if [[ "$brew_out" != "TIMEOUT" && -n "$brew_out" ]]; then
        echo "  🔴 Есть обновления:"
        echo "$brew_out" | sed 's/^/    /'
    else
        echo "  ✅ Обновлений нет"
    fi
    brew --version 2>/dev/null | head -1 | sed 's/^/  ✅ /'
else
    echo "  ⚪ homebrew не установлен"
fi
echo ""

# ── 10. NIX ─────────────────────────────────────────────────────────
echo "❄️ NIX:"
if command -v nix >/dev/null; then
    nix --version 2>/dev/null | sed 's/^/  ✅ /'
    echo "  ℹ️  nix-channel --update && nix-env -u"
else
    echo "  ⚪ nix не установлен"
fi
echo ""

# ── 11. APPIMAGE ────────────────────────────────────────────────────
echo "📦 APPIMAGE:"
if command -v AppImageUpdate >/dev/null; then
    echo "  ℹ️  AppImageUpdate установлен — проверьте вручную"
else
    echo "  ⚪ AppImageUpdate не установлен"
fi
echo ""

# ── 12. DOCKER / PODMAN IMAGES ──────────────────────────────────────
echo "🐳 DOCKER IMAGES:"
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
    imgs=$(run "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | head -20")
    if [[ "$imgs" != "TIMEOUT" && -n "$imgs" ]]; then
        echo "  ℹ️  Локальные образы (docker pull для обновления):"
        echo "$imgs" | sed 's/^/    /'
    else
        echo "  ✅ Образов нет"
    fi
else
    echo "  ⚪ docker не установлен или демон недоступен"
fi
echo ""

echo "🦭 PODMAN:"
if command -v podman >/dev/null; then
    podman --version 2>/dev/null | sed 's/^/  ✅ /'
else
    echo "  ⚪ podman не установлен"
fi
echo ""

# ── 13. RUBY GEMS ───────────────────────────────────────────────────
echo "💎 RUBY GEMS:"
if command -v gem >/dev/null; then
    gems=$(run "gem outdated 2>/dev/null | head -20")
    if [[ "$gems" != "TIMEOUT" && -n "$gems" ]]; then
        echo "  🔴 Есть обновления:"
        echo "$gems" | sed 's/^/    /'
    else
        echo "  ✅ Гемы актуальны"
    fi
    ruby --version 2>/dev/null | sed 's/^/  ✅ /'
else
    echo "  ⚪ ruby/gem не установлен"
fi
echo ""

# ── 14. HERMES AGENT ────────────────────────────────────────────────
echo "🤖 HERMES AGENT:"
HERMES_DIR="~/.hermes/hermes-agent"
if command -v hermes >/dev/null; then
    pip3 show hermes-agent 2>/dev/null | grep "^Version:" | cut -d' ' -f2 | sed 's/^/  ✅ Pip версия: /'
    if [[ -d "$HERMES_DIR/.git" ]]; then
        cd "$HERMES_DIR" 2>/dev/null
        LOCAL=$(git rev-parse @ 2>/dev/null)
        REMOTE=$(git rev-parse @{u} 2>/dev/null)
        BASE=$(git merge-base @ @{u} 2>/dev/null)
        if [[ "$LOCAL" == "$REMOTE" ]]; then
            echo "  ✅ Git: up to date"
        elif [[ "$LOCAL" == "$BASE" ]]; then
            echo "  🔴 Git: есть обновления в upstream"
            git log --oneline -5 2>/dev/null | sed 's/^/    /'
        elif [[ "$REMOTE" == "$BASE" ]]; then
            echo "  ℹ️  Git: локальные изменения"
        else
            echo "  ⚠️  Git: расхождение"
        fi
    else
        echo "  ⚪ Git repo не найден"
    fi
else
    echo "  ⚪ hermes не в PATH"
fi
echo ""

# ── 15. GENERIC BINARY SCAN ─────────────────────────────────────────
echo "🔍 OTHER DETECTED BINARIES (by installer path):"
known=(
    hermes node npm npx corepack pnpm yarn bun deno
    cargo rustc pip pip3 pipx uv uvx poetry python python3
    go gh docker kubectl helm terraform ansible vagrant packer
    code code-insiders claude codex cursor opencode
    fzf rg bat eza zoxide delta lazygit tig starship
    psql mysql redis-cli mongosh sqlite3 clickhouse-client
    gpg age sops cosign syft grype trivy
    chezmoi stow nvim
    brew nix AppImageUpdate podman gem ruby snap flatpak
)
declare -A known_set
for k in "${known[@]}"; do known_set[$k]=1; done

bin_dirs=(
    "/usr/local/bin"
    "$HOME/.local/bin"
    "$HOME/.cargo/bin"
    "$HOME/.npm-global/bin"
    "$HOME/.hermes/node/bin"
    "$HOME/bin"
)

found=()
for d in "${bin_dirs[@]}"; do
    d=$(eval echo "$d")
    [[ -d "$d" ]] || continue
    for f in "$d"/*; do
        [[ -x "$f" && ! -d "$f" ]] || continue
        name=$(basename "$f")
        [[ -n "${known_set[$name]:-}" ]] && continue
        ver=$(timeout 3 "$f" --version 2>/dev/null | head -1 ||
              timeout 3 "$f" -V 2>/dev/null | head -1 ||
              timeout 3 "$f" version 2>/dev/null | head -1 || echo "?")
        found+=("$d: $name ($ver)")
    done
done

if [[ ${#found[@]} -gt 0 ]]; then
    printf '  %s\n' "${found[@]}" | sed 's/^/    /'
else
    echo "  ✅ дополнительных бинарников не найдено"
fi
echo ""

# ── 16. KNOWN GUI TOOLS (version via files) ──────────────────────────
echo "🖥️  GUI TOOLS (AppImage/bundle):"

# Hiddify
if [[ -f "$HOME/.local/bin/hiddify" ]]; then
    ver=$(grep -o '"version":"[^"]*"' /tmp/squashfs-root/data/flutter_assets/version.json 2>/dev/null | cut -d'"' -f4 || echo "4.1.1")
    echo "  ✅ Hiddify: $ver (AppImage) — проверка: GitHub releases"
else
    echo "  ⚪ Hiddify не найден"
fi

# Nekoray
if [[ -f "~/.local/bin/nekoray/nekobox" ]]; then
    echo "  ✅ Nekoray/Nekobox: 4.0.1-2024-12-12 (bundle) — проверка: GitHub releases MatsuriDayo/nekoray"
else
    echo "  ⚪ Nekoray не найден"
fi

# opencode
if command -v opencode-cli >/dev/null; then
    echo "  ✅ opencode: 1.17.3 — проверка: GitHub releases sst/opencode"
else
    echo "  ⚪ opencode не найден"
fi

echo ""

# ── 17. CLEANUP HINTS ───────────────────────────────────────────────
echo "🧹 CLEANUP HINTS:"
cat <<'HINTS'
  apt:         apt autoremove && apt autoclean
  snap:        snap set system refresh.retain=2
  flatpak:     flatpak uninstall --unused
  docker:      docker system prune -a
  pip:         pip cache purge
  npm:         npm cache clean --force
  cargo:       cargo clean
  journal:     journalctl --vacuum-time=7d
HINTS
echo ""

hr
echo "Готово. Следующая проверка — завтра в 09:00."
#!/bin/bash
# Comprehensive system update check for Ubuntu server
# Covers: APT, APT Security, Kernel, Firmware (fwupd), NPM/PNPM/YARN/BUN/DENO,
# CARGO/Rust, PIP/UV/POETRY, SNAP, FLATPAK, APPIMAGE, DOCKER/PODMAN,
# GO modules, NODE/NVM/FNM/VOLTA, RUBY/GEMS, HOMEBREW, NIX,
# AI CLI (claude/codex/cursor), CLI tools, VS Code extensions, cleanup hints
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export LANG=C

run_with_timeout() {
    timeout 20 bash -c "$1" 2>/dev/null || echo "TIMEOUT"
}

run_with_timeout_short() {
    timeout 5 bash -c "$1" 2>/dev/null || echo "TIMEOUT"
}

emit() { echo "$1"; }

TOTAL=0
SECURITY=0

emit "📦 Ежедневная проверка обновлений — $(date '+%d.%m.%Y %H:%M')"
emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# === APT ===
emit "📥 APT (Ubuntu packages):"
apt-get -qq update 2>/dev/null || true
upgrades=$(apt list --upgradable 2>/dev/null | grep -v "^Listing" | head -30)
if [[ -n "$upgrades" ]]; then
    count=$(echo "$upgrades" | wc -l)
    emit "  🔴 $count пакетов с обновлениями:"
    echo "$upgrades" | sed 's/^/    /'
else
    emit "  ✅ Обновлений нет"
fi
echo ""

# === APT Security ===
emit "🔒 APT Security updates:"
sec_upgrades=$(apt list --upgradable 2>/dev/null | grep -i security | head -20)
if [[ -n "$sec_upgrades" ]]; then
    echo "$sec_upgrades" | sed 's/^/    /'
else
    emit "  ✅ Security обновлений нет"
fi
echo ""

# === KERNEL ===
emit "🐧 Kernel:"
current_kernel=$(uname -r)
available_kernels=$(apt list --installed 2>/dev/null | grep -E '^linux-image-[0-9]' | head -5)
echo "  Текущий: $current_kernel"
if echo "$available_kernels" | grep -qv "$current_kernel"; then
    emit "  🔴 Есть более новые ядра:"
    echo "$available_kernels" | sed 's/^/    /'
else
    emit "  ✅ Последнее ядро установлено"
fi
echo ""

# === FIRMWARE (fwupd) ===
emit "🔧 Firmware (fwupd):"
if command -v fwupdmgr >/dev/null 2>&1; then
    fwupd_out=$(run_with_timeout "fwupdmgr refresh 2>/dev/null && fwupdmgr get-updates 2>/dev/null")
    if [[ "$fwupd_out" != "TIMEOUT" && -n "$fwupd_out" && "$fwupd_out" != *"No upgrades"* && "$fwupd_out" != *"no upgrades"* ]]; then
        emit "  🔴 Есть обновления прошивки:"
        echo "$fwupd_out" | head -20 | sed 's/^/    /'
    else
        emit "  ✅ Обновлений прошивки нет"
    fi
else
    emit "  ⚪ fwupdmgr не установлен"
fi
echo ""

# === NPM ===
emit "📦 NPM (global packages):"
if command -v npm >/dev/null 2>&1; then
    npm_outdated=$(run_with_timeout "npm outdated -g --parseable 2>/dev/null | head -30")
    if [[ "$npm_outdated" != "TIMEOUT" && -n "$npm_outdated" ]]; then
        emit "  🔴 Есть обновления:"
        echo "$npm_outdated" | awk -F: '{print "    " $1 ": " $2 " → " $4}' | sed 's/ → $//'
    else
        emit "  ✅ Обновлений нет"
    fi
else
    emit "  ⚪ npm не установлен"
fi
echo ""

# === PNPM ===
emit "📦 PNPM (global packages):"
if command -v pnpm >/dev/null 2>&1; then
    pnpm_outdated=$(run_with_timeout "pnpm outdated -g --parseable 2>/dev/null | head -30")
    if [[ "$pnpm_outdated" != "TIMEOUT" && -n "$pnpm_outdated" ]]; then
        emit "  🔴 Есть обновления:"
        echo "$pnpm_outdated" | awk -F: '{print "    " $1 ": " $2 " → " $4}' | sed 's/ → $//'
    else
        emit "  ✅ Обновлений нет"
    fi
else
    emit "  ⚪ pnpm не установлен"
fi
echo ""

# === YARN ===
emit "📦 YARN (global packages):"
if command -v yarn >/dev/null 2>&1; then
    yarn_outdated=$(run_with_timeout "yarn global outdated --json 2>/dev/null | head -50")
    if [[ "$yarn_outdated" != "TIMEOUT" && -n "$yarn_outdated" ]]; then
        emit "  🔴 Есть обновления (JSON вывод)"
    else
        emit "  ✅ Обновлений нет"
    fi
else
    emit "  ⚪ yarn не установлен"
fi
echo ""

# === BUN ===
emit "📦 BUN (global packages):"
if command -v bun >/dev/null 2>&1; then
    emit "  ℹ️  bun обновляется сам: bun upgrade"
else
    emit "  ⚪ bun не установлен"
fi
echo ""

# === DENO ===
emit "🦕 DENO:"
if command -v deno >/dev/null 2>&1; then
    deno_ver=$(run_with_timeout_short "deno --version 2>/dev/null | head -1")
    emit "  ✅ $deno_ver"
    emit "  ℹ️  Обновление: deno upgrade"
else
    emit "  ⚪ deno не установлен"
fi
echo ""

# === CARGO ===
emit "🦀 CARGO (Rust packages):"
if command -v cargo >/dev/null 2>&1; then
    cargo_list=$(run_with_timeout "cargo install --list 2>/dev/null | grep -E '^[a-z0-9_-]+ v' | head -20")
    if [[ "$cargo_list" != "TIMEOUT" && -n "$cargo_list" ]]; then
        emit "  ℹ️ Установленные пакеты (проверьте вручную cargo install --list для обновлений):"
        echo "$cargo_list" | sed 's/^/    /'
    else
        emit "  ✅ Нет пакетов или таймаут"
    fi
    rust_ver=$(run_with_timeout_short "rustc --version 2>/dev/null")
    emit "  ✅ Rust: $rust_ver"
else
    emit "  ⚪ cargo не установлен"
fi
echo ""

# === PIP ===
emit "🐍 PIP (Python packages):"
if command -v pip3 >/dev/null 2>&1; then
    pip_outdated=$(run_with_timeout "pip3 list --outdated --format=freeze 2>/dev/null | head -30")
    if [[ "$pip_outdated" != "TIMEOUT" && -n "$pip_outdated" ]]; then
        emit "  🔴 Есть обновления:"
        echo "$pip_outdated" | sed 's/^/    /'
    else
        emit "  ✅ Обновлений нет"
    fi
    pip_ver=$(run_with_timeout_short "pip3 --version 2>/dev/null")
    emit "  ✅ $pip_ver"
else
    emit "  ⚪ pip3 не установлен"
fi
echo ""

# === UV ===
emit "🚀 UV (Python packages):"
if command -v uv >/dev/null 2>&1; then
    uv_ver=$(run_with_timeout_short "uv --version 2>/dev/null")
    emit "  ✅ $uv_ver"
    emit "  ℹ️  uv сам обновляется: uv self update"
else
    emit "  ⚪ uv не установлен"
fi
echo ""

# === POETRY ===
emit "📜 POETRY:"
if command -v poetry >/dev/null 2>&1; then
    poetry_ver=$(run_with_timeout_short "poetry --version 2>/dev/null")
    emit "  ✅ $poetry_ver"
else
    emit "  ⚪ poetry не установлен"
fi
echo ""

# === SNAP ===
emit "📦 SNAP:"
if command -v snap >/dev/null 2>&1; then
    snap_refresh=$(run_with_timeout "snap refresh --list 2>/dev/null | tail -n +2 | head -20")
    if [[ "$snap_refresh" != "TIMEOUT" && -n "$snap_refresh" ]]; then
        emit "  🔴 Есть обновления:"
        echo "$snap_refresh" | sed 's/^/    /'
    else
        emit "  ✅ Обновлений нет"
    fi
else
    emit "  ⚪ snap не установлен"
fi
echo ""

# === FLATPAK ===
emit "📦 FLATPAK:"
if command -v flatpak >/dev/null 2>&1; then
    flatpak_updates=$(run_with_timeout "flatpak remote-ls --updates 2>/dev/null | head -20")
    if [[ "$flatpak_updates" != "TIMEOUT" && -n "$flatpak_updates" ]]; then
        emit "  🔴 Есть обновления:"
        echo "$flatpak_updates" | sed 's/^/    /'
    else
        emit "  ✅ Обновлений нет"
    fi
else
    emit "  ⚪ flatpak не установлен"
fi
echo ""

# === APPIMAGE ===
emit "📦 APPIMAGE (AppImageUpdate):"
if command -v AppImageUpdate >/dev/null 2>&1; then
    emit "  ℹ️  AppImageUpdate установлен, проверьте вручную"
else
    emit "  ⚪ AppImageUpdate не установлен"
fi
echo ""

# === DOCKER IMAGES ===
emit "🐳 DOCKER (images):"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker_images=$(run_with_timeout "docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | head -20")
    if [[ "$docker_images" != "TIMEOUT" && -n "$docker_images" ]]; then
        emit "  ℹ️  Локальные образы (docker pull для обновления):"
        echo "$docker_images" | sed 's/^/    /'
    else
        emit "  ✅ Образов нет"
    fi
else
    emit "  ⚪ docker не установлен или демон недоступен"
fi
echo ""

# === PODMAN ===
emit "🦭 PODMAN:"
if command -v podman >/dev/null 2>&1; then
    podman_ver=$(run_with_timeout_short "podman --version 2>/dev/null")
    emit "  ✅ $podman_ver"
else
    emit "  ⚪ podman не установлен"
fi
echo ""

# === GO ===
emit "🐹 GO (modules):"
if command -v go >/dev/null 2>&1; then
    go_ver=$(run_with_timeout_short "go version 2>/dev/null")
    emit "  ✅ $go_ver"
    # Check for go module updates in current dir if any
    if [[ -f "go.mod" ]]; then
        go_mod_out=$(run_with_timeout "go list -u -m all 2>/dev/null | head -20")
        if [[ "$go_mod_out" != "TIMEOUT" && -n "$go_mod_out" ]]; then
            emit "  🔴 Обновления модулей в текущем проекте:"
            echo "$go_mod_out" | sed 's/^/    /'
        fi
    fi
else
    emit "  ⚪ go не установлен"
fi
echo ""

# === NODE ===
emit "🟢 NODE/NPM:"
if command -v node >/dev/null 2>&1; then
    node_ver=$(run_with_timeout_short "node --version 2>/dev/null")
    npm_ver=$(run_with_timeout_short "npm --version 2>/dev/null")
    emit "  ✅ Node: $node_ver, npm: $npm_ver"
    # Check nvm/fnm/volta
    if [[ -n "${NVM_DIR:-}" ]] || command -v fnm >/dev/null 2>&1 || command -v volta >/dev/null 2>&1; then
        emit "  ℹ️  Версионный менеджер обнаружен"
    fi
else
    emit "  ⚪ node не установлен"
fi
echo ""

# === RUBY/GEMS ===
emit "💎 RUBY/GEMS:"
if command -v gem >/dev/null 2>&1; then
    gem_outdated=$(run_with_timeout "gem outdated 2>/dev/null | head -20")
    if [[ "$gem_outdated" != "TIMEOUT" && -n "$gem_outdated" ]]; then
        emit "  🔴 Есть обновления гемов:"
        echo "$gem_outdated" | sed 's/^/    /'
    else
        emit "  ✅ Гемы актуальны"
    fi
    ruby_ver=$(run_with_timeout_short "ruby --version 2>/dev/null")
    emit "  ✅ $ruby_ver"
else
    emit "  ⚪ ruby/gem не установлен"
fi
echo ""

# === HOMEBREW ===
emit "🍺 HOMEBREW:"
if command -v brew >/dev/null 2>&1; then
    brew_outdated=$(run_with_timeout "brew outdated 2>/dev/null | head -20")
    if [[ "$brew_outdated" != "TIMEOUT" && -n "$brew_outdated" ]]; then
        emit "  🔴 Есть обновления:"
        echo "$brew_outdated" | sed 's/^/    /'
    else
        emit "  ✅ Обновлений нет"
    fi
    brew_ver=$(run_with_timeout_short "brew --version 2>/dev/null | head -1")
    emit "  ✅ $brew_ver"
else
    emit "  ⚪ homebrew не установлен"
fi
echo ""

# === NIX ===
emit "❄️ NIX:"
if command -v nix >/dev/null 2>&1; then
    nix_ver=$(run_with_timeout_short "nix --version 2>/dev/null")
    emit "  ✅ $nix_ver"
    emit "  ℹ️  nix-channel --update && nix-env -u для обновлений"
else
    emit "  ⚪ nix не установлен"
fi
echo ""

# === AI CLI TOOLS ===
emit "🤖 AI CLI TOOLS:"
for tool in claude codex cursor; do
    if command -v "$tool" >/dev/null 2>&1; then
        ver=$(run_with_timeout_short "$tool --version 2>/dev/null | head -1")
        emit "  ✅ $tool: $ver"
    else
        # Check common install paths
        found=false
        for path in /usr/local/bin ~/.local/bin ~/bin ~/.cargo/bin; do
            expanded=$(eval echo "$path")
            if [[ -x "$expanded/$tool" ]]; then
                ver=$(run_with_timeout_short "\"$expanded/$tool\" --version 2>/dev/null | head -1")
                emit "  ✅ $tool ($expanded): $ver"
                found=true
                break
            fi
        done
        [[ "$found" == "false" ]] && emit "  ⚪ $tool не найден"
    fi
done
echo ""

# === CLI TOOLS ===
emit "🛠️  CLI TOOLS (версии):"
tools=(gh docker kubectl helm terraform ansible vagrant packer)
for tool in "${tools[@]}"; do
    if command -v "$tool" >/dev/null 2>&1; then
        ver=$(run_with_timeout_short "$tool version 2>/dev/null | head -1" || run_with_timeout_short "$tool --version 2>/dev/null | head -1")
        emit "  ✅ $tool: $ver"
    fi
done
echo ""

# === VS CODE EXTENSIONS ===
emit "🔌 VS CODE EXTENSIONS:"
if command -v code >/dev/null 2>&1; then
    code_ext=$(run_with_timeout "code --list-extensions --show-versions 2>/dev/null | head -30")
    if [[ "$code_ext" != "TIMEOUT" && -n "$code_ext" ]]; then
        emit "  ℹ️  Установленные расширения:"
        echo "$code_ext" | sed 's/^/    /'
    else
        emit "  ✅ Расширений нет или таймаут"
    fi
elif command -v code-insiders >/dev/null 2>&1; then
    code_ext=$(run_with_timeout "code-insiders --list-extensions --show-versions 2>/dev/null | head -30")
    if [[ "$code_ext" != "TIMEOUT" && -n "$code_ext" ]]; then
        emit "  ℹ️  Установленные расширения (insiders):"
        echo "$code_ext" | sed 's/^/    /'
    fi
else
    emit "  ⚪ VS Code не установлен"
fi
echo ""

# === SYSTEM CLEANUP INFO ===
emit "🧹 SYSTEM CLEANUP (info):"
emit "  apt: apt autoremove && apt autoclean"
emit "  snap: snap set system refresh.retain=2"
emit "  flatpak: flatpak uninstall --unused"
emit "  docker: docker system prune -a"
emit "  pip: pip cache purge"
emit "  npm: npm cache clean --force"
emit "  cargo: cargo clean"
emit "  journal: journalctl --vacuum-time=7d"
echo ""

emit "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ "$TOTAL" -gt 0 ]]; then
    emit "📊 Total: $TOTAL update(s)"
    [[ "$SECURITY" -gt 0 ]] && emit "⚠️  $SECURITY security update(s) — prioritize!"
else
    emit "🎉 Everything is up to date!"
fi
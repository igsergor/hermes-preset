# Distro upgrade advisory — assess BEFORE recommending

Task class: user asks "what distro/version am I on", then "what does the newer
release give me, should I upgrade?". Never answer from memory: verify the host
state, then read the actual release notes, then compare against what HE runs.

## Step 1 — host profile (one terminal call, batched)

```bash
lsb_release -a; uname -r; systemd-detect-virt
lscpu | egrep 'Model name|^CPU\(s\)'; free -h | head -2
df -h / /boot                      # free space gate — see below
systemctl is-active systemd-timesyncd chrony   # NTP daemon in use
ls /etc/apt/sources.list.d/        # third-party repos that must survive
snap list                          # note desktop snaps if headless
systemctl list-units --state=running --no-legend | egrep -i 'ollama|wireguard|nginx|docker|podman'
which -a python3                   # Hermes runs its own venv; system python differs
```

Interpretation rules that changed the verdict in practice:

- **`uname -r` major >= the new LTS's kernel already?** If the host is on an HWE
  kernel from the interim line, the headline gain of the new LTS ("new kernel")
  is ALREADY installed — say so, it removes the main upgrade motive.
- **Free disk < ~25% of root** = no-go without a cleanup pass first. A release
  upgrade downloads, unpacks, and may need room to roll back.
- Host role is headless server + Hermes runtime → desktop/GNOME changes are
  near-zero value; weight the decision on server-side breaks.

## Step 2 — read the release notes properly

Canonical keeps one page per release: `documentation.ubuntu.com/release-notes/<ver>/`
with a `summary-for-lts-users/` subpage for the LTS-to-LTS delta. That page is
long; `web_extract` returns only the head regardless of `char_limit`. Use the
bundled stripper, then read the sections that matter:

```bash
python3 ~/.hermes/skills/devops/system-audit/scripts/html_to_text.py \
  https://documentation.ubuntu.com/release-notes/26.04/summary-for-lts-users/ /tmp/rel.txt
grep -n "¶" /tmp/rel.txt          # section index -> line numbers
```

Pitfall: the `` anchors become whitespace after stripping, so searching for the
section title with a trailing `` gives -1 hits. Search for the bare title
(`### Server`, `Server`) instead, or just index off the anchor listing.

## Step 3 — change categories that break a running host

Check the notes for each and state impact concretely:

| Category | What to look for | Consequence |
|---|---|---|
| Kernel | GA vs HWE line, new kernel major | already-have-it → no motive; else reboot + vendor modules |
| OpenSSH | major version jump | deprecated algos, new key-exchange defaults, DSA key removal — always flag on a host reached over SSH |
| Time daemon | `chrony` replacing `systemd-timesyncd` | time silently stops unless migrated manually (see migration cmd in notes) |
| Display | Wayland-only default session | breaks VNC/RDP/x11vnc access; X11 apps survive via XWayland |
| Removed features | e.g. GDM PreLogin/PostSession scripts, `kpartx-boot`, `dmraid` | corporate home-dir sync scripts, old RAID setups stop working |
| Python/toolchain | interpreter major bumps in archive | venvs pinned to old minor must be rebuilt |
| Third-party repos | PPA/deb sources that don't publish for the new release | apt update fails after upgrade; verify before recommending |

Also record from the notes: interim releases folded into the LTS (24.10, 25.04,
25.10 for a 26.04 target) — changes land that the summary highlights omit.

## Step 4 — verdict shape user expects

Three parts, no padding:

1. **Profile** — what he actually runs (short bullet list, facts from step 1).
2. **What the new release brings** — only the items touching his role; mark the
   already-present ones.
3. **Verdict with numbered reasons** — recommend stay or upgrade, each reason
   tied to a fact from step 1 (disk %, kernel present, SSH dependence), then one
   concrete next step ("clear to 40G+ free, wait for 26.04.2/3, plan chrony").

Offer the cleanup pass as a follow-up instead of doing it unasked — the host is a
live server.

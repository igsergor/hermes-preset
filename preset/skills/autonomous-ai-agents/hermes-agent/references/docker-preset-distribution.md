# Distributing Hermes as a preconfigured Docker image

Use when the ask is "give someone else a ready Hermes" — `docker pull` → `docker run` → working agent with skills, vault and memory, without a setup wizard. Covers image shape, what must never ship, first-run onboarding, local embeddings, and publishing.

## Shape: stateless image + seeded data volume

- The upstream repo ships `Dockerfile`, `docker-compose.yml`, `docker-compose.windows.yml` and a `docker/` supervision tree; a public image exists as `nousresearch/hermes-agent` (tags `latest`/`stable`/`main`/`X.Y.Z`, amd64+arm64). Do not fork the Dockerfile — base on it.
- The image is stateless: **all state is one directory mounted at `/opt/data`** (= `HERMES_HOME`). Therefore the distributable artifact is not "Hermes in Docker" (already done upstream) but a **curated `/opt/defaults` layer seeded into an empty `/opt/data` on first start**.
- The seeding step must be idempotent: copy only when the volume is empty or lacks a profile, never overwrite an existing profile — otherwise a version bump silently wipes the user's config.
- Ship `latest` plus an immutable version tag, and pin the base image by digest; a floating base makes "it worked yesterday" unreproducible.

## What must never enter a public image

Public layers are readable by anyone, and a leaked key cannot be revoked from copies already pulled. Secrets belong only in the runtime volume, written at first start:

- `.env`, `auth.json` (OAuth + refresh tokens), any provider key.
- `sessions/`, `state.db` (the whole conversation history), `browser-profile/` (live cookies), `logs/`, caches, backups, `state-snapshots/`, `media_cache/`.
- The user's Obsidian vault contents and memory/profile text — ship an empty PARA skeleton instead.

## Audit before publishing

Skills are the real leak vector: they were written against a specific machine. Grep counts triage the pass, they do not replace reading it: `sk-`-style strings, `password`, LAN addresses, mail domains, chat IDs, personal hostnames. Read every hit — most are examples, enough are not.

Cron: ship only generic jobs (memory distillation, vault reindex, digests) with delivery `local` by default. Personal jobs (work mail, document flow, billing, home network) do not belong in a preset at all — that is a content decision, not a config switch.

## First run without a setup wizard

- Hermes cannot answer a single message before a model key exists, and cron jobs without a provider fail rather than idle. Gate the cron runner on provider presence so jobs report `skipped (no model)` instead of filling logs with failures.
- Onboarding surfaces, best first:
  1. **Dashboard** (`hermes dashboard`, port 9119) — real provider/key editing UI. Bind `127.0.0.1` and publish the port; a non-loopback bind always requires an auth provider since the hardening, so never expose it on `0.0.0.0`.
  2. **Tiny first-run form** — a few dozen lines of HTML posting to the entrypoint, writing `.env` and restarting the gateway. The only custom code needed for a true "paste your key and go".
  3. `-e <PROVIDER>_API_KEY=...` on `docker run` — one line, but requires knowing the variable name.
  4. `hermes setup` inside the container — last resort; it is the wizard the user asked to avoid.
- Ask for at most: model key (mandatory), messaging-platform token (optional — the dashboard's embedded chat works without it), timezone/name (prefill and let them confirm).

## Local embeddings inside the container

Vector recall must not depend on the host. Bundle CPU inference and point the memory provider at it:

- `llama-server --embedding` with `bge-m3` in GGUF (~0.5–0.6 GB, 1024 dims, multilingual — the right default for Russian). Do **not** bundle full Ollama: +1 GB and a second daemon for one model.
- The Obsidian memory plugin calls an Ollama-style `/api/embeddings` with `{"model", "prompt"}` and also accepts OpenAI-style `{"model", "input"}`; it takes `embedding_api_url`/`embedding_api_key`, default model `bge-m3`, default dim 1024. Setting that URL to `127.0.0.1:<port>` is the whole integration.
- Payoff to state plainly: indexing and recall work before any API key, so "no brain yet" does not mean a broken memory layer.
- Pin the dimension in config. Swapping the embedding model without rebuilding the index corrupts results silently rather than erroring.

## Publishing

- Docker Hub public repo is the intended channel; Hermes is MIT, redistribution is fine, keep the copyright notice. ghcr.io as a mirror (anonymous Docker Hub pulls are rate-limited per IP).
- Build multi-arch with `buildx` (amd64 + arm64 for Apple silicon); GGUF weights are arch-independent, only the binaries rebuild.
- Expect ~3–4 GB from the base image (bundled Chromium) plus the preset layer; say so up front — pull time is the top complaint.
- Publish the run command with a **named volume**: `-v hermes:/opt/data`. On Windows a bind mount to `C:\...` brings ACL and speed problems.

## OS abstraction — what is and is not true

The image is genuinely OS-independent: one image, Linux inside, the user never configures an environment. Caveats are about the Docker runtime, not the image:

- **Windows**: Docker Desktop provisions a Linux kernel via WSL2 internally. It is a one-time installer prerequisite (virtualization enabled in BIOS, ~2 GB RAM overhead), not a step the user performs. `network_mode: host` does not work there — map ports instead.
- **macOS**: Docker Desktop or Colima (a VM either way); arm64 image required.
- **Linux**: the Docker engine directly, no layer at all.
- Docker Desktop is free for personal/small-business use and paid for large companies; Podman Desktop and Rancher Desktop run the same image when that matters.
- Not available in the container: local GPU models and the Electron desktop app.

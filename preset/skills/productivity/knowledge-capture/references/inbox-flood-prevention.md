# Preventing Inbox Flood from Auto-Capture (fix 2026-08-21; resume-aware upgrade 2026-08-21)

Discovered and fixed: auto-capture cron (`auto-capture-obsidian.py`, daily 02:00, job `61669f929e9a`)
piled up unprocessed notes in `Inbox/` with duplicate `(1)`, `(2)` suffixes.

## Root causes
- Every session written to `Inbox/`, including empty (message_count=0), test, and short greetings («привет»).
- No dedup → re-runs created duplicate files via the `(N)` collision branch.
- Filename built from generic `title` → distinct re-captures collide on the same path.

## Fix (encode into the capture script)
1. **Output to `Archives/Sessions/` instead of `Inbox/`.** Session logs are history/journal,
   not action items. Inbox stays purely for manual quick-captures.
   - `SESSIONS_DIR = VAULT_PATH/"Archives"/"Sessions"`; `mkdir(parents=True, exist_ok=True)`.
2. **Resume-aware dedup by watermark — NOT "skip if session_id exists".** A naive skip-by-session_id
   LOSES data: sessions can be resumed or context-compressed later, and the same `session_id`
   accumulates new messages. Never discard a session just because a note already exists.
   - The robust watermark is `MAX(messages.id)`. Verified against `state.db`: message `id` is
     **monotonic and never decreases** — resume appends messages with higher `id`, and context
     compression also *adds* new (rewriting) messages with higher `id`. So `MAX(id)` always grows
     when there is genuinely new content.
   - Store `captured_msg_id: <MAX(messages.id)>` in the note's frontmatter.
   - Logic (one file per session):
     - No note → create, set `captured_msg_id`.
     - Note exists AND `current MAX(id) > captured_msg_id` → **update in place** (overwrite same file
       with a fresh snapshot), bump `captured_msg_id`. This catches resume, dossip, and compression.
     - Note exists AND `MAX(id) == captured_msg_id` → skip (idempotent).
   - Helper `find_session_note(session_id)` scans ONLY `Archives/Sessions/*.md` for
     `session_id: "<id>"` and returns (path, captured_msg_id). NEVER rglob the whole vault:
     Knowledge-дистилляты в Resources тоже содержат session_id в frontmatter, и захват,
     найдя такой файл, ЗАТРЁТ Knowledge-заметку шаблоном сессии (см. gotcha 13/14 в SKILL.md).
3. **Selection by last activity, not `started_at`.** `get_sessions(days)` must select sessions whose
   `MAX(messages.timestamp)` is in the window (JOIN messages + GROUP BY s.id), so a session resumed
   today but started a week ago is still picked up. `WHERE started_at > ?` silently drops resumed sessions.
4. **Skip trivial/empty** with `is_trivial_session(messages, session_data)`:
   - `message_count == 0` → skip.
   - No user-role messages → skip.
   - total `message_count < 8` AND **all** user messages are short greetings → skip.
   - Greeting check must strip the `[Sender] ` prefix AND strip punctuation from the first word
     (`привет,` → `привет`). Use `all(...)` over user msgs, NOT `len(user_msgs)<=1`, because
     `state.db` can contain duplicated copies of the same user message.
5. Also fix latent template bug: `content.replace("{{insights}", ...)` (missing closing `}`)
   never matched, leaving the placeholder in every note.
6. **No boilerplate stubs in sections.** Template placeholders must render to empty ("-") or real
   content — never fixed stub text like "(добавить при обработке)": identical strings repeated
   across hundreds of files poison full-text and vector search. Clean existing notes in bulk
   (regex replace across Archives/Sessions) when stubs are found.

## Live confirmation of resume behavior
The active conversation session (started today, `ended=None`, still growing) correctly re-captures on
each run: previous `captured_msg_id=18642`, DB `MAX(id)` grew to 18644 (2 new messages) → it updated.
Finished sessions stayed idempotent (`⏭ No new messages since last capture`). This is the desired
behavior; a session note being "updated" repeatedly is NOT a bug when the session is genuinely active.

## Pitfall for reviewers
- Broken wiki-links in hub notes (e.g. `[[📚 Ресурсы/CLI шпаргалки]]`) often don't match real
  filenames (`CLI Шпаргалки.md`). Reference the actual filename without folder prefix.
- Backfill: pre-existing session notes created before the watermark field exist with
  `captured=0`; the next run updates them once to backfill `captured_msg_id` (harmless, no duplicate).

## Verification
After the fix, run `python3 auto-capture-obsidian.py --days 3` twice. First run may UPDATE existing
notes (backfills watermark); second run must be idempotent: prints `⏭ No new messages since last
capture ...` for finished sessions, `⏭ Trivial/empty session skipped ...` for greetings, and the
active session may `🔄 Updated session note (resumed)`. No new files land in `Inbox/`.
# Hermes Gateway — Supported Messaging Platforms

Verified against source: `~/.hermes/hermes-agent/gateway/platforms/` (May 2026).

## Platforms with Dedicated Adapters (confirmed in source code)

| Platform | Adapter File | Auth Method | Notes |
|----------|-------------|-------------|-------|
| Telegram | `telegram.py` | Bot API token via `.env` | Full support: DMs, groups, topics, media |
| Slack | `slack.py` | Bot token + App token (Socket Mode) | Requires `message.channels` event subscription |
| WhatsApp | `whatsapp.py` | Baileys bridge, QR pairing | Run `hermes whatsapp` to pair |
| Signal | `signal.py` | signal-cli | Personal + group chats |
| Email | `email.py` | SMTP/IMAP via himalaya or config | |
| SMS | `sms.py` | Configurable provider | |
| Matrix | `matrix.py` | Open protocol, any homeserver | |
| Home Assistant | `homeassistant.py` | HA access token | Smart home control |
| DingTalk | `dingtalk.py` | Alibaba enterprise chat | Corporate messenger |
| Feishu / Lark | `feishu.py` | App token | Corporate messenger + docs + drive |
| WeCom | `wecom.py` | WeChat Business (企业微信) | Business WeChat |
| WeChat (Weixin) | `weixin.py` | | Main Chinese messenger |
| BlueBubbles | `bluebubbles.py` | Mac relay server | iMessage via BlueBubbles server |
| Webhooks | `webhook.py` | HTTP callbacks | Event-driven integrations |
| API Server | `api_server.py` | REST API | Open WebUI and external clients |
| Yuanbao | `yuanbao.py` | Tencent 元宝 | Chinese messenger |
| QQ Bot | `qqbot/` | QQ official bot API | Chinese platform QQ |
| MS Graph Webhook | `msgraph_webhook.py` | Microsoft Graph | Outlook / Microsoft 365 integration |

## Platforms Mentioned in Docs but NOT in Source Code

| Platform | Status | Notes |
|----------|--------|-------|
| Mattermost | ⚠️ Not found in platform adapters (as of May 2026) | Listed in docs but code may be pending or deprecated |
| Discord | ⚠️ Not in `gateway/platforms/` | Docs mention it; may be at a different path or pending |

## Platforms Available via CLI Tools (not gateway adapters)

These work via dedicated skills/CLIs, not as gateway message channels:

| Platform | Tool | Category |
|----------|------|----------|
| X / Twitter | `xurl` CLI | social-media skill |
| Airtable | REST API via curl | productivity skill |
| Google Workspace | `gws CLI` | productivity skill (Gmail, Calendar, Drive, Docs) |
| Linear | `linear` CLI | productivity skill |
| Notion | `ntn CLI` | productivity skill |
| Spotify | `spotify` skill | media skill |
| iMessage | `apple-wrapper` (macOS only) | Built-in |

## How to Verify the Current List

Don't rely on docs alone — they go stale. Always check the source:

```bash
ls ~/.hermes/hermes-agent/gateway/platforms/*.py | xargs -I{} basename {} .py
```

Or for the full doc reference:
```
hermes-agent/docs/user-guide/messaging/
```

# MTProto Proxy Ecosystem — May 2026

Last researched: 2026-05-29. Sources verified live during session.

## Context

Research conducted for Telegram access under Russian ISP blocking (РКН / TSPU). Scope: **native Telegram proxies only** — `tg://proxy` links that auto-configure in the app with one click. Excluded: VPS self-hosting, SOCKS5 services, VPN-based solutions.

## Free Aggregators & Services

### MTProto.Space (✅ verified live)
- URL: https://mtproto.space/
- Server: proxy.mtproto.space (dynamic per session)
- Port: 2053
- FakeTLS: ✅ (vk.ru obfuscation)
- Users online: ~5,300
- Bandwidth: 1 Gbps dedicated
- Language: Russian
- Registration: none (one-click button)
- Sister site: MTProto.Monster (same team)
- **Verdict**: Best free option for Russian users. Fast, FakeTLS, no registration.

### MTProto.Monster (✅ verified live)
- URL: https://mtproto.monster/
- Port: 443
- FakeTLS: ✅
- Language: Russian
- Sister of MTProto.Space (cross-linked in footers)
- **Verdict**: Good backup, slightly slower generation.

### MTPro.XYZ (✅ verified live)
- URL: https://mtpro.xyz/
- Running since: 2018
- Proxies online: 50+ at time of check
- Countries: DE, RU, US, FI, FR
- Access: bot @mtpro_xyz_bot, channel @mtpro_xyz
- Paid option: private proxies via PX6.ME (proxy6.net)
- **Verdict**: Largest aggregator, time-tested. Public list means IPs get blocked faster.

### Telegram Channels (public proxy lists)

**@proxyMTProto** (✅ very active)
- Latest posts: May 28-29, 2026 (same day as research)
- Providers: chunkycorp.shop, proxytg.space, duckdns.org
- FakeTLS obfuscation domains: avito.ru, microsoft.com, amazon.com
- ~20 messages per page scroll
- **Verdict**: Best channel for fresh daily proxies.

**@tgproxylist** (⚠️ less active)
- Description: "Бесплатные публичные прокси сервера для работы Telegram"
- Latest post: April 2026
- ~20 messages visible
- **Verdict**: Good backup, but proxyMTProto is more active.

### Static Lists (not recommended as primary)

**mtprotoproxy.com**
- Only ~5 proxies, all Netherlands (tlgfast.com)
- Last updated: June 2025
- No FakeTLS on listed proxies
- **Verdict**: Stale, skip.

## Commercial Services

### PX6.ME (proxy6.net)
- URL: https://px6.me/ (redirects from proxy6.net)
- Scale: 995,807 users, 39M+ proxies sold, 514K active
- MTProto pricing: from $0.26/week (Taiwan)
- Countries: Russia, Ukraine, Taiwan, UK, and 20+ more
- Periods: 3 days to 3 months
- Automation: instant after payment, API available
- Referral: 30% partnership program
- **Caveat**: Not all IPs have FakeTLS. Must verify before buying for Russia.
- **Verdict**: Largest commercial option. Cheap per-IP but check for RKN blocks.

## Proxy Link Format

All services generate links in this format:
```
tg://proxy?server=<host>&port=<port>&secret=<hex_secret>
```
or
```
https://t.me/proxy?server=<host>&port=<port>&secret=<hex_secret>
```

The `secret` field encodes the FakeTLS domain (first 2 hex chars = version, remaining = obfuscation domain + padding). Example from chunkycorp.shop: secret starts with `ee`, domain = `avito.ru` — makes DPI see Avito traffic, not Telegram.

## Key Criteria for Russia

1. **FakeTLS is essential** — plain MTProto is signature-blocked by TSPU
2. **Port 443 preferred** — standard HTTPS port, harder to block without collateral
3. **Non-Russian IP** — Russian IPs are less useful (if VPN/proxy blocking is the problem, RU IP → RU server is already blocked)
4. **Regular updates** — public proxies get blocked within days/weeks

## Recommended Starter Stack

1. **Primary**: MTProto.Space (free, one click, FakeTLS/vk.ru)
2. **Fallback**: PX6.ME Taiwan MTProto ($0.26/week, private IP)
3. **Monitor**: @proxyMTProto Telegram channel (daily fresh proxies)

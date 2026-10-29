# TPROXY + MikroTik VPN Debugging Pattern

## Architecture (confirmed working)

```
LAN client (192.168.1.x)
    │
    ▼
MikroTik (192.168.1.10)
    │  mangle prerouting: src=VPN_Clients → mark-routing VLESS_MARK
    │  route VLESS_MARK: 0.0.0.0/0 via 192.168.1.10%bridge
    │  nat srcnat: routing-mark=VLESS_MARK → masquerade
    │
    ▼
VPN server (192.168.1.10)
    │  iptables mangle PREROUTING → SINGBOX chain
    │    lo → ACCEPT
    │    192.168.1.10/24 → RETURN (local bypass)
    │    TCP/UDP → TPROXY :15001 mark 0x1
    │  sing-box listens on :15001 (TPROXY mode)
    │  sing-box outbound: VLESS → upstream:8443
    │
    ▼
Upstream VLESS server (e.g. 193.233.249.18:8443)
    │
    ▼
Internet
```

## Critical Debugging Rules

### 1. Server's own traffic ≠ client traffic
- `curl` from the VPN server goes through OUTPUT chain, NOT PREROUTING/TPROXY
- Server's curl will ALWAYS show the server's real IP, not the VPN IP
- This is BY DESIGN — prevents a loop
- **Never conclude VPN is broken because server's curl shows real IP**

### 2. How to verify VPN is working
- Check iptables TPROXY counters: `iptables -t mangle -L SINGBOX -n -v` — should show increasing packet counts
- Check sing-box logs for `outbound connection to <real-domain>:443` — proves tunnel carries real traffic
- Check for DNS errors: `dns: exchange failed ... EOF` means upstream blocks port 53

### 3. DNS through tunnel is a common failure point
- sing-box DNS config: `address: "tcp://8.8.8.8"` with `detour: "proxy"` sends DNS through VLESS tunnel
- Many VPN upstreams BLOCK port 53 through the tunnel → `EOF` errors
- Symptoms: tunnel is up (HTTPS works in logs), but clients can't resolve domains → "no internet"
- Fix: switch to DNS-over-HTTPS (`https://dns.google/dns-query`) or different upstream

### 4. When user says "no internet through VPN" — investigate YOURSELF
Do NOT ask the user to test from the client. Work through the evidence:
1. `systemctl is-active sing-box`
2. `ping <upstream_ip>` + `nc -zv <upstream_ip> <port>`
3. `openssl s_client -connect <upstream_ip>:<port> -servername <sni>`
4. sing-box logs: look for outbound connections AND DNS errors
5. iptables TPROXY counters increasing?
6. DNS EOF errors in logs?
7. Only THEN conclude: config issue vs upstream blocking

### 5. MikroTik command length limit
- RouterOS SSH has ~190 char command limit
- Run ONE command per SSH call, not `cmd1; cmd2; cmd3`

## Session Notes (2026-05-29)

**Symptom:** Tunnel up (TLS OK, sing-box connected), clients "no internet".

**Root cause:** Upstream VLESS server blocks DNS (port 53) through tunnel. `dns: exchange failed ... EOF` for all queries. Without DNS, no domains resolve.

**Evidence:**
- `outbound connection to eu-mobile.events.data.microsoft.com:443` (111ms) → tunnel works
- `dns: exchange failed for gateway.discord.gg. IN A: EOF` → DNS blocked
- `dig @193.233.249.18 google.com` → `connection refused` on port 53

**Lesson:** When tunnel is up but no internet, check DNS through tunnel FIRST.
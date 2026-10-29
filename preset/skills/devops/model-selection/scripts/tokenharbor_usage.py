#!/usr/bin/env python3
"""Статистика использования TokenHarbor через локальный OmniRoute.

Берёт usage_history из ~/.omniroute/storage.sqlite (провайдер = OpenAI-compatible
коннект на tokenharbor.ai), считает токены по дням/моделям и оценивает расход
в долларах по ценам из каталога https://tokenharbor.ai/models.

Запуск: python3 tokenharbor_usage.py [дней]

Внимание: DB и TH provider id захардкожены под эту машину; если TH-коннект в
OmniRoute пересоздавали — узнайте актуальный id через
`select provider, count(*) from usage_history group by provider` и поправьте TH.
"""
import json
import re
import sqlite3
import sys
import urllib.request

DB = "~/.omniroute/storage.sqlite"
TH = "openai-compatible-chat-e62cc7bb-782c-4da0-b0bc-8c286d31ea31"
MODELS_URL = "https://tokenharbor.ai/models"

days = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def fetch_prices():
    """Цены моделей ($/Mtok in, out) из HTML каталога /models."""
    html = urllib.request.urlopen(MODELS_URL, timeout=15).read().decode("utf-8", "ignore")
    prices = {}
    for m in re.finditer(
        r'surface\\":\\"([a-z0-9.:-]+)\\".*?priceIn\\":([\d.]+),\\"priceOut\\":([\d.]+).*?isFree\\":(true|false)',
        html,
    ):
        prices[m.group(1)] = (float(m.group(2)), float(m.group(3)), m.group(4) == "true")
    return prices


def main():
    prices = fetch_prices()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    # окно 4-недельного Pass = 28 дней, но свежие данные обычно за 7
    rows = con.execute(
        """select date(timestamp) d, model, sum(tokens_input), sum(tokens_output),
                  sum(tokens_cache_read), count(*), min(timestamp), max(timestamp)
           from usage_history where provider=? and timestamp >= datetime('now', ?)
           group by d, model order by d desc, model""",
        (TH, f"-{days} days"),
    ).fetchall()

    total_cost = 0.0
    total_tok = 0
    per_day = {}
    print(f"{'день':<12}{'модель':<28}{'in':>12}{'out':>10}{'cache':>12}{'req':>5}{'~$':>8}")
    for d, m, ti, to, tcr, n, _, _ in rows:
        ti, to, tcr = ti or 0, to or 0, tcr or 0
        p = prices.get(m) or prices.get(m.replace(":free", ""))
        if p:
            pin, pout, isfree = p
            cost = 0.0 if isfree else (ti / 1e6) * pin + (to / 1e6) * pout + (tcr / 1e6) * pin * 0.1
        else:
            cost = 0.0  # модель без публичной цены — вклад ~0 (проверено)
        total_cost += cost
        total_tok += ti + to + tcr
        dd = per_day.setdefault(d, [0.0, 0])
        dd[0] += cost
        dd[1] += n
        print(f"{d:<12}{m:<28}{ti:>12,}{to:>10,}{tcr:>12,}{n:>5}{cost:>8.3f}")

    print(f"\nИтого за {days} дн.: {total_tok:,} токенов, ~${total_cost:.2f} израсходовано Pass-allowance")
    print("По дням:")
    for d in sorted(per_day, reverse=True):
        c, n = per_day[d]
        print(f"  {d}: ~${c:.2f} ({n} req)")
    print("\n(Точный остаток allowance — только в Dashboard -> Billing на tokenharbor.ai:")


if __name__ == "__main__":
    main()

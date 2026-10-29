# No-Agent Script: Dynamic Provider Routing

## Когда это нужно

`no_agent=true` cron-скрипты не используют Hermes LLM routing — они вызывают API напрямую через curl/subprocess. Если скрипту нужно обращаться к LLM, он должен сам определить:
- Какой endpoint использовать (unwrap proxy для ClinePass или прямой API провайдера)
- Как авторизоваться (Bearer token или без)

Ранее модель и endpoint жёстко зашивались в скрипт (`DS_MODEL = "cline-pass/deepseek-v4-flash"`). Это ломается при смене дефолтной модели в Hermes.

## Паттерн: `get_model_config()`

Скрипт читает `model.default` из `config.yaml` и находит соответствующий провайдер в `custom_providers`.

### Импорт

```python
import yaml
from pathlib import Path

HERMES_CONFIG = Path(os.environ.get("HERMES_CONFIG", "~/.hermes/config.yaml"))
UNWRAP_URL = "http://127.0.0.1:8765/chat/completions"
```

### Функция

```python
def get_model_config():
    """Прочитать модель по умолчанию из config.yaml и определить endpoint для API.

    Returns:
        (model_id: str, endpoint_url: str, api_key: str or None)
        - Для ClinePass: endpoint = unwrap proxy (:8765), api_key = None (прокси сам авторизует)
        - Для остальных: endpoint = base_url провайдера + /chat/completions, api_key = из config/key_env
    """
    try:
        with open(HERMES_CONFIG) as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"  ⚠ Ошибка чтения config.yaml: {e}")
        return ("", "", None)

    model_id = cfg.get("model", {}).get("default", "")
    if not model_id:
        return ("", "", None)

    custom_providers = cfg.get("custom_providers", [])

    for prov in custom_providers:
        models = prov.get("models", [])
        matched = None
        for m in models:
            if m.get("id") == model_id:
                matched = m
                break
        if matched is None:
            continue  # этот провайдер не содержит нашу модель

        base_url = prov.get("base_url", "").rstrip("/")

        # ClinePass — идёт через unwrap proxy
        if "cline-pass" in model_id or "127.0.0.1:8765" in base_url:
            return (model_id, f"{base_url}/chat/completions", None)

        # Остальные — напрямую с Bearer auth
        api_key = prov.get("api_key", "")
        if not api_key:
            key_env = prov.get("key_env", "")
            if key_env:
                api_key = os.environ.get(key_env, "")
        return (model_id, f"{base_url}/chat/completions", api_key)

    # Fallback: модель не найдена в custom_providers
    print(f"  ⚠ Модель '{model_id}' не найдена в custom_providers, fallback на unwrap proxy")
    return (model_id, UNWRAP_URL, None)
```

### Использование

```python
model_id, endpoint, api_key = get_model_config()
if not model_id:
    print("  ⚠ Не удалось прочитать модель по умолчанию из config.yaml")
    sys.exit(1)

payload = json.dumps({
    "model": model_id,
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 500,
    "temperature": 0.3,
})

cmd = ["curl", "-s", "-X", "POST", endpoint,
       "-H", "Content-Type: application/json",
       "-d", payload, "--max-time", "300"]

if api_key:
    cmd.insert(4, "-H")
    cmd.insert(5, f"Authorization: Bearer {api_key}")

# Выполнить curl-запрос
result = subprocess.run(cmd, capture_output=True, text=True, timeout=310)
resp = json.loads(result.stdout)
```

## Логика роутинга

| Модель | Endpoint | Auth |
|--------|----------|------|
| `cline-pass/*` | unwrap proxy `:8765/v1/chat/completions` | нет (прокси сам авторизует) |
| `googleai/*` | `generativelanguage.googleapis.com/v1beta/chat/completions` | Bearer из `api_key` |
| `ministral-*` / `mistral-*` | `api.mistral.ai/v1/chat/completions` | Bearer из `MISTRAL_API_KEY` (env) |
| `auto/*` (OpenRouter) | локальный proxy `localhost:20128/chat/completions` | нет |
| Не найдена в `custom_providers` | unwrap proxy (`:8765/chat/completions`) | нет (fallback) |

## Преимущества

- Смена дефолтной модели в `config.yaml` → скрипт автоматически подхватывает
- Не требует `pinned model/provider` в `jobs.json` (модель живёт внутри скрипта)
- Работает с любым провайдером из `custom_providers`
- Единая точка конфигурации (config.yaml)

## Где применяется

- `obsidian-weekly-review.py` — еженедельный разбор Obsidian (cron `7fa6f2f77e31`)

## Gotchas

- `yaml` (PyYAML) должен быть установлен в системе (`pip install pyyaml` или системный пакет)
- Для ClinePass unwrap proxy должен быть запущен (`systemctl --user status clinepass-unwrap-proxy`)
- `api_key` из `prov.get("api_key")` может быть полным ключом или пустым — тогда читается из `key_env`
- Если `HERMES_CONFIG` не задан в env — используется `~/.hermes/config.yaml`
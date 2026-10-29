# Model Comparison: Mistral Large 3 2512 vs Nemotron-3-Ultra vs DeepSeek V4 Flash
*Source: OpenRouter API (`curl -s "https://openrouter.ai/api/v1/models"`), 22.08.2026*

## ⚠️ Critical: Reasoning_effort Support

Not all models support the `/reasoning` command at the API level. Check `supported_parameters` via OpenRouter API.

| Model | Supports reasoning_effort? | Valid levels |
|-------|---------------------------|--------------|
| `mistralai/mistral-large-2512` | **NO** ❌ | N/A |
| `mistralai/mistral-medium-3-5` | **YES** ✅ | none/low/medium/high/xhigh |
| `nvidia/nemotron-3-ultra-550b-a55b` | **NO** ❌ | N/A |
| `deepseek/deepseek-v4-flash-0731` | **YES** ✅ | none/low/medium/high/xhigh (xhigh=max) |
| `deepseek/deepseek-v4-flash` (0423) | **YES** ✅ | none/low/medium/high/xhigh (xhigh=max) |
| `~deepseek/deepseek-v4-flash-latest` | **YES** ✅ | none/low/medium/high/xhigh (xhigh=max) |

## Summary Table (Corrected 22.08.2026)

| Критерий               | Mistral Large 3 2512         | Nemotron-3-Ultra             | DeepSeek V4 Flash 0731       |
|------------------------|------------------------------|------------------------------|------------------------------|
| **ID модели**          | `mistralai/mistral-large-2512` | `nvidia/nemotron-3-ultra-550b-a55b` | `deepseek/deepseek-v4-flash-0731` |
| **Версия**             | Декабрь 2025                 | Июнь 2026                    | Июль 2026                    |
| **Параметры**          | 41B / 675B MoE               | 55B / 550B MoE               | 13B / 284B MoE               |
| **Лицензия**           | Apache 2.0                   | open weights                 | proprietary                  |
| **Контекст**           | 262K                         | 512K (платный) / 1M (free)   | **1.3M**                     |
| **Мультимодальность**  | **Да** (текст+изобр+файлы)  | Нет                          | Нет (есть Vision Exp)        |
| **Цена (ввод)**        | $0.50 / 1M                   | $0.60 / 1M                   | **$0.08 / 1M**               |
| **Цена (вывод)**       | $1.50 / 1M                   | $3.60 / 1M                   | **$0.18 / 1M**               |
| **Кэш**                | $0.05 / 1M                   | $0.20 / 1M                   | $0.016 / 1M                  |
| **Скорость (лучшая)**  | 0.49s (Mistral, P50)         | **0.53s** (Baseten, P50)     | **0.46s** (CoreWeave, P50)   |
| **Throughput**         | 41 ток/с                     | **98 ток/с** (Baseten)       | **89 ток/с** (Alibaba)       |
| **Supported params**   | structured_outputs, tools     | structured_outputs, tools    | reasoning_effort, tools      |

## Ключевые отличия от предыдущей версии сравнения

1. **Mistral Large 3 2512** — это совсем другая модель, не `mistral-large-2407`:
   - MoE архитектура (41B активных / 675B total) вместо dense 123B
   - Цена снижена в 4× (было $2/$6, стало $0.50/$1.50)
   - Apache 2.0 лицензия (было proprietary)
   - Мультимодальность: текст+изображения+файлы (было только файлы)
   - **Не поддерживает reasoning_effort**

2. **DeepSeek V4 Flash**:
   - Версия 0731 новее версии 0423 (в пикере как `deepseek/deepseek-v4-flash`)
   - Цена: $0.08/$0.18 (0731) vs $0.051/$0.103 (0423 на OpenRouter)
   - Через ClinePass действуют отдельные цены (дешевле)
   - **Поддерживает reasoning_effort**: none/low/medium/high/xhigh

3. **Nemotron-3-Ultra**:
   - Контекст зависит от endpoint: 512K (платный) или 1M (free)
   - Цена на OpenRouter: $0.60/$3.60 (не $0.50/$2.20 как на DeepInfra)
   - **Не поддерживает reasoning_effort**

## Источники
- OpenRouter API (22.08.2026): `curl -s "https://openrouter.ai/api/v1/models"`
- Mistral Large 3 2512: https://openrouter.ai/mistralai/mistral-large-2512
- Nemotron-3-Ultra: https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b
- DeepSeek V4 Flash 0731: https://openrouter.ai/deepseek/deepseek-v4-flash-0731
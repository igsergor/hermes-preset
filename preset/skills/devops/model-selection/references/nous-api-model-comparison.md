# Nous Inference API Model Comparison (Detailed)

**Last updated**: August 3, 2026 via direct API calls + HuggingFace model cards

---

## Models Compared

| Model | Provider | Total Params | Active Params | Architecture | Context | Modality |
|-------|----------|--------------|---------------|--------------|---------|----------|
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OpenRouter (via Nous Portal) | 550B | 55B | LatentMoE (Mamba-2 + MoE + Attention + MTP) | 1M | Text only |
| `stepfun/step-3.7-flash:free` | Nous Inference API | 198B (196B + 1.8B vision) | ~11B | Sparse MoE | 256K | **Text + Image + Video** |
| `tencent/hy3:free` | Nous Inference API | 295B | 21B (+ 3.8B MTP) | MoE | 256K | Text only |

---

## Artificial Analysis Index (OpenRouter data)

| Метрика | Nemotron-3-Ultra | Step-3.7-Flash | Hy3 |
|---------|-----------------|----------------|-----|
| **Intelligence Index** (общий IQ) | **37.8** 🥇 | 30.3 | *нет данных на OR* |
| **Coding Index** (кодинг) | **49.3** 🥇 | 39.6 | *нет данных на OR* |
| **Agentic Index** (агентские сценарии) | **27.4** 🥇 | 21.5 | *нет данных на OR* |

> Nemotron-3-Ultra лидирует во всех трёх индексах Artificial Analysis.

---

## Design Arena ELO (OpenRouter data — одинаковые категории)

| Категория | Nemotron-3-Ultra | Step-3.7-Flash | Hy3 |
|-----------|-----------------|----------------|-----|
| **codecategories** (кодинг) | 1156 (36.3%, #69) | **1203** (44.6%, #48) 🥇 | 1206 (41.1%, #45) 🥈 |
| **website** (веб-разработка) | 1131 (32.9%, #83) | **1212** (46.1%, #47) 🥇 | 1206 (41.4%, #53) 🥈 |
| **uicomponent** (UI компоненты) | 1180 (39.5%, #59) | **1202** (43.6%, #48) 🥇 | 1198 (40.2%, #52) 🥈 |
| **gamedev** (геймдев) | 1183 (38.8%, #60) | **1204** (41.9%, #46) 🥇 | 1189 (38.6%, #56) |
| **dataviz** (визуализация данных) | 1151 (37.6%, #71) | **1201** (45.8%, #48) 🥇 | 1154 (36.1%, #67) |
| **3d** | 1191 (41.6%, #49) | 1178 (41.7%, #54) | **1232** (43.8%, #37) 🥇 |

> Step-3.7-Flash выигрывает в вебе, UI, геймдеве, датавизе и кодинге по Design Arena.
> Hy3 лидирует в 3D.

---

## Ключевые бенчмарки из карточек моделей (HuggingFace README)

| Бенчмарк | Nemotron-3-Ultra | Step-3.7-Flash | Hy3 |
|----------|-----------------|----------------|-----|
| **SWE-Bench Verified** (реальные баги в репо) | **70.7** 🥇 | 56.3 | — |
| **SWE-Bench Multilingual** | 67.7 | — | — |
| **LiveCodeBench v6** | **89.0** 🥇 | — | — |
| **Terminal-Bench 2.1** (терминал/PC control) | 56.4 | **59.5** 🥇 | — |
| **ClawEval-1.1** (агентская надёжность) | — | **67.1 #1** 🥇 | — |
| **GPQA** (наука/рассуждения) | 87.0 | — | — |
| **MMLU-Pro** | 86.8 | — | — |
| **IMOAnswerBench (tools)** | 92.3 | — | — |
| **SimpleVQA (Search)** | — | **79.2 #1** 🥇 | — |
| **V* (Python)** | — | 95.3 (frontier) | — |
| **Экспертная слепая оценка (270 экспертов)** | — | — | **2.67/4** 🥇 (победил GLM-5.1 2.51) |
| **Галлюцинации (внутренние тесты)** | — | — | **5.4%** (было 12.5%) 🥇 |
| **Multi-turn issues** | — | — | **7.9%** (было 17.4%) 🥇 |

---

## Итог по критериям пользователя (агентские сценарии, управление ПК/браузером, кодинг)

| Критерий | Победитель | Почему |
|----------|-----------|--------|
| **Кодинг (SWE-Bench, LiveCodeBench)** | **Nemotron-3-Ultra** | 70.7% на SWE-Bench Verified, 89% на LiveCodeBench — максимальные результаты |
| **Агентские сценарии / управление ПК и браузером (Terminal-Bench, ClawEval)** | **Step-3.7-Flash** | #1 на ClawEval (67.1), лучше на Terminal-Bench (59.5) — это именно управление компьютером/браузером |
| **Веб-разработка / UI / фронтенд (Design Arena)** | **Step-3.7-Flash** | Выигрывает в website, uicomponent, gamedev, dataviz |
| **Надёжность в продакшене / мало галлюцинаций / мультитёрн** | **Hy3** | Эксперты поставили выше GLM-5.1, галлюцинации 5.4%, multi-turn issues 7.9% |
| **Общий IQ / рассуждения (Artificial Analysis)** | **Nemotron-3-Ultra** | 37.8 vs 30.3 |

---

## Рекомендация для конкретных задач

| Задача | Лучший выбор | Команда переключения |
|--------|--------------|---------------------|
| Сложный кодинг, SWE-Bench, 1M контекст | Nemotron-3-Ultra (OpenRouter) | `/model nvidia/nemotron-3-ultra-550b-a55b:free --global` |
| Управление браузером, ПК, терминал, UI-автоматизация | Step-3.7-Flash (Nous API) | `hermes chat --provider nous --model stepfun/step-3.7-flash:free` |
| Продакшн-надёжность, мало галлюцинаций, русский/китайский | Hy3 (Nous API) | `hermes chat --provider nous --model tencent/hy3:free` |
| Мультимодальное (видео/изображения) | Step-3.7-Flash (единственная с vision) | `hermes chat --provider nous --model stepfun/step-3.7-flash:free` |

---

## Quick Test Commands

```bash
# Test Nemotron-3-Ultra (OpenRouter)
hermes chat -q "test" --provider openrouter --model nvidia/nemotron-3-ultra-550b-a55b:free

# Test Step-3.7-Flash (Nous API)
hermes chat -q "test" --provider nous --model stepfun/step-3.7-flash:free

# Test Hy3 (Nous API)
hermes chat -q "test" --provider nous --model tencent/hy3:free

# List all Nous API models
curl -s https://inference-api.nousresearch.com/v1/models | jq -r '.data[].id'
```

---

## Источники данных

1. **OpenRouter API** — `curl https://openrouter.ai/api/v1/models` (Artificial Analysis index, Design Arena ELO, pricing, specs)
2. **HuggingFace Model Cards** — raw README.md для каждой модели:
   - `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16` (технический отчёт NVIDIA)
   - `stepfun-ai/Step-3.7-Flash` (блог StepFun + карточка)
   - `tencent/Hy3` (карточка Tencent Hy Team)
3. **Nous Inference API** — `curl https://inference-api.nousresearch.com/v1/models` (каталог моделей и бесплатные тарифы)
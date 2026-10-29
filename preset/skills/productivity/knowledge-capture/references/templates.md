# Knowledge Capture Templates Reference

Все шаблоны хранятся в `Templates/` папке vault и используются скриптом автозахвата.

---

## 📝 Session Capture.md
**Использование**: Автоматически создается при автозахвате сессий Hermes

```markdown
---
tags: [session, capture, knowledge, hermes]
created: {{date}}
source: "hermes"
session_id: "{{session_id}}"
platform: "{{platform}}"
thread: "{{thread}}"
chat_id: "{{chat_id}}"
model: "{{model}}"
duration_minutes: {{duration}}
message_count: {{message_count}}
---

# 📝 Session Capture: {{title}}

**Session**: `{{session_id}}` | **Date**: {{date}} | **Platform**: {{platform}} | **Thread**: {{thread}} | **Duration**: {{duration}} min | **Messages**: {{message_count}}

## 🎯 Цель сессии
{{goal}}

## 📋 Ход работы
{{work_log}}

## 🛠 Использованные навыки (skills)
{{skills_used}}

## 💡 Ключевые инсайты / Решения
{{insights}}

## ⚠️ Проблемы и как решены
{{problems}}

## 🔗 Связанные заметки
{{links}}

## 📎 Артефакты
{{artifacts}}

## 🔄 Следующие шаги
{{next_steps}}

---

*Автоматически захвачено из Hermes Agent (state.db). Обработать при еженедельном обзоре.*
```

**Переменные**: `{{date}}`, `{{session_id}}`, `{{title}}`, `{{platform}}`, `{{thread}}`, `{{chat_id}}`, `{{model}}`, `{{duration}}`, `{{message_count}}`, `{{goal}}`, `{{work_log}}`, `{{skills_used}}`, `{{insights}}`, `{{problems}}`, `{{links}}`, `{{artifacts}}`, `{{next_steps}}`

**Папка назначения**: `Inbox/`

---

## 📚 Knowledge Entry.md
**Использование**: Ручное или полуавтоматическое добавление в базу знаний

```markdown
---
tags: [knowledge, entry, project, reference]
created: {{date}}
project: "{{project}}"
category: "{{category}}"
source: "{{source}}"
status: "active"
---

# 📚 Knowledge: {{title}}

**Project**: `{{project}}` | **Category**: {{category}} | **Date**: {{date}}

## 📌 Суть
{{essence}}

## 📝 Детали
{{details}}

## 🔧 Технические детали
```bash
{{tech_details}}
```

## 💡 Применение
{{application}}

## ⚠️ Подводные камни / Gotchas
{{gotchas}}

## 🔗 Связи
- [[Projects/{{project}}]]
- [[Resources/]]
- #knowledge/{{category}}

## 📚 Источники
{{sources}}

---

*Добавлено в базу знаний. Актуальность проверять при использовании.*
```

**Переменные**: `{{date}}`, `{{title}}`, `{{project}}`, `{{category}}`, `{{source}}`, `{{essence}}`, `{{details}}`, `{{tech_details}}`, `{{application}}`, `{{gotchas}}`, `{{sources}}`

**Папка назначения**: `Resources/`

**CLI**:
```bash
python3 auto-capture-obsidian.py --knowledge \
  --title "Pattern Name" \
  --project "Project Name" \
  --category "setup|automation|debugging|research" \
  --essence "One-line summary" \
  --details "Full details" \
  --tech "Commands, configs, code" \
  --application "When/how to use" \
  --gotchas "Pitfalls"
```

---

## 🔄 Weekly Review.md
**Использование**: Еженедельный обзор (cron по понедельникам 10:00)

```markdown
---
tags: [weekly, review, process, hermes]
created: {{date}}
week: "{{week}}
---

# 🔄 Weekly Review: Week {{week}} ({{date}})

## 📊 Статистика за неделю
- Сессий Hermes: 
- Заметок создано в vault: 
- Проектов обновлено: 
- Задач закрыто: 

---

## 1. 📥 Inbox → PARA Processing
*Разобрать всё из Inbox (5-10 мин)*

### Session Captures (автозахваченные)
- [ ] 
- [ ] 

### Knowledge Entries (ручные)
- [ ] 

### Быстрые захваты (Inbox Capture)
- [ ] 

**Действие для каждого**: Project / Area / Resource / Archive / Delete

---

## 2. 🎯 Projects Review
*Обновить статус, перенести завершенные в Archives*

| Проект | Статус | Прогресс | Следующий шаг |
|--------|--------|----------|---------------|
|  |  |  |  |

---

## 3. 🏢 Areas Check
*Проверить регулярные действия по областям*

| Область | Регулярное действие | Сделано? | Примечание |
|---------|---------------------|----------|------------|
| Home & Family |  | [ ] |  |
| Development & Tech |  | [ ] |  |
| Health & Fitness |  | [ ] |  |
| Finances |  | [ ] |  |

---

## 4. 📅 Calendar & Planning
*Планировать следующую неделю*

### Приоритеты на следующую неделю:
1. 
2. 
3. 

### Блокеры / Зависимости:
- 

---

## 5. 📝 Daily Notes Review
*Просмотреть daily notes за неделю, вынести важное*

### Ключевые инсайты недели:
- 

### Паттерны / Тренды:
- 

---

## 6. 🧠 Knowledge Base Health
*Состояние базы знаний*

- [ ] Теги актуальны
- [ ] Ссылки между проектами/ресурсами работают
- [ ] Дубликаты объединены
- [ ] Старые заметки в Archives актуальны

---

## 7. 🤖 Hermes & Automation
*Проверка автоматизаций*

- [ ] Auto-capture cron job работает (проверить Inbox)
- [ ] Dashboard доступен
- [ ] VPN/доступ с телефона работает
- [ ] Backups vault в порядке

---

## 📋 Action Items на неделю
- [ ] 
- [ ] 
- [ ] 

---

*Шаблон: Weekly Review.md | Обрабатывать еженедельно (понедельник/воскресенье)*
```

**Переменные**: `{{date}}`, `{{week}}`

**Папка назначения**: `Daily/`

**CLI**:
```bash
# Через obsidian-vault CLI
obsidian new -t weekly "Week 33 Review"

# Через автозахват скрипт
python3 auto-capture-obsidian.py --weekly
```

---

## 📋 Frontmatter Standards

Рекомендуемые поля для всех заметок:

```yaml
---
title: "Название"           # Обязательно для проектов/встреч
created: 2026-08-12       # ISO дата создания
tags: [tag1, tag2]        # Массив тегов
status: active            # active | done | on-hold | cancelled
priority: high            # high | medium | low
area: "Development"       # Связанная область (для проектов)
project: "Project Name"   # Связанный проект (для задач/ресурсов)
---
```

Теги лучше держать в массиве `[tag1, tag2]` для корректного парсинга.

---

## 🔧 Добавление своих шаблонов

1. Создайте `.md` файл в `Templates/`
2. Используйте переменные:
   - `{{title}}` — заголовок (передается через CLI)
   - `{{date:YYYY-MM-DD}}` — текущая дата
   - `{{date:dddd}}` — день недели
   - `{{time:HH:mm}}` — текущее время
   - `{{любая_переменная}}` — передается через `--key value` в CLI
3. Добавьте запись в `TEMPLATES` словарь в парсере
# Obsidian Vault Templates Reference

Все шаблоны хранятся в `Templates/` папке vault.

---

## 📅 Daily Note.md
**Использование**: Автоматически создается для ежедневных заметок

```markdown
---
date: {{date:YYYY-MM-DD}}
day: {{date:dddd}}
tags: [daily]
---

# {{date:YYYY-MM-DD}}, {{date:dddd}}

## 📅 План на день
- [ ] 
- [ ] 
- [ ] 

## 📝 Заметки
<!-- Ссылки на встречи, идеи, мысли -->

## ✅ Выполнено
- 

## 🔄 В процессе
- 

## 💡 Идеи / Мысли
- 

## 📊 Метрики
- Сон: 
- Спорт: 
- Чтение: 
- Код: 

## 🔗 Связанные заметки
- 
```

**Переменные**: `{{date:YYYY-MM-DD}}`, `{{date:dddd}}`

---

## 🎯 Project.md
**Использование**: `obsidian new -t Project "Название проекта"`

```markdown
---
title: "{{title}}"
status: "active"
priority: "high"
created: {{date:YYYY-MM-DD}}
tags: [project]
---

# {{title}}

## 🎯 Цель
<!-- Чего хотим достичь -->

## 📋 Задачи
- [ ] 
- [ ] 
- [ ] 

## 📦 Ресурсы
<!-- Ссылки, документы, люди -->

## 📝 Заметки
<!-- Ход работы, решения, проблемы -->

## ✅ Критерии завершения
- [ ] 

## 🔗 Связанные проекты
- 
```

**Переменные**: `{{title}}`, `{{date:YYYY-MM-DD}}`
**Папка назначения**: `Projects/`

---

## 🤝 Meeting.md
**Использование**: `obsidian new -t Meeting "Название встречи"`

```markdown
---
date: {{date:YYYY-MM-DD}}
time: {{time:HH:mm}}
attendees: []
tags: [meeting]
---

# Встреча: {{title}} — {{date:YYYY-MM-DD}}

## Участники
- 

## Повестка
1. 
2. 
3. 

## Ключевые решения
- 

## Действия (Action Items)
- [ ]  — @ответственный — срок:
- [ ]  — @ответственный — срок:

## Заметки
<!-- Подробности обсуждения -->

## Следующая встреча
- Дата: 
- Тема: 
```

**Переменные**: `{{title}}`, `{{date:YYYY-MM-DD}}`, `{{time:HH:mm}}`

---

## 📝 Note.md
**Использование**: `obsidian new -t Note "Название заметки"`

```markdown
---
title: "{{title}}"
created: {{date:YYYY-MM-DD}}
tags: []
---

# {{title}}

## 📌 Основная мысль
<!-- Одна фраза, суть заметки -->

## 📝 Содержание
<!-- Детали, аргументы, примеры -->

## 🔗 Связи
- [[Связанная заметка]]
- #тег

## 📚 Источники
- 
```

**Переменные**: `{{title}}`, `{{date:YYYY-MM-DD}}`

---

## 📥 Inbox Capture.md
**Использование**: `obsidian new -t Inbox "Краткая мысль"` или автоматически из Telegram

```markdown
---
tags: [inbox, capture]
created: {{date:YYYY-MM-DD}}
source: "telegram"
---

# 📥 Inbox: {{title}}

## 💡 Суть
<!-- Что пришло в голову, одна фраза -->

## 📝 Детали
<!-- Подробности, контекст, ссылки -->

## 🏷 Теги
#inbox #capture

## 🔄 Обработка (PARA)
- [ ] **Проект** → переместить в `Projects/`
- [ ] **Область** → переместить в `Areas/`
- [ ] **Ресурс** → переместить в `Resources/`
- [ ] **Архив** → переместить в `Archives/`
- [ ] **Удалить** — не актуально

## 🔗 Связи
- [[Связанная заметка]]
- 

---
*Создано автоматически из Telegram. Обработать при еженедельном обзоре.*
```

**Переменные**: `{{title}}`, `{{date:YYYY-MM-DD}}`
**Папка назначения**: `Inbox/`

---

## 🔧 Добавление своих шаблонов

1. Создайте `.md` файл в `Templates/`
2. Используйте переменные:
   - `{{title}}` — заголовок (передается через CLI)
   - `{{date:YYYY-MM-DD}}` — текущая дата
   - `{{date:dddd}}` — день недели
   - `{{time:HH:mm}}` — текущее время
   - `{{любая_переменная}}` — передается через `--key value` в CLI

3. Добавьте запись в `TEMPLATES` словарь в `scripts/obsidian-cli.py`:
   ```python
   TEMPLATES = {
       "daily": "Daily Note.md",
       "project": "Project.md",
       "meeting": "Meeting.md",
       "note": "Note.md",
       "inbox": "Inbox Capture.md",
       "your-template": "Your Template.md",  # добавьте здесь
   }
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
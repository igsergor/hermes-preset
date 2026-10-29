# Network Access to Obsidian Vault

## Samba (SMB/CIFS) — для сетевого диска на Windows

### Настройка на сервере (требует sudo)

```bash
# 1. Установить Samba (если не установлен)
sudo apt-get update && sudo apt-get install -y samba

# 2. Задать SMB пароль для пользователя igor
sudo smbpasswd -a igor
# Пароль: *** (два раза)

# 3. Применить конфиг для obsidian-vault
sudo cp ~/smb.conf.obsidian /etc/samba/smb.conf
sudo testparm -s

# 4. Перезапустить сервисы
sudo systemctl restart smbd nmbd
sudo systemctl enable smbd nmbd
```

### Конфиг `~/smb.conf.obsidian`

Также доступен как шаблон: `templates/smb.conf.obsidian`

```ini
[global]
   workgroup = WORKGROUP
   server string = Hermes Server
   netbios name = HERMES-SERVER
   security = user
   map to guest = bad user
   dns proxy = no
   bind interfaces only = yes
   interfaces = lo enp1s0
   log file = /var/log/samba/log.%m
   max log size = 1000
   logging = file
   panic action = /usr/share/samba/panic-action %d
   
   # Performance
   socket options = TCP_NODELAY IPTOS_LOWDELAY SO_RCVBUF=8192 SO_SNDBUF=8192
   read raw = yes
   write raw = yes
   max xmit = 65535
   dead time = 15
   getwd cache = yes
   
   # VFS modules for better macOS/Windows compatibility
   vfs objects = catia fruit streams_xattr
   fruit:metadata = stream
   fruit:model = MacSamba
   fruit:posix_rename = yes
   fruit:veto_appledouble = no
   fruit:wipe_intentionally_left_blank_rfork = yes
   fruit:delete_empty_adfiles = yes

[obsidian-vault]
   path = ~/obsidian-vault
   browseable = yes
   read only = no
   guest ok = no
   create mask = 0664
   directory mask = 0775
   force create mode = 0664
   force directory mode = 0775
   valid users = igor
   write list = igor
   # File locking for concurrent access
   oplocks = yes
   level2 oplocks = yes
   locking = yes
   # Case sensitivity
   preserve case = yes
   short preserve case = yes
   case sensitive = no
   # Veto files that could cause issues
   veto files = /._*/.DS_Store/.Trashes/Thumbs.db/~*/
   delete veto files = yes
```

### Подключение на Windows

1. `Win+R` → `\\192.168.1.10\obsidian-vault`
2. Логин: `igor`, Пароль: `***`
3. Или подключить как сетевой диск:
   - Проводник → Этот компьютер → Подключить сетевой диск
   - Диск: `Z:`, Папка: `\\192.168.1.10\obsidian-vault`
   - ✅ "Подключать при входе в систему"

### В Obsidian на Windows

File → Open vault → выбери сетевой диск/папку `Z:\` или `\\192.168.1.10\obsidian-vault`

---

## Syncthing (рекомендуется) — настоящая синхронизация

### Преимущества перед Samba

- ✅ Офлайн-работа (синхронизируется при появлении сети)
- ✅ Нет блокировок файлов (конфликты решаются автоматически)
- ✅ Быстрее (локальные файлы, не сетевые)
- ✅ История версий (File Versioning)
- ✅ Работает через NAT/фаерволы без проброса портов

### Настройка на сервере

```bash
# Установка
sudo apt install syncthing

# Запуск от пользователя igor (не root!)
systemctl --user enable syncthing
systemctl --user start syncthing

# Веб-UI доступен на http://192.168.1.10:8384
# Или через SSH туннель: ssh -L 8384:127.0.0.1:8384 igor@192.168.1.10
```

### Настройка в веб-UI (порт 8384)

1. **Actions** → **Settings** → **GUI** → Authentication: задать пользователь/пароль
2. **Add Folder** → Label: "obsidian-vault", Path: `~/obsidian-vault`
3. **Sharing** → добавить Device ID Windows-машины
4. **Advanced** → File Versioning: "Simple File Versioning" (keep 5 versions)

### Настройка на Windows

1. Установить Syncthing: https://syncthing.net/downloads/
2. Запустить, открыть веб-UI (обычно http://127.0.0.1:8384)
3. **Add Device** → ввести Device ID сервера
4. Принять папку "obsidian-vault", выбрать локальный путь (например `C:\Users\user\ObsidianVault`)

### В Obsidian на Windows

File → Open vault → выбери локальную папку `C:\Users\user\ObsidianVault`

---

## Сравнение

| Критерий | Samba | Syncthing |
|----------|-------|-----------|
| Офлайн доступ | ❌ | ✅ |
| Скорость | Сетевая | Локальная |
| Конфликты файлов | Блокировки | Авто-решение |
| История версий | ❌ | ✅ (настраиваемая) |
| Настройка | Проще (один раз) | Чуть сложнее |
| Требования к сети | Порт 445 открыт | Любая сеть (relay) |
| Рекомендация | Для быстрого просмотра | Для постоянной работы |

**Рекомендация**: Использовать Syncthing для основной работы, Samba — как запасной вариант для разового доступа.
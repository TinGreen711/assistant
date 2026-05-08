import random
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Any, Optional

from config import ASSISTANT_DB_PATH, USER_TIMEZONE

TZ = ZoneInfo(USER_TIMEZONE)

TASK_TOPICS: Dict[str, str] = {
    "linux": "Linux",
    "networks": "Сети",
    "docker": "Docker",
    "git": "Git",
    "bash": "Bash",
    "systemd": "systemd",
    "nginx": "Nginx",
    "monitoring": "Мониторинг",
    "cicd": "CI/CD",
}

TASKS: Dict[str, List[Dict[str, Any]]] = {
    "linux": [
        {
            "title": "Топ процессов по памяти",
            "description": "Найди 5 процессов, которые потребляют больше всего оперативной памяти на твоём сервере.",
            "command": "ps aux --sort=-%mem | head -6",
            "hint": "`--sort=-%mem` сортирует по %MEM убыванием. `head -6` — первая строка заголовок + 5 процессов.",
            "verify": "Какой процесс занял первое место по памяти?",
        },
        {
            "title": "Свободное место на диске",
            "description": "Проверь использование дискового пространства. Найди раздел с наименьшим свободным местом.",
            "command": "df -h",
            "hint": "Колонка `Use%` показывает процент использования. Колонка `Avail` — свободное место.",
            "verify": "Сколько свободного места на корневом разделе (/)?",
        },
        {
            "title": "Открытые порты сервера",
            "description": "Посмотри какие порты сейчас слушает твой сервер и какие процессы их держат.",
            "command": "ss -tlnp",
            "hint": "`-t` TCP, `-l` listening, `-n` числовые порты, `-p` показать процесс. Найди порт 22 (SSH) и порт своего бота.",
            "verify": "Какие порты слушает твой сервер? Нашёл порт Telegram-бота?",
        },
        {
            "title": "Большие файлы в системе",
            "description": "Найди файлы больше 50MB на сервере. Это помогает найти что занимает место на диске.",
            "command": "find /var /home /tmp -size +50M -type f 2>/dev/null",
            "hint": "`-size +50M` — больше 50 мегабайт. `-type f` — только файлы. `2>/dev/null` — скрыть ошибки доступа.",
            "verify": "Нашёл что-то крупное? Что это за файлы?",
        },
        {
            "title": "История входов на сервер",
            "description": "Посмотри кто и когда последний раз заходил на сервер по SSH.",
            "command": "last | head -15",
            "hint": "`last` читает /var/log/wtmp — журнал входов/выходов. Видишь свой IP-адрес в колонке?",
            "verify": "С какого IP последний раз был вход на сервер?",
        },
        {
            "title": "Права доступа к файлам",
            "description": "Посмотри права на важные файлы. Найди файлы в /etc/ которые читает только root.",
            "command": "ls -la /etc/shadow /etc/passwd /etc/sudoers",
            "hint": "Первый символ `-` = файл, `d` = папка. Потом три тройки: владелец/группа/остальные. `r`=чтение, `w`=запись, `x`=исполнение.",
            "verify": "Кто может читать /etc/shadow? Почему это важно?",
        },
    ],
    "networks": [
        {
            "title": "DNS резолвинг",
            "description": "Проверь как твой сервер разрешает DNS-имена. Узнай IP-адрес google.com через DNS.",
            "command": "dig google.com +short",
            "hint": "Если `dig` не установлен: `nslookup google.com`. `+short` выводит только IP без лишнего.",
            "verify": "Какой IP-адрес вернул DNS для google.com?",
        },
        {
            "title": "Таблица маршрутизации",
            "description": "Посмотри через какой шлюз твой сервер выходит в интернет.",
            "command": "ip route",
            "hint": "Строка `default via X.X.X.X` — это твой шлюз (gateway). Через него идёт весь трафик в интернет.",
            "verify": "Какой IP-адрес твоего шлюза (default gateway)?",
        },
        {
            "title": "Трассировка маршрута",
            "description": "Посмотри через какие узлы проходят пакеты от твоего сервера до 8.8.8.8 (DNS Google).",
            "command": "traceroute -n 8.8.8.8",
            "hint": "Если не установлен: `apt install traceroute`. `-n` не резолвит имена, быстрее. Каждая строка — один промежуточный узел (hop).",
            "verify": "Сколько хопов до 8.8.8.8? Где теряются пакеты (если теряются)?",
        },
        {
            "title": "Сетевые интерфейсы",
            "description": "Посмотри все сетевые интерфейсы сервера: локальный IP, MAC-адрес, статус.",
            "command": "ip addr show",
            "hint": "`lo` — loopback (127.0.0.1). Остальные — реальные интерфейсы. `inet` = IPv4 адрес. `state UP` = активен.",
            "verify": "Какой у сервера локальный IP-адрес? (должен быть 192.168.1.92)",
        },
        {
            "title": "Активные соединения",
            "description": "Посмотри активные TCP-соединения сервера прямо сейчас.",
            "command": "ss -tn state established",
            "hint": "`established` — только активные соединения. Увидишь SSH-сессию со своего компьютера/телефона.",
            "verify": "Нашёл своё SSH-соединение в списке?",
        },
    ],
    "docker": [
        {
            "title": "Запусти первый контейнер",
            "description": "Запусти официальный тестовый контейнер Docker. Он проверит что Docker работает правильно.",
            "command": "docker run hello-world",
            "hint": "Docker скачает образ hello-world (~13KB) и запустит. Увидишь приветственное сообщение. Если docker не установлен: `apt install docker.io`.",
            "verify": "Увидел 'Hello from Docker!'? Что ещё написано в выводе?",
        },
        {
            "title": "Инспекция контейнеров",
            "description": "Посмотри все контейнеры на сервере, включая остановленные.",
            "command": "docker ps -a",
            "hint": "Колонка STATUS: `Up` = запущен, `Exited` = остановлен. `PORTS` = проброшенные порты. `NAMES` = имя контейнера.",
            "verify": "Сколько контейнеров на сервере? Какие запущены прямо сейчас?",
        },
        {
            "title": "Использование диска Docker",
            "description": "Docker накапливает образы, контейнеры, volumes. Проверь сколько места он занимает.",
            "command": "docker system df",
            "hint": "Images, Containers, Volumes, Build Cache — четыре категории. `RECLAIMABLE` — что можно очистить командой `docker system prune`.",
            "verify": "Сколько места занимает Docker на твоём сервере?",
        },
        {
            "title": "Логи контейнера",
            "description": "Посмотри последние 20 строк логов своего assistant-контейнера, или любого другого запущенного.",
            "command": "docker logs --tail 20 $(docker ps -q | head -1)",
            "hint": "Если нет запущенных контейнеров — сначала запусти: `docker run -d nginx`. `$(docker ps -q | head -1)` подставляет ID первого контейнера.",
            "verify": "Что выводит контейнер в логи?",
        },
        {
            "title": "Запусти nginx в контейнере",
            "description": "Запусти веб-сервер nginx в контейнере и проверь что он отвечает.",
            "command": "docker run -d -p 8080:80 --name test-nginx nginx && curl http://localhost:8080",
            "hint": "`-d` = фон, `-p 8080:80` = порт 8080 хоста → порт 80 контейнера. После теста удали: `docker rm -f test-nginx`.",
            "verify": "Увидел HTML-ответ от nginx? Что там написано?",
        },
    ],
    "git": [
        {
            "title": "Настрой git на сервере",
            "description": "Проверь и настрой своё имя и email в git. Они будут видны в каждом коммите.",
            "command": "git config --global user.name && git config --global user.email",
            "hint": "Если пусто — настрой: `git config --global user.name 'Tin Green'` и `git config --global user.email 'your@email.com'`.",
            "verify": "Какое имя и email настроены в git?",
        },
        {
            "title": "Клонируй свой репозиторий",
            "description": "Склонируй свой репозиторий assistant в новую папку и посмотри историю коммитов.",
            "command": "git clone https://github.com/TinGreen711/assistant /tmp/assistant-clone && cd /tmp/assistant-clone && git log --oneline -10",
            "hint": "`git log --oneline` — компактная история. Каждая строка: короткий хэш + сообщение коммита. После теста: `rm -rf /tmp/assistant-clone`.",
            "verify": "Сколько коммитов в репозитории? Что написано в последнем?",
        },
        {
            "title": "Создай ветку и сделай коммит",
            "description": "В папке своего проекта создай новую ветку, измени любой файл и сделай коммит.",
            "command": "cd ~/assistant && git checkout -b test-branch && echo '# test' >> README.md && git add README.md && git commit -m 'test commit' && git checkout main && git branch -D test-branch",
            "hint": "`checkout -b` создаёт и переключает на ветку. `-D` удаляет ветку. Весь процесс безопасен — не трогает main.",
            "verify": "Получилось создать коммит в отдельной ветке?",
        },
        {
            "title": "Посмотри что изменено",
            "description": "В своём проекте посмотри текущий статус и разницу между последними коммитами.",
            "command": "cd ~/assistant && git status && git log --oneline -5",
            "hint": "`git status` — что изменено сейчас. `git diff HEAD~1` — разница с предыдущим коммитом. `git show` — детали последнего коммита.",
            "verify": "Есть ли несохранённые изменения в проекте прямо сейчас?",
        },
        {
            "title": "Изучи .gitignore проекта",
            "description": "Посмотри что игнорируется в твоём проекте. Добавь новое правило если нужно.",
            "command": "cd ~/assistant && cat .gitignore 2>/dev/null || echo 'файл не найден' && git status --short",
            "hint": "Если .gitignore нет — создай: `echo '.env' > .gitignore && echo '__pycache__/' >> .gitignore`. Файлы в .gitignore не попадают в git.",
            "verify": "Что сейчас игнорируется в проекте? Есть ли файлы которые нужно добавить в .gitignore?",
        },
    ],
    "bash": [
        {
            "title": "Скрипт проверки диска",
            "description": "Напиши простой bash-скрипт который проверяет свободное место и предупреждает если меньше 20%.",
            "command": 'echo \'#!/bin/bash\nUSAGE=$(df / | tail -1 | awk \'{print $5}\' | tr -d %)\nif [ $USAGE -gt 80 ]; then\n  echo "ВНИМАНИЕ: диск заполнен на $USAGE%"\nelse\n  echo "OK: диск заполнен на $USAGE%"\nfi\' > /tmp/check_disk.sh && chmod +x /tmp/check_disk.sh && /tmp/check_disk.sh',
            "hint": "`awk '{print $5}'` берёт 5-ю колонку (Use%). `tr -d %` убирает знак процента. `[ $USAGE -gt 80 ]` — условие больше 80.",
            "verify": "Скрипт запустился? Что он вывел о состоянии диска?",
        },
        {
            "title": "Переменные и подстановка",
            "description": "Исследуй переменные окружения своего сервера.",
            "command": "echo \"Пользователь: $USER\" && echo \"Домашняя папка: $HOME\" && echo \"Оболочка: $SHELL\" && echo \"Путь: $PATH\"",
            "hint": "Переменные в двойных кавычках раскрываются. `env` покажет все переменные окружения. `printenv HOME` — конкретную переменную.",
            "verify": "Какая оболочка ($SHELL) используется на сервере?",
        },
        {
            "title": "Перенаправление вывода",
            "description": "Запусти несколько команд и сохрани их вывод и ошибки в файл.",
            "command": "ls /home /nonexistent > /tmp/output.txt 2>&1 && cat /tmp/output.txt",
            "hint": "`>` перезаписывает файл. `>>` добавляет. `2>&1` — stderr в stdout. `2>/dev/null` — выбросить ошибки.",
            "verify": "Что попало в файл? Видишь содержимое /home и ошибку о /nonexistent?",
        },
        {
            "title": "Цикл for в bash",
            "description": "Создай цикл который выводит информацию о нескольких файлах.",
            "command": "for f in /etc/passwd /etc/hostname /etc/os-release; do echo \"=== $f ===\"; head -3 $f; done",
            "hint": "`for f in ...` перебирает список. `do ... done` — тело цикла. `$f` — текущий элемент. Можно использовать `$(ls /etc/*.conf)` для динамического списка.",
            "verify": "Что вывел цикл? Как выглядит начало /etc/os-release?",
        },
        {
            "title": "Скрипт с аргументами",
            "description": "Напиши скрипт который принимает имя сервиса как аргумент и показывает его статус.",
            "command": "echo '#!/bin/bash\nSERVICE=${1:-assistant}\necho \"Проверяю сервис: $SERVICE\"\nsystemctl is-active $SERVICE && echo \"ЗАПУЩЕН\" || echo \"НЕ ЗАПУЩЕН\"' > /tmp/check_service.sh && chmod +x /tmp/check_service.sh && /tmp/check_service.sh assistant",
            "hint": "`${1:-assistant}` — первый аргумент, если нет — значение по умолчанию 'assistant'. `&&` выполняет если успех, `||` — если ошибка.",
            "verify": "Скрипт показал что assistant запущен?",
        },
    ],
    "systemd": [
        {
            "title": "Детальный статус сервиса",
            "description": "Посмотри подробный статус своего assistant.service и разберись что значит каждая строка.",
            "command": "systemctl status assistant.service",
            "hint": "Важные строки: `Active:` (состояние), `Main PID:` (процесс), `Memory:` (потребление RAM), последние строки — свежие логи.",
            "verify": "Сколько памяти потребляет assistant.service? Когда последний раз перезапускался?",
        },
        {
            "title": "Логи за последний час",
            "description": "Посмотри что писал твой бот в лог за последний час.",
            "command": "journalctl -u assistant.service --since '1 hour ago' --no-pager",
            "hint": "`--since` принимает: '1 hour ago', '2024-01-01', 'today'. `--until` — конец периода. `-n 50` — последние 50 строк.",
            "verify": "Какие события были за последний час? Были ли ошибки (ERROR)?",
        },
        {
            "title": "Сервисы в автозапуске",
            "description": "Посмотри какие сервисы включены в автозапуск при загрузке сервера.",
            "command": "systemctl list-unit-files --state=enabled --type=service",
            "hint": "`enabled` — стартует при загрузке. `disabled` — не стартует. `static` — запускается другим юнитом. Найди assistant.service в списке.",
            "verify": "assistant.service есть в автозапуске?",
        },
        {
            "title": "Ошибки в системных логах",
            "description": "Найди ошибки и критические сообщения в системном журнале за сегодня.",
            "command": "journalctl -p err --since today --no-pager | tail -20",
            "hint": "`-p err` — приоритет error и выше (err, crit, alert, emerg). `-p warning` — включит также предупреждения.",
            "verify": "Есть ли ошибки сегодня? Что за сервисы их генерируют?",
        },
        {
            "title": "Время загрузки системы",
            "description": "Узнай сколько времени занимает загрузка сервера и какие сервисы грузятся дольше всего.",
            "command": "systemd-analyze && systemd-analyze blame | head -10",
            "hint": "`systemd-analyze` — общее время загрузки. `blame` — топ сервисов по времени старта. Долгий старт часто из-за сетевых таймаутов.",
            "verify": "Сколько секунд загружается сервер? Какой сервис стартует дольше всего?",
        },
    ],
    "nginx": [
        {
            "title": "Установи и запусти Nginx",
            "description": "Установи Nginx на сервер, запусти и проверь что он отвечает на запросы.",
            "command": "apt install -y nginx && systemctl start nginx && curl http://localhost",
            "hint": "Если nginx уже установлен — просто `curl http://localhost`. Должна вернуться стандартная страница 'Welcome to nginx!'.",
            "verify": "Nginx ответил? Что написано на странице?",
        },
        {
            "title": "Конфигурация Nginx",
            "description": "Изучи структуру конфигурации Nginx: главный файл и папки с настройками сайтов.",
            "command": "cat /etc/nginx/nginx.conf | head -30 && ls /etc/nginx/sites-enabled/",
            "hint": "sites-available — все конфиги. sites-enabled — активные (симлинки на sites-available). `include` в nginx.conf подключает дополнительные файлы.",
            "verify": "Сколько сайтов в sites-enabled? Что подключает главный nginx.conf?",
        },
        {
            "title": "Проверь конфиг и перезагрузи",
            "description": "Проверь синтаксис конфигурации Nginx и перезагрузи без прерывания соединений.",
            "command": "nginx -t && systemctl reload nginx && echo 'OK — nginx перезагружен'",
            "hint": "`nginx -t` проверяет синтаксис. Если ошибка — покажет строку. `reload` мягче чем `restart` — без прерывания соединений.",
            "verify": "nginx -t показал 'syntax is ok'?",
        },
        {
            "title": "Логи доступа Nginx",
            "description": "Посмотри кто обращается к твоему Nginx в реальном времени. Запусти в одном терминале, в другом — curl.",
            "command": "tail -f /var/log/nginx/access.log",
            "hint": "Формат: IP — — [дата] \"метод URL\" код_ответа размер. Код 200 = OK, 404 = не найдено, 301/302 = редирект. Ctrl+C для выхода.",
            "verify": "Видишь запросы в логе? Попробуй зайти на http://192.168.1.92 с телефона.",
        },
        {
            "title": "Создай простой сайт",
            "description": "Создай свою HTML-страницу и настрой Nginx отдавать её.",
            "command": "echo '<h1>Привет от Тина!</h1>' > /var/www/html/index.html && curl http://localhost",
            "hint": "/var/www/html/ — корневая папка для файлов по умолчанию. В конфиге это `root /var/www/html;`. Nginx отдаёт index.html автоматически.",
            "verify": "Nginx вернул твою страницу с 'Привет от Тина!'?",
        },
    ],
    "monitoring": [
        {
            "title": "Проверь uptime сервера",
            "description": "Узнай как долго сервер работает без перезагрузки и текущую нагрузку.",
            "command": "uptime && uptime -p",
            "hint": "`uptime` выводит: текущее время, время работы, кол-во пользователей, load average (1/5/15 минут). Load average > числа CPU = перегрузка.",
            "verify": "Сколько времени сервер работает без перезагрузки? Какой load average?",
        },
        {
            "title": "Использование памяти",
            "description": "Детально проверь состояние оперативной памяти: что занято, что свободно, swap.",
            "command": "free -h && echo '---' && cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree'",
            "hint": "`available` ≠ `free`. Available — реально доступно включая кэш который можно освободить. free — физически не используется.",
            "verify": "Сколько RAM доступно реально? Используется ли swap?",
        },
        {
            "title": "Нагрузка на CPU",
            "description": "Посмотри загрузку CPU за последние секунды в реальном времени.",
            "command": "vmstat 1 5",
            "hint": "Колонки: `us` user, `sy` system, `id` idle (свободный), `wa` wait IO. `id` близко к 100 = CPU почти свободен. `r` в начале = процессы в очереди на CPU.",
            "verify": "Какой процент CPU свободен (id) на твоём сервере?",
        },
        {
            "title": "Мониторинг в реальном времени",
            "description": "Запусти top и разберись в его выводе. Найди самый нагруженный процесс.",
            "command": "top -bn1 | head -20",
            "hint": "В живом top: `q` выход, `P` сортировка по CPU, `M` по памяти, `k` убить процесс по PID. `-bn1` = пакетный режим, одна итерация.",
            "verify": "Какой процесс потребляет больше всего CPU прямо сейчас?",
        },
        {
            "title": "Проверь I/O диска",
            "description": "Посмотри нагрузку на диск: сколько операций чтения и записи происходит.",
            "command": "iostat -x 1 3 2>/dev/null || cat /proc/diskstats | awk '{print $3, $6, $10}' | head -5",
            "hint": "Если iostat не установлен: `apt install sysstat`. `%util` — загрузка диска в процентах. Близко к 100% = диск перегружен.",
            "verify": "Какая нагрузка на диск? Больше чтений или записей?",
        },
    ],
    "cicd": [
        {
            "title": "Создай GitHub Actions workflow",
            "description": "В своём репозитории assistant создай простой workflow который запускается при каждом push.",
            "command": "mkdir -p ~/assistant/.github/workflows && cat > ~/assistant/.github/workflows/check.yml << 'EOF'\nname: Check\non: [push]\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - name: Check Python syntax\n        run: python -m py_compile bot.py && echo 'OK'\nEOF\ncat ~/assistant/.github/workflows/check.yml",
            "hint": "`on: [push]` — триггер при push. `runs-on` — среда выполнения. `steps` — список шагов. Добавь в git и запушь чтобы увидеть в GitHub → Actions.",
            "verify": "Файл создан? Что делает этот workflow?",
        },
        {
            "title": "Посмотри на CI/CD в действии",
            "description": "Зайди на GitHub в репозиторий assistant и посмотри на вкладку Actions.",
            "command": "cd ~/assistant && git log --oneline -5 && echo 'Зайди на: https://github.com/TinGreen711/assistant/actions'",
            "hint": "Если нет ни одного workflow — сначала создай (предыдущая задача). Actions запускаются при push/PR. Зелёная галочка = успех, красный крест = ошибка.",
            "verify": "Видишь вкладку Actions на GitHub? Есть ли запущенные workflows?",
        },
        {
            "title": "Добавь линтер в pipeline",
            "description": "Добавь проверку кода (flake8) в свой GitHub Actions workflow.",
            "command": "cat > ~/assistant/.github/workflows/check.yml << 'EOF'\nname: Check\non: [push]\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v3\n      - uses: actions/setup-python@v4\n        with:\n          python-version: '3.11'\n      - run: pip install flake8\n      - run: flake8 bot.py --max-line-length=120 --count\nEOF\necho 'Workflow обновлён'",
            "hint": "flake8 — линтер Python: находит синтаксические ошибки и нарушения стиля. `--max-line-length=120` — допустимая длина строки. Запушь чтобы сработало.",
            "verify": "Файл workflow обновлён? Что нового он проверяет?",
        },
        {
            "title": "Локальная симуляция CI",
            "description": "Запусти те же проверки что делает CI — локально на сервере, до пуша в GitHub.",
            "command": "cd ~/assistant && .venv/bin/python -m py_compile bot.py quiz.py tasks.py && echo 'Синтаксис OK' && .venv/bin/python -c 'import bot, quiz, tasks; print(\"Импорты OK\")'",
            "hint": "Локальная проверка быстрее CI — сразу видишь ошибки. Это называется 'shift left' — сдвинуть проверки влево по времени, раньше в процессе.",
            "verify": "Все модули прошли проверку?",
        },
    ],
}


def init_tasks_db() -> None:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL
            )
        """)


def log_task_completion(chat_id: int, topic: str, title: str, completed: bool) -> None:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO task_completions (chat_id, date, topic, title, completed) VALUES (?, ?, ?, ?, ?)",
            (chat_id, today, topic, title, int(completed)),
        )


def get_weak_topic(chat_id: int) -> str:
    with sqlite3.connect(ASSISTANT_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT topic, SUM(correct) * 1.0 / SUM(total) as score
            FROM quiz_results
            WHERE chat_id = ?
            GROUP BY topic
            HAVING SUM(total) >= 5
            """,
            (chat_id,),
        ).fetchall()

    scored = {topic: score for topic, score in rows if topic in TASK_TOPICS}
    if scored:
        return min(scored, key=scored.get)
    return random.choice(list(TASK_TOPICS.keys()))


def get_task(chat_id: int, preferred_topic: str | None = None) -> Dict[str, Any]:
    if preferred_topic and preferred_topic in TASK_TOPICS:
        topic = preferred_topic
    else:
        topic = get_weak_topic(chat_id)
    task = random.choice(TASKS[topic])
    return {"topic": topic, "topic_label": TASK_TOPICS[topic], **task}


def format_task(task: Dict[str, Any]) -> str:
    return (
        f"Практическая задача — {task['topic_label']}\n\n"
        f"{task['title']}\n\n"
        f"{task['description']}\n\n"
        f"Команда:\n`{task['command']}`\n\n"
        f"После выполнения: {task['verify']}"
    )


def format_task_with_hint(task: Dict[str, Any]) -> str:
    return (
        f"Практическая задача — {task['topic_label']}\n\n"
        f"{task['title']}\n\n"
        f"{task['description']}\n\n"
        f"Команда:\n`{task['command']}`\n\n"
        f"Подсказка: {task['hint']}\n\n"
        f"После выполнения: {task['verify']}"
    )

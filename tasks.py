import html
import random
import db
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
        {
            "title": "Трейсинг системных вызовов",
            "description": "Используй strace чтобы увидеть что делает процесс на уровне ядра.",
            "command": "strace -c ls /tmp 2>&1 | head -20",
            "hint": "`-c` — статистика вызовов. Без флага выводит каждый вызов. `strace -p PID` — присоединиться к запущенному процессу.",
            "verify": "Какие системные вызовы чаще всего делает ls?",
        },
        {
            "title": "Открытые файлы процесса",
            "description": "Посмотри какие файлы и сокеты держит открытыми твой бот-процесс.",
            "command": "lsof -p $(pgrep -f bot.py | head -1) 2>/dev/null | head -20",
            "hint": "lsof = list open files. `TYPE`: REG=файл, IPv4/IPv6=сетевой сокет, FIFO=pipe. `FD`: cwd=рабочая папка, txt=исполняемый файл.",
            "verify": "Сколько файловых дескрипторов держит бот? Видишь сетевые соединения?",
        },
        {
            "title": "Сообщения ядра (dmesg)",
            "description": "Посмотри последние события в ядре Linux — ошибки устройств, OOM, сетевые события.",
            "command": "dmesg --level=err,warn --since '1 hour ago' --no-pager 2>/dev/null || dmesg | tail -20",
            "hint": "`--level` фильтрует по уровню. OOM Killer — это ядро убивает процессы при нехватке RAM. Net: — сетевые события.",
            "verify": "Есть ли ошибки ядра? Что они означают?",
        },
        {
            "title": "Лимиты файловых дескрипторов",
            "description": "Узнай сколько файлов одновременно может открыть процесс. Это критично для серверов.",
            "command": "ulimit -n && cat /proc/sys/fs/file-max && ls /proc/$(pgrep -f bot.py | head -1)/fd 2>/dev/null | wc -l",
            "hint": "`ulimit -n` — лимит для текущего шелла. `file-max` — системный лимит. Для высоконагруженных серверов часто нужно 65536+.",
            "verify": "Какой текущий лимит fd? Сколько открыто у бота?",
        },
        {
            "title": "Инспекция /proc/<pid>",
            "description": "Загляни в виртуальную файловую систему /proc — там хранится всё о запущенных процессах.",
            "command": "PID=$(pgrep -f bot.py | head -1); echo \"PID: $PID\"; cat /proc/$PID/status | grep -E 'Name|VmRSS|Threads|State'; cat /proc/$PID/cmdline | tr '\\0' ' '",
            "hint": "VmRSS — реальная RAM процесса. Threads — кол-во потоков. cmdline — полная команда запуска через нулевые байты.",
            "verify": "Сколько RAM (VmRSS) занимает бот? Сколько у него потоков?",
        },
        {
            "title": "Поиск по содержимому файлов",
            "description": "Найди в логах или конфигах все строки содержащие определённое слово.",
            "command": "grep -rn 'ERROR\\|error' /var/log/syslog 2>/dev/null | tail -10 || journalctl -p err --since today --no-pager | tail -10",
            "hint": "`-r` рекурсивно, `-n` показывает номер строки, `-i` игнорирует регистр. `grep -c` считает строки, `grep -l` только имена файлов.",
            "verify": "Нашёл ERROR-строки? В каких сервисах ошибки?",
        },
        {
            "title": "Сравни два файла",
            "description": "Используй diff чтобы найти разницу между двумя конфигами или файлами.",
            "command": "diff /etc/hostname /etc/mailname 2>/dev/null || diff <(echo 'server1') <(echo 'server2') && diff /etc/cron.d/ /etc/cron.daily/ 2>&1 | head -10",
            "hint": "`diff file1 file2` — построчно. `<` — строки только в первом, `>` — только во втором. `diff -u` — унифицированный формат (как git diff).",
            "verify": "Чем различаются файлы? Что означают символы < и >?",
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
        {
            "title": "Захват пакетов (tcpdump)",
            "description": "Захвати первые 10 пакетов на сетевом интерфейсе. Это основа сетевой диагностики.",
            "command": "tcpdump -n -c 10 -i any 2>/dev/null || tcpdump -n -c 10 2>/dev/null",
            "hint": "`-n` не резолвит имена, `-c 10` остановиться после 10 пакетов, `-i any` все интерфейсы. Формат: время src > dst: флаги.",
            "verify": "Какие хосты обмениваются пакетами? Видишь SSH-трафик?",
        },
        {
            "title": "HTTP-запрос с заголовками",
            "description": "Сделай HTTP-запрос к своему серверу и изучи ответные заголовки.",
            "command": "curl -I http://localhost 2>/dev/null || curl -I http://localhost:8080 2>/dev/null || curl -sI https://httpbin.org/get | head -15",
            "hint": "`-I` = HEAD запрос (только заголовки). `-v` = verbose (полный диалог). `-L` следовать редиректам. Код 200=OK, 301=redirect, 404=not found.",
            "verify": "Какой код ответа? Какие заголовки вернул сервер (Server, Content-Type)?",
        },
        {
            "title": "Правила iptables",
            "description": "Посмотри правила межсетевого экрана на сервере.",
            "command": "iptables -L -n --line-numbers 2>/dev/null || nft list ruleset 2>/dev/null | head -30",
            "hint": "INPUT — входящий трафик, OUTPUT — исходящий, FORWARD — проходящий. ACCEPT = разрешить, DROP = отбросить, REJECT = отклонить с ответом.",
            "verify": "Открыт ли порт 22 (SSH)? Есть ли правила блокировки?",
        },
        {
            "title": "Статистика сетевых ошибок",
            "description": "Проверь есть ли потери пакетов и ошибки на сетевых интерфейсах.",
            "command": "ip -s link show && cat /proc/net/dev | column -t",
            "hint": "RX errors/dropped — потери входящих пакетов. TX errors — ошибки отправки. Ненулевые значения = проблема с сетью или кабелем.",
            "verify": "Есть ли ошибки или потери пакетов на интерфейсах?",
        },
        {
            "title": "Детальный DNS-запрос",
            "description": "Разберись как работает DNS изнутри: проследи весь путь запроса.",
            "command": "dig +trace google.com | head -30",
            "hint": "`+trace` показывает весь путь: корневые серверы → TLD (.com) → авторитативный сервер. Тип A = IPv4, CNAME = псевдоним, MX = почта.",
            "verify": "Через сколько уровней прошёл запрос? Что такое TTL в DNS?",
        },
        {
            "title": "Сводка сетевых соединений",
            "description": "Получи сводку по всем типам соединений сервера одной командой.",
            "command": "ss -s && echo '---' && ss -tn | awk '{print $1}' | sort | uniq -c",
            "hint": "`ss -s` — общая статистика. CLOSE-WAIT = клиент закрыл соединение, мы ещё нет. TIME-WAIT = ждём финального ACK.",
            "verify": "Сколько соединений в состоянии ESTABLISHED? Есть ли CLOSE-WAIT?",
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
        {
            "title": "Войди в контейнер (exec)",
            "description": "Подключись к запущенному nginx-контейнеру и изучи его файловую систему изнутри.",
            "command": "docker run -d --name explore-nginx nginx && docker exec -it explore-nginx ls /etc/nginx/ && docker exec explore-nginx cat /etc/nginx/nginx.conf | head -20 && docker rm -f explore-nginx",
            "hint": "`exec -it` — интерактивный терминал. Без `-it` команда выполнится и вернёт вывод. `/bin/bash` или `/bin/sh` — войти в шелл.",
            "verify": "Что находится в /etc/nginx/ внутри контейнера?",
        },
        {
            "title": "Детали контейнера (inspect)",
            "description": "Получи всю техническую информацию о контейнере в формате JSON.",
            "command": "docker run -d --name inspect-test nginx && docker inspect inspect-test | python3 -c \"import json,sys; d=json.load(sys.stdin)[0]; print('IP:', d['NetworkSettings']['IPAddress']); print('Image:', d['Config']['Image'])\" && docker rm -f inspect-test",
            "hint": "`docker inspect` возвращает JSON с полной конфигурацией. `--format '{{.NetworkSettings.IPAddress}}'` — быстрый способ вытащить поле.",
            "verify": "Какой IP получил контейнер? Какой образ использован?",
        },
        {
            "title": "Сети Docker",
            "description": "Изучи сетевую изоляцию Docker — как контейнеры видят друг друга.",
            "command": "docker network ls && docker network inspect bridge | python3 -c \"import json,sys; d=json.load(sys.stdin)[0]; print('Subnet:', d['IPAM']['Config'][0]['Subnet'] if d['IPAM']['Config'] else 'нет')\" 2>/dev/null",
            "hint": "bridge — сеть по умолчанию. host — контейнер использует сеть хоста. none — без сети. Контейнеры в одной сети видят друг друга по имени.",
            "verify": "Какие сети есть у Docker? Какая подсеть у bridge?",
        },
        {
            "title": "Мониторинг контейнеров",
            "description": "Посмотри потребление ресурсов всеми запущенными контейнерами.",
            "command": "docker stats --no-stream --format 'table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.NetIO}}'",
            "hint": "`--no-stream` — одна итерация вместо live-обновления. `--format` управляет выводом. CPU > 100% возможен если несколько ядер.",
            "verify": "Какие контейнеры запущены? Сколько RAM они потребляют?",
        },
        {
            "title": "Создай свой Docker-образ",
            "description": "Напиши простой Dockerfile и собери из него образ.",
            "command": "mkdir -p /tmp/myapp && echo -e 'FROM python:3.11-slim\\nCMD [\"python\", \"-c\", \"print(\\\"Hello from my image!\\\")\"]\n' > /tmp/myapp/Dockerfile && docker build -t myapp:test /tmp/myapp && docker run --rm myapp:test && docker rmi myapp:test",
            "hint": "FROM — базовый образ. CMD — команда по умолчанию. COPY — копировать файлы. RUN — выполнить при сборке. Каждая инструкция = слой образа.",
            "verify": "Образ собрался? Контейнер напечатал 'Hello from my image!'?",
        },
        {
            "title": "Volumes (постоянное хранилище)",
            "description": "Создай volume — данные переживут удаление контейнера.",
            "command": "docker volume create mydata && docker run --rm -v mydata:/data alpine sh -c 'echo \"saved\" > /data/test.txt' && docker run --rm -v mydata:/data alpine cat /data/test.txt && docker volume rm mydata",
            "hint": "`-v volume_name:/path` — монтирует volume в контейнер. `docker volume inspect` — детали. `-v /host/path:/container/path` — монтирует папку хоста.",
            "verify": "Данные сохранились между двумя разными контейнерами?",
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
        {
            "title": "git stash — временный карман",
            "description": "Спрячь незакоммиченные изменения в stash чтобы переключиться на другую задачу.",
            "command": "cd ~/assistant && echo 'temp change' >> /tmp/stash_test.txt && git stash list && echo 'stash list показан выше'",
            "hint": "`git stash` — спрятать изменения. `git stash pop` — вернуть. `git stash list` — список. `git stash show -p` — что внутри. Stash — стек, LIFO.",
            "verify": "Сколько stash-записей в репозитории? Как вернуть последний stash?",
        },
        {
            "title": "git blame — кто написал строку",
            "description": "Узнай кто и когда написал каждую строку файла — незаменимо при дебаггинге.",
            "command": "cd ~/assistant && git blame bot.py | head -15",
            "hint": "Формат: хэш (автор дата строка) содержимое. `git blame -L 50,60 file.py` — только строки 50-60. `git log -S 'текст'` — найти коммит где появился текст.",
            "verify": "Кто написал первые строки bot.py? Как давно?",
        },
        {
            "title": "git revert — безопасная отмена",
            "description": "Отмени последний коммит создав новый коммит-откат (безопасно, история сохраняется).",
            "command": "cd ~/assistant && git log --oneline -3 && echo 'Команда для отмены: git revert HEAD --no-edit (НЕ запускай без нужды!)'",
            "hint": "`git revert` создаёт новый коммит отменяющий изменения. `git reset` — опасно, переписывает историю. В командах с общей историей — только revert!",
            "verify": "В чём разница между git revert и git reset --hard?",
        },
        {
            "title": "git diff — изучи изменения",
            "description": "Детально изучи разницу между коммитами — это ежедневный инструмент разработчика.",
            "command": "cd ~/assistant && git diff HEAD~1 HEAD --stat && git diff HEAD~1 HEAD -- bot.py | head -30",
            "hint": "`--stat` — краткая статистика изменений. `git diff main..feature` — между ветками. `git diff --cached` — что уже добавлено в stage.",
            "verify": "Что изменилось в последнем коммите? Сколько строк добавлено/удалено?",
        },
        {
            "title": "git remote — управление удалёнными репозиториями",
            "description": "Изучи настройки remote в своём проекте.",
            "command": "cd ~/assistant && git remote -v && git remote show origin 2>/dev/null | head -15",
            "hint": "`git remote -v` — показать все remote. `git remote add upstream URL` — добавить второй remote. fetch vs push URL могут быть разными.",
            "verify": "Какой URL у remote origin? Это fetch или push?",
        },
        {
            "title": "git log — расширенный просмотр",
            "description": "Изучи историю проекта через разные форматы git log.",
            "command": "cd ~/assistant && git log --oneline --graph --all -10 && git log --format='%h %an %ar: %s' -5",
            "hint": "`--graph` рисует ASCII граф веток. `%h`=хэш, `%an`=автор, `%ar`=время, `%s`=тема. `git log --after='2024-01-01'` — фильтр по дате.",
            "verify": "Как выглядит граф веток? Какой формат сообщений коммитов в проекте?",
        },
    ],
    "bash": [
        {
            "title": "Функции в bash",
            "description": "Напиши функцию которая принимает аргумент и возвращает результат.",
            "command": "check_port() { ss -tlnp | grep -q \":$1 \" && echo \"PORT $1: ОТКРЫТ\" || echo \"PORT $1: ЗАКРЫТ\"; }; check_port 22; check_port 8080; check_port 5432",
            "hint": "Функция в bash: `name() { тело; }`. `$1` — первый аргумент. `return 0` — успех, `return 1` — ошибка. `local var=value` — локальная переменная.",
            "verify": "Функция показала статус портов? Как передать несколько аргументов?",
        },
        {
            "title": "grep с regex",
            "description": "Используй grep с расширенными регулярными выражениями для фильтрации логов.",
            "command": "journalctl --since today --no-pager 2>/dev/null | grep -E '(ERROR|WARN|Failed)' | tail -10 || grep -E '^[A-Z]' /etc/os-release",
            "hint": "`-E` — расширенный regex. `|` — ИЛИ. `^` — начало строки. `$` — конец. `[A-Z]` — любая заглавная. `+` — один и более. `?` — ноль или один.",
            "verify": "Нашёл ERROR/WARN строки? Что означает символ ^ в regex?",
        },
        {
            "title": "sed — замена в потоке",
            "description": "Используй sed для трансформации текста без редактирования файла вручную.",
            "command": "echo 'server_name localhost;' | sed 's/localhost/example.com/g' && cat /etc/nginx/nginx.conf 2>/dev/null | sed '/^#/d' | sed '/^$/d' | head -10",
            "hint": "`sed 's/old/new/g'` — заменить все вхождения. `-i` — изменить файл на месте. `/^#/d` — удалить строки начинающиеся с #. `p` — печатать.",
            "verify": "sed заменил localhost на example.com? Что делает `sed '/^$/d'`?",
        },
        {
            "title": "awk — обработка колонок",
            "description": "Используй awk для извлечения и обработки структурированных данных.",
            "command": "df -h | awk 'NR>1 {print $5, $6}' | sort -r | head -5 && ps aux | awk '{sum += $4} END {print \"Итого %MEM:\", sum}' | head -1",
            "hint": "`NR` — номер строки. `$1,$2...` — колонки. `BEGIN{}` — до обработки. `END{}` — после. `-F:` — разделитель двоеточие. `printf` — форматированный вывод.",
            "verify": "awk показал использование дисков? Что означает `NR>1`?",
        },
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
        {
            "title": "xargs — передача аргументов",
            "description": "Используй xargs чтобы применить команду к каждому элементу из stdin.",
            "command": "echo '/etc/passwd /etc/hostname /etc/os-release' | tr ' ' '\\n' | xargs wc -l && find /tmp -name '*.sh' -type f | xargs ls -la 2>/dev/null",
            "hint": "`xargs` берёт stdin и передаёт как аргументы. `-I{}` — подстановка. `-P4` — параллельно 4 процесса. `xargs -n1` — по одному аргументу.",
            "verify": "xargs посчитал строки в файлах? Как передать каждый аргумент отдельно?",
        },
        {
            "title": "Heredoc — многострочный ввод",
            "description": "Используй heredoc для создания многострочных файлов и передачи текста командам.",
            "command": "cat > /tmp/test_heredoc.conf << 'EOF'\n[service]\nname=test\nport=8080\nenabled=true\nEOF\ncat /tmp/test_heredoc.conf && rm /tmp/test_heredoc.conf",
            "hint": "`<< 'EOF'` — heredoc с одинарными кавычками не раскрывает переменные. Без кавычек — `$VAR` раскрываются. `<<<` — herestring (одна строка).",
            "verify": "Файл создался с нужным содержимым? Когда heredoc удобнее echo?",
        },
        {
            "title": "trap — обработка сигналов",
            "description": "Напиши скрипт который корректно завершается при Ctrl+C и убирает временные файлы.",
            "command": "cat > /tmp/trap_demo.sh << 'EOF'\n#!/bin/bash\nTMPFILE=$(mktemp)\ntrap 'echo \"Чистим $TMPFILE\"; rm -f $TMPFILE; exit 0' INT TERM EXIT\necho \"Работаю... файл: $TMPFILE\"\ndate > $TMPFILE\ncat $TMPFILE\nEOF\nchmod +x /tmp/trap_demo.sh && /tmp/trap_demo.sh",
            "hint": "`trap 'команда' СИГНАЛ`. INT=Ctrl+C, TERM=kill, EXIT=любой выход. Это паттерн cleanup — обязателен в продакшн-скриптах.",
            "verify": "Скрипт запустился и почистил временный файл? Зачем trap EXIT?",
        },
    ],
    "systemd": [
        {
            "title": "Создай свой unit-файл",
            "description": "Напиши systemd-юнит который запускает простой скрипт как сервис.",
            "command": "cat > /tmp/hello.sh << 'EOF'\n#!/bin/bash\nwhile true; do echo \"alive $(date)\"; sleep 60; done\nEOF\nchmod +x /tmp/hello.sh\ncat > /tmp/hello.service << 'EOF'\n[Unit]\nDescription=Hello Test Service\n\n[Service]\nExecStart=/tmp/hello.sh\nRestart=on-failure\n\n[Install]\nWantedBy=multi-user.target\nEOF\ncat /tmp/hello.service",
            "hint": "[Unit]=метаданные, [Service]=как запускать, [Install]=в какой target. `Restart=on-failure` — перезапуск при сбое. `Type=simple` по умолчанию.",
            "verify": "Unit-файл создан? Что означает `WantedBy=multi-user.target`?",
        },
        {
            "title": "systemd Timer (замена cron)",
            "description": "Создай timer-юнит который запускает задачу по расписанию.",
            "command": "systemctl list-timers --all | head -15 && echo '---' && cat /lib/systemd/system/apt-daily.timer 2>/dev/null | head -20",
            "hint": "Timer юнит активирует одноимённый .service. `OnCalendar=daily` = раз в день. `OnBootSec=5min` = через 5 минут после загрузки. Заменяет cron, но с journald-логами.",
            "verify": "Какие timers уже запущены в системе? Чем timer лучше cron?",
        },
        {
            "title": "systemd-cgls — дерево cgroups",
            "description": "Посмотри иерархию контрольных групп — как systemd изолирует процессы.",
            "command": "systemd-cgls --no-pager | head -30",
            "hint": "cgroup изолирует ресурсы: CPU, RAM, IO. `systemctl set-property assistant.service MemoryMax=512M` — ограничить RAM сервиса. `/sys/fs/cgroup/` — интерфейс ядра.",
            "verify": "Видишь свой assistant.service в дереве? Под каким slice он находится?",
        },
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
        {
            "title": "journald: ротация и размер логов",
            "description": "Проверь сколько места занимают логи systemd и как ими управлять.",
            "command": "journalctl --disk-usage && journalctl --list-boots | head -5",
            "hint": "`--disk-usage` — общий размер. `--vacuum-size=500M` — обрезать до 500MB. `--vacuum-time=30d` — удалить старше 30 дней. `/etc/systemd/journald.conf` — настройки.",
            "verify": "Сколько места занимают логи? Сколько загрузок сохранено?",
        },
        {
            "title": "systemctl mask — полный запрет",
            "description": "Разберись с разницей между disable и mask для управления сервисами.",
            "command": "systemctl is-enabled assistant.service && systemctl cat assistant.service | head -10",
            "hint": "`disable` — не запускать при загрузке, но можно запустить вручную. `mask` — симлинк на /dev/null, невозможно запустить вообще. `unmask` — снять маску.",
            "verify": "assistant.service включён в автозапуск? Что в его unit-файле?",
        },
        {
            "title": "Зависимости между сервисами",
            "description": "Посмотри от чего зависит твой сервис и что зависит от него.",
            "command": "systemctl list-dependencies assistant.service 2>/dev/null || systemctl list-dependencies sshd.service | head -15",
            "hint": "`Wants=` — мягкая зависимость (запустит если можно). `Requires=` — строгая (упадёт если зависимость не запустилась). `After=` — порядок запуска.",
            "verify": "От каких сервисов зависит sshd? Что такое network.target?",
        },
    ],
    "nginx": [
        {
            "title": "Реверс-прокси через proxy_pass",
            "description": "Настрой Nginx как реверс-прокси перед приложением — стандартная схема в продакшне.",
            "command": "cat > /tmp/proxy_example.conf << 'EOF'\nserver {\n    listen 80;\n    server_name example.com;\n\n    location / {\n        proxy_pass http://127.0.0.1:8000;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n    }\n}\nEOF\nnginx -t -c /tmp/proxy_example.conf 2>&1 | head -5 || cat /tmp/proxy_example.conf",
            "hint": "`proxy_pass` передаёт запрос к backend. `proxy_set_header X-Real-IP` — передать реальный IP клиента. `upstream {}` — балансировка между несколькими backend.",
            "verify": "Понял схему? Зачем нужен заголовок X-Real-IP?",
        },
        {
            "title": "Rate limiting в Nginx",
            "description": "Настрой ограничение частоты запросов — защита от DDoS и перегрузки.",
            "command": "cat << 'EOF'\nhttp {\n    limit_req_zone $binary_remote_addr zone=one:10m rate=10r/s;\n    server {\n        location /api/ {\n            limit_req zone=one burst=20 nodelay;\n        }\n    }\n}\nEOF\nnginx -T 2>/dev/null | grep -A5 'limit_req' | head -10 || echo 'Изучи синтаксис выше'",
            "hint": "`limit_req_zone` — создать зону. `$binary_remote_addr` — по IP клиента. `rate=10r/s` — 10 запросов/секунду. `burst=20` — допустимый всплеск. `nodelay` — не задерживать.",
            "verify": "Что такое burst в rate limiting? Чем nodelay отличается от delay?",
        },
        {
            "title": "Заголовки безопасности",
            "description": "Добавь HTTP-заголовки безопасности в конфиг Nginx — базовая защита веб-приложения.",
            "command": "cat << 'EOF'\nadd_header X-Frame-Options SAMEORIGIN;\nadd_header X-Content-Type-Options nosniff;\nadd_header X-XSS-Protection \"1; mode=block\";\nadd_header Strict-Transport-Security \"max-age=31536000\" always;\nEOF\ncurl -sI http://localhost 2>/dev/null | grep -iE 'X-Frame|X-Content|Strict' || echo 'Заголовки не настроены — изучи синтаксис выше'",
            "hint": "HSTS (Strict-Transport-Security) говорит браузеру всегда использовать HTTPS. X-Frame-Options защищает от clickjacking. nosniff — не угадывать тип контента.",
            "verify": "Какие заголовки безопасности отвечает твой Nginx? Что защищает HSTS?",
        },
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
        {
            "title": "gzip-сжатие в Nginx",
            "description": "Включи gzip-сжатие — экономит трафик и ускоряет загрузку страниц.",
            "command": "nginx -T 2>/dev/null | grep -A10 'gzip' | head -15 || cat << 'EOF'\ngzip on;\ngzip_vary on;\ngzip_min_length 1024;\ngzip_types text/plain text/css application/json application/javascript;\nEOF",
            "hint": "`gzip_min_length` — не сжимать файлы меньше N байт. `gzip_comp_level` 1-9 (баланс CPU vs размер). `gzip_vary on` — добавляет Vary: Accept-Encoding для кэшей.",
            "verify": "Включён ли gzip в твоём Nginx? Какие типы файлов сжимаются?",
        },
        {
            "title": "upstream — балансировка нагрузки",
            "description": "Изучи конфигурацию upstream-блока для распределения трафика между серверами.",
            "command": "cat << 'EOF'\nupstream backend {\n    least_conn;\n    server 127.0.0.1:8001 weight=3;\n    server 127.0.0.1:8002;\n    server 127.0.0.1:8003 backup;\n}\nEOF\nnginx -T 2>/dev/null | grep -A5 'upstream' | head -15 || echo 'Изучи синтаксис upstream выше'",
            "hint": "`least_conn` — к серверу с наименьшим числом соединений. `weight` — относительный вес. `backup` — используется если остальные недоступны. `ip_hash` — сессионная афинность.",
            "verify": "Что такое least_conn? Для чего нужен backup-сервер?",
        },
    ],
    "monitoring": [
        {
            "title": "Исторические метрики (sar)",
            "description": "Посмотри исторические метрики CPU и памяти через sar.",
            "command": "sar -u 1 3 2>/dev/null || apt list --installed 2>/dev/null | grep sysstat || echo 'Установи: apt install sysstat && systemctl enable sysstat'",
            "hint": "`sar -u` = CPU, `-r` = RAM, `-n DEV` = сетевой интерфейс. `sar -u -f /var/log/sysstat/saXX` — данные конкретного дня. Хранит 28 дней по умолчанию.",
            "verify": "sar установлен? Сколько процентов CPU используется?",
        },
        {
            "title": "Блочные устройства (lsblk)",
            "description": "Изучи структуру дисков и разделов сервера.",
            "command": "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT && fdisk -l 2>/dev/null | grep -E 'Disk /dev|/dev/[a-z]' | head -10",
            "hint": "`TYPE`: disk=диск, part=раздел, lvm=логический том. `lsblk -f` показывает UUID и тип ФС. LVM позволяет изменять размер разделов без остановки.",
            "verify": "Сколько дисков на сервере? Есть ли LVM разделы?",
        },
        {
            "title": "Мониторинг сетевого трафика",
            "description": "Посмотри сколько трафика проходит через сетевые интерфейсы.",
            "command": "cat /proc/net/dev | column -t | head -10 && ip -s link show | grep -A5 'eth0\\|ens\\|enp' | head -20",
            "hint": "RX bytes — получено, TX bytes — отправлено. `iftop` — live мониторинг по соединениям. `nethogs` — по процессам. `/proc/net/dev` обновляется с момента загрузки.",
            "verify": "Сколько трафика прошло через основной интерфейс?",
        },
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
        {
            "title": "Алертинг через скрипт",
            "description": "Напиши простой скрипт мониторинга который сообщает о проблемах.",
            "command": "cat > /tmp/monitor.sh << 'SCRIPT'\n#!/bin/bash\nCPU=$(top -bn1 | grep 'Cpu(s)' | awk '{print int($2)}')\nMEM=$(free | awk '/Mem:/ {printf \"%.0f\", $3/$2*100}')\nDISK=$(df / | awk 'NR==2 {print int($5)}')\necho \"CPU: ${CPU}%, MEM: ${MEM}%, DISK: ${DISK}%\"\n[ $DISK -gt 80 ] && echo 'ALERT: диск заполнен!'\n[ $MEM -gt 90 ] && echo 'ALERT: мало памяти!'\nSCRIPT\nchmod +x /tmp/monitor.sh && /tmp/monitor.sh",
            "hint": "Это основа для мониторинг-агента. В продакшне результат отправляется в Prometheus/Grafana/Zabbix. Cron раз в минуту + telegram-уведомление = простой алертинг.",
            "verify": "Скрипт показал метрики? Есть ли алерты? Как добавить уведомление в Telegram?",
        },
        {
            "title": "Размер папок на диске",
            "description": "Найди самые тяжёлые папки на сервере — диагностика заполнения диска.",
            "command": "du -sh /var/* 2>/dev/null | sort -rh | head -10 && du -sh /home/* 2>/dev/null | sort -rh | head -5",
            "hint": "`du -sh` = disk usage, summary, human-readable. `sort -rh` — сортировка по размеру убыванием. `/var/log`, `/var/cache` — обычно самые тяжёлые.",
            "verify": "Какая папка занимает больше всего места? Что это за данные?",
        },
        {
            "title": "Процессы-зомби",
            "description": "Найди зомби-процессы — завершённые, но не убранные родителем.",
            "command": "ps aux | awk '$8 == \"Z\" {print $0}' && ps aux | grep -c 'defunct' && echo '---' && ps --ppid 2 -p 2 --deselect -o pid,stat,cmd | head -10",
            "hint": "Зомби (Z в колонке STAT) — процесс завершился, но запись в таблице процессов не удалена. Сами не убивают ресурсы, но занимают PID. Убить их нельзя — надо убить родителя.",
            "verify": "Есть ли зомби-процессы? Почему kill не помогает убить зомби?",
        },
    ],
    "cicd": [
        {
            "title": "docker build в CI",
            "description": "Разберись как собирают Docker-образы в GitHub Actions.",
            "command": "cat << 'EOF'\n- name: Build Docker image\n  run: |\n    docker build -t myapp:${{ github.sha }} .\n    docker tag myapp:${{ github.sha }} myapp:latest\n\n- name: Push to registry\n  run: |\n    docker login -u ${{ secrets.DOCKER_USER }} -p ${{ secrets.DOCKER_TOKEN }}\n    docker push myapp:latest\nEOF\ndocker images | head -5",
            "hint": "`${{ github.sha }}` — хэш коммита как тег образа. Хорошая практика: тег = sha, никогда только latest. Registry: Docker Hub, GHCR, ECR.",
            "verify": "Какие образы есть локально? Почему sha лучше latest в качестве тега?",
        },
        {
            "title": "Environment secrets в Actions",
            "description": "Разберись как безопасно передавать секреты в GitHub Actions.",
            "command": "cat << 'EOF'\njobs:\n  deploy:\n    environment: production\n    env:\n      DB_URL: ${{ secrets.DATABASE_URL }}\n      API_KEY: ${{ secrets.API_KEY }}\n    steps:\n      - run: echo \"Deploying to prod\"\n        # Secrets маскируются в логах автоматически\nEOF\ncat ~/assistant/.env 2>/dev/null | grep -v '=' | head -5 || echo 'Секреты хранятся в .env (не в git!)'",
            "hint": "Secrets в GitHub: Settings → Secrets. Никогда не выводи `env` в Actions — секреты попадут в логи! `${{ env.VAR }}` в шагах, `${{ secrets.VAR }}` — напрямую.",
            "verify": "Где хранятся секреты твоего проекта? Как они попадают в CI?",
        },
        {
            "title": "Кэширование в GitHub Actions",
            "description": "Ускори CI через кэширование зависимостей — основная оптимизация.",
            "command": "cat << 'EOF'\n- uses: actions/cache@v3\n  with:\n    path: ~/.cache/pip\n    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}\n    restore-keys: |\n      ${{ runner.os }}-pip-\n\n- run: pip install -r requirements.txt\nEOF\npip cache info 2>/dev/null || echo 'pip кэш: ~/.cache/pip'",
            "hint": "`key` — ключ кэша. Если requirements.txt не изменился → кэш попадёт. `hashFiles()` — хэш файла. `restore-keys` — частичное совпадение при промахе.",
            "verify": "Что будет с кэшем если изменить requirements.txt? Где хранится кэш pip?",
        },
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
        {
            "title": "Matrix build — тест на нескольких версиях",
            "description": "Изучи matrix-стратегию для тестирования на нескольких версиях Python.",
            "command": "cat << 'EOF'\njobs:\n  test:\n    strategy:\n      matrix:\n        python-version: ['3.10', '3.11', '3.12']\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/setup-python@v4\n        with:\n          python-version: ${{ matrix.python-version }}\n      - run: python --version\nEOF\npython3 --version",
            "hint": "Matrix запускает N параллельных джобов — по одному на каждую комбинацию. `include/exclude` — добавить/убрать конкретные комбинации. `fail-fast: false` — не прерывать остальные при падении одного.",
            "verify": "На какой версии Python работает твой бот? Зачем тестировать на нескольких версиях?",
        },
        {
            "title": "Артефакты и отчёты в CI",
            "description": "Сохраняй результаты тестов и отчёты как артефакты GitHub Actions.",
            "command": "cat << 'EOF'\n- name: Run tests\n  run: python -m pytest --junitxml=report.xml -v || true\n\n- uses: actions/upload-artifact@v3\n  if: always()\n  with:\n    name: test-report\n    path: report.xml\n    retention-days: 30\nEOF\necho 'Артефакты доступны в GitHub → Actions → твой запуск → Artifacts'",
            "hint": "`if: always()` — загрузить артефакт даже если тесты упали. `retention-days` — сколько хранить. Артефакты: логи, скриншоты, coverage-репорты, собранные бинарники.",
            "verify": "Для чего нужны артефакты в CI? Где они хранятся?",
        },
        {
            "title": "Деплой после успешного CI",
            "description": "Настрой автоматический деплой на сервер после прохождения тестов.",
            "command": "cat << 'EOF'\njobs:\n  deploy:\n    needs: [test, lint]\n    if: github.ref == 'refs/heads/main'\n    steps:\n      - name: Deploy via SSH\n        uses: appleboy/ssh-action@master\n        with:\n          host: ${{ secrets.SERVER_HOST }}\n          username: ${{ secrets.SERVER_USER }}\n          key: ${{ secrets.SSH_PRIVATE_KEY }}\n          script: |\n            cd ~/assistant && git pull\n            systemctl restart assistant\nEOF\nsystemctl is-active assistant.service",
            "hint": "`needs: [test, lint]` — запускать только если эти джобы прошли. `if: github.ref == 'refs/heads/main'` — только для main ветки. SSH-деплой — простейший способ, для продакшна лучше Docker+registry.",
            "verify": "Понял схему CD? Почему деплой должен идти после тестов (needs)?",
        },
    ],
}


def init_tasks_db() -> None:
    with db.connect() as conn:
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
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO task_completions (chat_id, date, topic, title, completed) VALUES (?, ?, ?, ?, ?)",
            (chat_id, today, topic, title, int(completed)),
        )


def get_weak_topic(chat_id: int) -> str:
    with db.connect() as conn:
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
        f"Практическая задача — {html.escape(task['topic_label'])}\n\n"
        f"{html.escape(task['title'])}\n\n"
        f"{html.escape(task['description'])}\n\n"
        f"Команда:\n<code>{html.escape(task['command'])}</code>\n\n"
        f"После выполнения: {html.escape(task['verify'])}"
    )


def format_task_with_hint(task: Dict[str, Any]) -> str:
    return (
        f"Практическая задача — {html.escape(task['topic_label'])}\n\n"
        f"{html.escape(task['title'])}\n\n"
        f"{html.escape(task['description'])}\n\n"
        f"Команда:\n<code>{html.escape(task['command'])}</code>\n\n"
        f"Подсказка: {html.escape(task['hint'])}\n\n"
        f"После выполнения: {html.escape(task['verify'])}"
    )

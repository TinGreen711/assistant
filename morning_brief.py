import db
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

from config import ASSISTANT_DB_PATH, USER_TIMEZONE
from study_tracker import get_streak, get_stats, TOPICS
from skills_path import format_path_short


TZ = ZoneInfo(USER_TIMEZONE)


TASK_BANKS: Dict[str, list] = {
    "linux": [
        {"task": "Запусти `ps aux` и найди процесс бота. Что означают столбцы PID, %CPU, %MEM?", "tip": "PID — уникальный номер процесса. Запомни его — он нужен для kill и strace."},
        {"task": "Посмотри логи любого сервиса: `journalctl -u assistant.service -n 50`", "tip": "journalctl — главный инструмент отладки в systemd-системах. Флаг -n задаёт количество строк."},
        {"task": "Проверь права файлов в /home/tin: `ls -la`. Что значат символы rwxrwxrwx?", "tip": "Три группы: владелец, группа, остальные. r=4, w=2, x=1. chmod 755 = rwxr-xr-x."},
        {"task": "Найди все файлы .py в проекте: `find /home/tin/assistant -name '*.py'`", "tip": "find — мощнее ls. Можно фильтровать по типу (-type f), размеру (-size), дате (-mtime)."},
        {"task": "Посмотри использование диска: `df -h` и `du -sh /home/tin/*`", "tip": "df показывает разделы целиком, du — конкретные папки. Флаг -h переводит байты в MB/GB."},
        {"task": "Посмотри переменные окружения: `printenv | grep -i path`", "tip": "PATH определяет где система ищет исполняемые файлы. export VAR=value — задать переменную."},
        {"task": "Попробуй grep: `grep -r 'proactive' /home/tin/assistant/ --include='*.py'`", "tip": "grep -r ищет рекурсивно. -i игнорирует регистр. -n показывает номер строки."},
        {"task": "Проверь сетевые соединения: `ss -tlnp`", "tip": "ss заменяет старый netstat. -t=TCP, -l=listening, -n=числа вместо имён, -p=процесс."},
        {"task": "Изучи crontab: `crontab -l`. Формат: минута час день месяц день_недели команда", "tip": "* * * * * = каждую минуту. 0 9 * * 1-5 = 9:00 по будням. Проверь: crontab.guru"},
        {"task": "Сожми папку: `tar -czf backup.tar.gz /home/tin/assistant/data`", "tip": "-c создать, -z сжать через gzip, -f имя файла. Распаковать: tar -xzf файл."},
    ],
    "networks": [
        {"task": "Запусти `ip addr show` — найди свой IP и сетевой интерфейс", "tip": "lo — loopback (127.0.0.1). eth0/enp* — проводная. wlan*/wlp* — WiFi. Запомни свой интерфейс."},
        {"task": "Проверь маршруты: `ip route show`. Что такое default gateway?", "tip": "default — куда идут пакеты без конкретного маршрута. Обычно это твой роутер (192.168.x.1)."},
        {"task": "Сделай `ping 1.1.1.1` и `ping google.com`. Что проверяет каждый вариант?", "tip": "IP проверяет сеть. Домен проверяет ещё и DNS. Если IP работает, а домен нет — DNS сломан."},
        {"task": "Посмотри DNS-запись: `dig google.com A` или `nslookup google.com`", "tip": "A-запись — IPv4 адрес. AAAA — IPv6. MX — почта. NS — DNS-серверы домена. TTL — время кеша."},
        {"task": "Проверь открытые порты на своём сервере: `ss -tlnp`", "tip": "Порт 22 = SSH. 80 = HTTP. 443 = HTTPS. 5432 = PostgreSQL. 6379 = Redis. Знание портов — база DevOps."},
        {"task": "Попробуй `traceroute 8.8.8.8` — посмотри через сколько хопов проходит пакет", "tip": "Каждый хоп — это маршрутизатор. * * * означает что хоп не отвечает (не ошибка)."},
        {"task": "Изучи CIDR: что значит /24 в адресе 192.168.1.0/24?", "tip": "/24 = 255.255.255.0 = 256 адресов (254 хоста). /32 = один IP. /16 = 65534 хоста. Калькулятор: ipcalc."},
        {"task": "Проверь firewall: `sudo iptables -L -n` или `sudo ufw status`", "tip": "UFW — упрощённый интерфейс над iptables. ACCEPT = разрешить, DROP = отбросить без ответа."},
        {"task": "Посмотри ARP-таблицу: `arp -n`. Что она показывает?", "tip": "ARP связывает IP-адреса с MAC-адресами в локальной сети. Нужно при отладке L2-проблем."},
        {"task": "Протестируй HTTP: `curl -v https://httpbin.org/get`", "tip": "-v показывает заголовки запроса и ответа. Смотри на статус (200, 404, 500) и Content-Type."},
    ],
    "docker": [
        {"task": "Запусти контейнер: `docker run --rm hello-world`. Что произошло?", "tip": "--rm удаляет контейнер после завершения. Без него контейнеры накапливаются. docker ps -a покажет все."},
        {"task": "Посмотри запущенные контейнеры: `docker ps`. Найди контейнеры проекта.", "tip": "CONTAINER ID, IMAGE, STATUS, PORTS, NAMES — основные столбцы. docker ps -a = включая остановленные."},
        {"task": "Зайди внутрь контейнера: `docker exec -it <имя> bash`", "tip": "-i интерактивный, -t псевдотерминал. Внутри контейнера — отдельная файловая система."},
        {"task": "Посмотри логи контейнера: `docker logs -f <имя>`", "tip": "-f следит за логами в реальном времени (как tail -f). --tail 50 = последние 50 строк."},
        {"task": "Изучи docker-compose.yml проекта. Что означают секции services, volumes, networks?", "tip": "services — контейнеры. volumes — постоянные данные. networks — изолированная сеть для контейнеров."},
        {"task": "Посмотри образы: `docker images`. Сколько занимают? Удали лишние: `docker image prune`", "tip": "Образы наслаиваются (layers). Неиспользуемые занимают место. prune удаляет только неиспользуемые."},
        {"task": "Напиши минимальный Dockerfile для Python-скрипта (FROM, COPY, RUN, CMD)", "tip": "FROM — базовый образ. RUN — команды при сборке. CMD — команда при запуске контейнера."},
        {"task": "Изучи volumes: `docker volume ls`. Зачем нужны volume вместо bind mount?", "tip": "Volume управляется Docker и переживает пересоздание контейнера. Bind mount = папка с хоста."},
        {"task": "Попробуй `docker inspect <имя_контейнера>` — найди IP контейнера в сети", "tip": "inspect выдаёт JSON со всей конфигурацией. Networks → IPAddress — IP внутри Docker-сети."},
        {"task": "Собери образ: `docker build -t mytest .` из папки с Dockerfile", "tip": "-t задаёт имя:тег. . означает текущую папку. Каждый шаг Dockerfile = отдельный слой кеша."},
    ],
    "git": [
        {"task": "Посмотри историю коммитов: `git log --oneline --graph`", "tip": "--oneline = одна строка на коммит. --graph рисует ветки. Понимать историю = понимать проект."},
        {"task": "Проверь статус: `git status` и `git diff`. В чём разница?", "tip": "status показывает какие файлы изменены. diff показывает что именно изменилось (строки)."},
        {"task": "Создай ветку: `git checkout -b feature/test`. Посмотри ветки: `git branch`", "tip": "-b создаёт и переключается. Ветки нужны чтобы не ломать основной код при экспериментах."},
        {"task": "Изучи git stash: сохрани изменения без коммита и восстанови их", "tip": "stash = временный карман. git stash push, затем git stash pop. Удобно при срочном переключении."},
        {"task": "Попробуй `git log --author='TinGreen711'` — посмотри свои коммиты", "tip": "git log умеет фильтровать по автору, дате, файлу. git log -- filename покажет историю файла."},
        {"task": "Изучи .gitignore: что в нём есть? Добавь паттерн для .env файлов", "tip": ".env не должен попасть в репозиторий — там секреты. *.log, __pycache__/, .venv/ — типичные исключения."},
        {"task": "Попробуй `git show HEAD` — что показывает последний коммит?", "tip": "HEAD — указатель на текущий коммит. HEAD~1 — предыдущий. git show покажет diff и метаданные."},
        {"task": "Изучи git remote: `git remote -v`. Что такое origin?", "tip": "origin — стандартное имя для удалённого репозитория (обычно GitHub). fetch и push могут быть разными URL."},
        {"task": "Сделай коммит с хорошим сообщением: тип(область): описание", "tip": "Примеры: feat(bot): add study tracker, fix(proactive): restore jobs on startup. Это называется Conventional Commits."},
        {"task": "Попробуй `git diff HEAD~1 HEAD` — что изменилось в последнем коммите?", "tip": "Сравнивать коммиты — обычная задача при ревью и отладке регрессий."},
    ],
    "ai": [
        {"task": "Разберись с понятием 'токен': почему 1 токен ≠ 1 слово?", "tip": "Токен — кусок текста ~4 символа. 'tokenizer' → ['token', 'izer']. Цены и лимиты считаются в токенах."},
        {"task": "Попробуй изменить temperature в brain.py (0.0 vs 1.0). Как меняются ответы?", "tip": "0 = детерминировано, всегда один ответ. 1+ = творческий, разные ответы. Для задач кода — 0-0.3."},
        {"task": "Изучи system prompt в brain.py. Почему он важнее user message?", "tip": "System prompt задаёт роль и контекст. Модель следует ему сильнее. Это рычаг управления поведением."},
        {"task": "Посчитай токены своего system prompt: примерно символы/4. Сколько стоит 1000 вызовов?", "tip": "gpt-4.1-mini: ~$0.15/1M input tokens. 500 токенов × 1000 вызовов = $0.075. Оптимизация важна."},
        {"task": "Изучи разницу между RAG и fine-tuning. Когда что применяется?", "tip": "RAG = подгружаем контекст каждый раз (гибко, дёшево). Fine-tuning = обучаем модель (дорого, для стиля/формата)."},
        {"task": "Посмотри как работает `store=False` в daily_cycle.py. Зачем это нужно?", "tip": "store=False запрещает OpenAI сохранять разговор для обучения. Важно для приватных данных."},
        {"task": "Изучи что такое embeddings. Как они используются в поиске?", "tip": "Embedding = вектор числ, описывающий смысл текста. Похожие тексты = похожие векторы. Основа семантического поиска."},
        {"task": "Прочитай про function calling / tool use в OpenAI API. Чем это отличается от обычного запроса?", "tip": "Модель может 'вызывать функции' — возвращает JSON с именем и аргументами. Ты исполняешь, возвращаешь результат."},
        {"task": "Посмотри на структуру ответа OpenAI API в коде. Что такое output_text?", "tip": "Responses API (новый): response.output_text. Chat Completions (старый): response.choices[0].message.content."},
        {"task": "Изучи понятие 'context window'. Что происходит когда контекст переполнен?", "tip": "Старые сообщения обрезаются или модель выдаёт ошибку. Поэтому нужна компрессия истории (как в этом боте)."},
    ],
    "prompt": [
        {"task": "Сравни zero-shot и few-shot. Добавь 1 пример в system prompt brain.py и посмотри разницу", "tip": "Few-shot = 'Вот примеры хорошего ответа'. Модель подстраивается под формат примеров."},
        {"task": "Попробуй chain-of-thought: добавь 'Думай пошагово перед ответом' в промпт", "tip": "COT улучшает точность на задачах рассуждения. Модель 'думает вслух' и реже ошибается."},
        {"task": "Изучи role prompting: перепиши system prompt в brain.py в форме роли", "tip": "'Ты опытный DevOps-инженер, ты отвечаешь кратко и по делу'. Роль задаёт стиль и компетентность."},
        {"task": "Добавь ограничение на формат ответа в промпт: 'Отвечай только в формате JSON'", "tip": "Явное указание формата снижает галлюцинации и упрощает парсинг. Ещё лучше — JSON mode в API."},
        {"task": "Попробуй разбить сложный промпт на шаги: 1) ... 2) ... 3) ...", "tip": "Нумерованные инструкции выполняются точнее чем длинный абзац. Модель следует структуре."},
        {"task": "Изучи prompt injection: как пользователь может сломать твой system prompt?", "tip": "'Игнорируй все предыдущие инструкции...' — классическая атака. Валидируй пользовательский ввод."},
        {"task": "Поэкспериментируй с max_output_tokens в config.py. Как это влияет на качество?", "tip": "Слишком мало = обрезанный ответ. Слишком много = лишние слова. Баланс зависит от задачи."},
        {"task": "Напиши промпт для генерации задач обучения (как в этом briefing). Что важно указать?", "tip": "Целевая аудитория, уровень, формат, количество, язык. Чем конкретнее — тем лучше результат."},
        {"task": "Сравни два промпта для одной задачи: краткий vs подробный. Что лучше?", "tip": "Для простых задач — краткий. Для сложных с нюансами — подробный. Тестируй, не угадывай."},
        {"task": "Добавь в промпт пример плохого ответа: 'Не делай так: ...'", "tip": "Negative examples иногда эффективнее позитивных. Показывай что избегать, а не только что делать."},
    ],
    "other": [
        {"task": "Запиши что именно изучал сегодня — одно конкретное понятие или команду", "tip": "Конкретность важнее объёма. Одна хорошо понятая команда лучше десяти прочитанных."},
        {"task": "Найди одну вещь в проекте ассистента которую не понимаешь, разберись с ней", "tip": "Непонятый код — технический долг в голове. Лучше разобрать сейчас чем откладывать."},
        {"task": "Прочитай одну статью по DevOps/SRE и запиши 1 главный вывод", "tip": "DigitalOcean tutorials, NGINX docs, Linux man pages — хорошие источники для начала."},
    ],
}


IT_WORDS = [
    {"word": "deploy", "translation": "развернуть", "example": "We deploy new code every Friday evening."},
    {"word": "daemon", "translation": "фоновый процесс", "example": "The SSH daemon listens on port 22."},
    {"word": "endpoint", "translation": "конечная точка API", "example": "Send a POST request to the /login endpoint."},
    {"word": "latency", "translation": "задержка", "example": "High latency makes the app feel slow."},
    {"word": "throughput", "translation": "пропускная способность", "example": "We need higher throughput to handle peak traffic."},
    {"word": "redundancy", "translation": "избыточность", "example": "We added redundancy with a backup server."},
    {"word": "failover", "translation": "переключение на резерв", "example": "Automatic failover keeps the service running."},
    {"word": "load balancing", "translation": "балансировка нагрузки", "example": "The load balancer splits traffic between servers."},
    {"word": "container", "translation": "контейнер", "example": "Each service runs in its own container."},
    {"word": "pipeline", "translation": "конвейер / цепочка задач", "example": "The CI/CD pipeline runs tests automatically."},
    {"word": "dependency", "translation": "зависимость", "example": "Add the library to your requirements.txt as a dependency."},
    {"word": "environment", "translation": "окружение", "example": "Never use production environment for testing."},
    {"word": "permission", "translation": "права доступа", "example": "You don't have permission to read that file."},
    {"word": "namespace", "translation": "пространство имён", "example": "Docker uses namespaces to isolate containers."},
    {"word": "mount", "translation": "монтировать", "example": "Mount the volume to persist data between restarts."},
    {"word": "proxy", "translation": "прокси-сервер", "example": "Nginx acts as a reverse proxy for our app."},
    {"word": "authentication", "translation": "аутентификация (кто ты?)", "example": "Use SSH key authentication instead of passwords."},
    {"word": "authorization", "translation": "авторизация (что можешь?)", "example": "Only admins have authorization to delete records."},
    {"word": "token", "translation": "токен (ключ доступа)", "example": "Store your API token in an environment variable."},
    {"word": "webhook", "translation": "вебхук", "example": "GitHub sends a webhook when code is pushed."},
    {"word": "cron", "translation": "планировщик задач", "example": "Set up a cron job to run backups at midnight."},
    {"word": "socket", "translation": "сокет", "example": "The database connects via a Unix socket."},
    {"word": "kernel", "translation": "ядро ОС", "example": "The Linux kernel manages hardware resources."},
    {"word": "repository", "translation": "репозиторий", "example": "Clone the repository and run the setup script."},
    {"word": "branch", "translation": "ветка", "example": "Create a new branch before making changes."},
    {"word": "rollback", "translation": "откат", "example": "If the deploy fails, we rollback to the previous version."},
    {"word": "orchestration", "translation": "оркестрация", "example": "Kubernetes handles orchestration of containers."},
    {"word": "monitoring", "translation": "мониторинг", "example": "Set up monitoring to catch issues before users do."},
    {"word": "logging", "translation": "логирование", "example": "Good logging makes debugging much faster."},
    {"word": "throttling", "translation": "ограничение скорости", "example": "The API uses throttling to prevent abuse."},
]


def _get_last_session(chat_id: int) -> Optional[Dict[str, Any]]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT topic, date FROM study_sessions WHERE chat_id = ? ORDER BY date DESC, id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()

    if not row:
        return None

    topic, date_str = row
    last = date.fromisoformat(date_str)
    today = datetime.now(TZ).date()
    days_ago = (today - last).days

    return {
        "topic": topic,
        "label": TOPICS.get(topic, topic),
        "days_ago": days_ago,
    }


def _get_topic_session_count(chat_id: int, topic: str) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE chat_id = ? AND topic = ?",
            (chat_id, topic),
        ).fetchone()
    return row[0] if row else 0


def _get_total_session_count(chat_id: int) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return row[0] if row else 0


def _pick_task(topic: str, session_count: int) -> Dict[str, str]:
    bank = TASK_BANKS.get(topic, TASK_BANKS["other"])
    return bank[session_count % len(bank)]


def _pick_word(total_sessions: int) -> Dict[str, str]:
    return IT_WORDS[total_sessions % len(IT_WORDS)]


def _get_weak_topics(chat_id: int, limit: int = 1) -> list:
    with db.connect() as conn:
        quiz_rows = conn.execute(
            """SELECT topic, SUM(correct), SUM(total)
               FROM quiz_results WHERE chat_id = ?
               GROUP BY topic HAVING SUM(total) >= 3""",
            (chat_id,),
        ).fetchall()
        task_rows = conn.execute(
            """SELECT topic, SUM(1 - completed), COUNT(*)
               FROM task_completions WHERE chat_id = ?
               GROUP BY topic HAVING COUNT(*) >= 2""",
            (chat_id,),
        ).fetchall()

    quiz_scores = {t: (c, total) for t, c, total in quiz_rows}
    task_scores = {t: (f, total) for t, f, total in task_rows}

    all_topics = set(quiz_scores) | set(task_scores)
    if not all_topics:
        return []

    def weakness(topic: str) -> float:
        parts = []
        if topic in quiz_scores:
            c, t = quiz_scores[topic]
            parts.append(1 - c / t)
        if topic in task_scores:
            f, t = task_scores[topic]
            parts.append(f / t)
        return sum(parts) / len(parts)

    ranked = sorted(all_topics, key=weakness, reverse=True)[:limit]

    result = []
    for topic in ranked:
        if topic in quiz_scores:
            c, t = quiz_scores[topic]
            hint = f"{round(100 * c / t)}% в квизах"
        else:
            f, t = task_scores[topic]
            hint = f"{round(100 * f / t)}% задач не выполнено"
        result.append({"topic": topic, "label": TOPICS.get(topic, topic), "hint": hint})

    return result


def _format_progress_fact(chat_id: int) -> str:
    stats = get_stats(chat_id)
    topics = stats["topics"]
    streak = stats["streak"]

    if not topics:
        return ""

    total = sum(t["count"] for t in topics)
    top = topics[0]

    if streak >= 7:
        return f"📊 {streak} дней подряд — это уже привычка. Продолжай."
    if streak >= 3:
        return f"📊 {streak} дня подряд. Набираешь темп."
    if top["count"] >= 10:
        return f"📊 {top['count']} сессий по теме {top['label']} — серьёзная база."
    if total >= 5:
        return f"📊 {total} сессий за всё время. Каждая — вклад в итог."
    return ""


def build_morning_brief(chat_id: int, gilfoyle: bool = False) -> str:
    last = _get_last_session(chat_id)

    if not last:
        return ""

    topic = last["topic"]
    days_ago = last["days_ago"]
    label = last["label"]

    session_count = _get_topic_session_count(chat_id, topic)
    total = _get_total_session_count(chat_id)

    task = _pick_task(topic, session_count)
    word = _pick_word(total)
    progress = _format_progress_fact(chat_id)

    weak = _get_weak_topics(chat_id)

    if gilfoyle:
        lines = []
        when = "Сегодня" if days_ago == 0 else ("Вчера" if days_ago == 1 else f"{days_ago} дн. назад")
        lines.append(f"Последнее: {label} ({when}).")
        lines.append(f"Сегодня: {task['task']}")
        lines.append(f"{word['word']} — {word['translation']}. \"{word['example']}\"")
        if weak:
            w = weak[0]
            lines.append(f"Слабо: {w['label']} — {w['hint']}. Иди учи.")
        return "\n".join(lines)

    lines = []

    if days_ago == 0:
        lines.append(f"📍 Сегодня уже изучал: {label}")
    elif days_ago == 1:
        lines.append(f"📍 Вчера изучал: {label}")
    else:
        lines.append(f"📍 Последняя тема: {label} ({days_ago} дн. назад)")

    lines.append(f"🎯 Задача на сегодня:\n{task['task']}")
    lines.append(f"💡 {task['tip']}")

    lines.append(
        f"🇬🇧 Слово дня: {word['word']} — {word['translation']}\n"
        f"   \"{word['example']}\""
    )

    if progress:
        lines.append(progress)

    if weak:
        w = weak[0]
        lines.append(f"⚠️ Слабое место: {w['label']} — {w['hint']}. Стоит повторить.")

    lines.append(format_path_short(chat_id))

    return "\n\n".join(lines)

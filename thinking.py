import random
import db
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional

import logging

from openai_client import client
from config import ASSISTANT_DB_PATH, USER_TIMEZONE, OPENAI_CHAT_MODEL

logger = logging.getLogger(__name__)

TZ = ZoneInfo(USER_TIMEZONE)

SCENARIOS = [
    {
        "id": "slow_server",
        "symptom": (
            "Коллеги сообщают что приложение работает очень медленно.\n"
            "Время ответа выросло с 200ms до 5-10 секунд. Ошибок нет — просто всё тормозит."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Железо: CPU throttling, диск умирает (высокий I/O wait)\n"
            "Ядро: высокий load average, swap активно используется, OOM killer срабатывал\n"
            "Процессы: один процесс съедает CPU или RAM\n"
            "Сеть: потеря пакетов, переполнение очереди соединений\n"
            "Приложение: медленные SQL-запросы, утечка памяти, thread pool исчерпан"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. uptime — load average за 1/5/15 мин. Понять масштаб и динамику\n"
            "2. free -h — память и swap. Если swap > 0 — это уже проблема\n"
            "3. top / htop — кто ест CPU или RAM прямо сейчас\n"
            "4. iostat -x 1 3 — I/O диска. iowait > 20% = диск является узким местом\n"
            "5. df -h — место на диске. 100% = катастрофа, всё встанет\n"
            "6. journalctl -p err --since '30 min ago' — ошибки в системе\n"
            "7. Логи приложения — медленные запросы, таймауты"
        ),
        "key_insight": (
            "Начинай с ресурсов — CPU, RAM, Disk, Network. Это даёт картину за 60 секунд. "
            "Только потом иди в логи приложения. Никогда не начинай с логов — потеряешь время "
            "на детали пока не знаешь где проблема."
        ),
        "framework": "USE Method: Utilization (загрузка) → Saturation (очередь) → Errors (ошибки)",
    },
    {
        "id": "service_down",
        "symptom": (
            "После рестарта сервера твой сервис не поднимается.\n"
            "systemctl status показывает: failed. Пользователи не могут работать."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Конфигурация: путь к файлу конфига изменился или файл отсутствует\n"
            "Зависимости: БД не запустилась раньше сервиса, порт занят другим процессом\n"
            "Код: синтаксическая ошибка в коде после обновления\n"
            "Окружение: переменные окружения не заданы, venv не активирован\n"
            "Права: файл не исполняемый, нет прав на папку"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. systemctl status service — exit code и последние строки лога\n"
            "2. journalctl -u service -n 50 — полные логи, ищешь строку с ошибкой\n"
            "3. Смотришь строку ExecStart= — правильная ли команда запуска\n"
            "4. Запускаешь команду вручную из терминала — видишь реальную ошибку\n"
            "5. Проверяешь файлы конфига — существуют ли, правильные ли права\n"
            "6. Проверяешь зависимости — БД доступна? нужный порт свободен?"
        ),
        "key_insight": (
            "Три шага всегда: systemctl status (код ошибки) → journalctl (причина) → "
            "запуск вручную (точная ошибка). Exit code говорит многое: "
            "1 = ошибка приложения, 127 = файл не найден, 137 = убит OOM killer."
        ),
        "framework": "Symptom → Logs → Manual run: три уровня детализации",
    },
    {
        "id": "disk_full",
        "symptom": (
            "Приложение перестало писать логи. В cron появились ошибки:\n"
            "'No space left on device'. Диск заполнен."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Логи приложения: выросли без ротации\n"
            "journald: системный журнал занял много места\n"
            "Docker: старые образы и остановленные контейнеры\n"
            "Временные файлы: /tmp, /var/tmp\n"
            "Ядро: core dumps после падений процессов\n"
            "БД: выросла база данных"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. df -h — какой именно раздел заполнен (/ или /var или другой)\n"
            "2. du -sh /var/* | sort -h — что занимает место в /var\n"
            "3. du -sh /var/log/* | sort -h — какие логи разрослись\n"
            "4. journalctl --disk-usage — сколько занимает journald\n"
            "5. docker system df — если Docker есть\n"
            "6. find /var /tmp -size +500M -type f 2>/dev/null — большие файлы\n"
            "7. Чистка: truncate логи, docker system prune, journalctl --vacuum-size=500M"
        ),
        "key_insight": (
            "Диск чистят сверху вниз: df показывает раздел → du идёт от папки к папке → "
            "находишь большое → чистишь. Никогда не удаляй файл не зная что это. "
            "truncate -s 0 file.log — обнулить лог без удаления (процесс продолжит писать)."
        ),
        "framework": "Локализация (df) → Поиск виновника (du) → Очистка",
    },
    {
        "id": "no_ssh",
        "symptom": (
            "Не можешь подключиться к серверу по SSH.\n"
            "Connection timeout. Сервер должен быть включён — ты его только что перезагружал."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Сеть: сервер вообще недоступен, кабель, роутер\n"
            "Firewall: iptables или ufw заблокировал порт 22\n"
            "fail2ban: твой IP забанен после неудачных попыток\n"
            "sshd: демон не запустился после перезагрузки\n"
            "Конфигурация: изменили порт или PermitRootLogin\n"
            "Ресурсы: сервер перегружен, не успевает принять соединение"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. ping server_ip — сервер вообще живой и отвечает на сеть?\n"
            "2. nc -zv server_ip 22 — порт 22 открыт и слушает?\n"
            "3. Если есть консоль/VNC: systemctl status sshd\n"
            "4. ufw status / iptables -L — не заблокирован ли порт\n"
            "5. fail2ban-client status sshd — не забанен ли твой IP\n"
            "6. Попробовать другой порт или другой ключ"
        ),
        "key_insight": (
            "Диагностируй снаружи → внутрь: Сеть (ping) → Порт (nc) → Сервис (systemctl) → "
            "Конфиг. Не лезь в конфиги пока не знаешь на каком уровне проблема. "
            "Connection timeout ≠ Connection refused: timeout = не доходит до порта, "
            "refused = порт закрыт или сервис не слушает."
        ),
        "framework": "Network → Port → Service → Config: от внешнего к внутреннему",
    },
    {
        "id": "crash_loop",
        "symptom": (
            "systemctl status показывает что сервис перезапускается каждые 30 секунд.\n"
            "Restart=on-failure работает, но сервис так и не поднимается."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Код: исключение при старте, синтаксическая ошибка\n"
            "Конфиг: неверные параметры, отсутствующий файл конфигурации\n"
            "Зависимости: порт занят, БД недоступна, API не отвечает\n"
            "Ресурсы: OOM killer убивает сразу после старта\n"
            "Права: нет прав на сокет, файл или папку"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. systemctl status service — exit code последнего падения\n"
            "2. journalctl -u service -n 100 — что происходит перед 'Process exited'\n"
            "3. Читаешь последние строки перед падением — там ошибка\n"
            "4. Запускаешь команду вручную — видишь полный вывод интерактивно\n"
            "5. Проверяешь зависимости: ss -tlnp | grep PORT — порт занят?\n"
            "6. journalctl -k | grep -i oom — не OOM killer ли причина"
        ),
        "key_insight": (
            "Exit code — первая зацепка: 1 = ошибка приложения, 127 = исполняемый файл "
            "не найден, 137 = убит сигналом (часто OOM). Запуск вручную — самый быстрый "
            "способ увидеть реальную ошибку без фильтрации systemd."
        ),
        "framework": "Exit code → Logs → Manual run → Dependencies",
    },
    {
        "id": "high_cpu",
        "symptom": (
            "load average показывает 8.0 при 4 CPU.\n"
            "Сервер еле отвечает на команды, top зависает при открытии."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Процессы: один процесс в бесконечном цикле, runaway process\n"
            "I/O wait: высокий iowait — ждут диск, а не CPU (похожий симптом!)\n"
            "Ядро: много процессов в очереди (D-state, ждут IO)\n"
            "Компиляция/сборка: неожиданный build процесс\n"
            "Атака: майнер, DDoS обработка"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. uptime — динамика load average: растёт или стабилизировалась?\n"
            "2. top — смотришь us (user) vs sy (system) vs wa (iowait)\n"
            "3. Если wa > 20%: проблема в диске, не CPU — идёшь в iostat\n"
            "4. Если us высокий: ps aux --sort=-%cpu | head -10 — находишь процесс\n"
            "5. ps aux | grep ' D ' — процессы в D-state (ждут IO)\n"
            "6. kill -15 PID — пробуешь мягко завершить процесс-виновника"
        ),
        "key_insight": (
            "iowait и высокий CPU — разные проблемы с одинаковым симптомом. "
            "Смотри столбец 'wa' в top. iowait > 20% = диск узкое место, не CPU. "
            "Ещё: load average включает D-state процессы (ждут IO) — "
            "load 8.0 на 4 CPU не обязательно значит CPU перегружен."
        ),
        "framework": "Load Average → CPU vs IO → Process → Action",
    },
    {
        "id": "oom",
        "symptom": (
            "Приложение несколько раз в день падает без очевидной причины.\n"
            "В логах приложения — ничего. Просто обрывается на середине."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "OOM killer: ядро убивает процесс когда память заканчивается\n"
            "Утечка памяти: приложение потребляет RAM постепенно\n"
            "Внешний сигнал: кто-то или что-то посылает SIGKILL\n"
            "Segfault: ошибка в коде, краш на уровне C-библиотеки\n"
            "Watchdog: systemd убивает процесс по таймауту"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. journalctl -k | grep -i 'oom\\|killed\\|out of memory' — был ли OOM killer\n"
            "2. dmesg | grep -i 'oom\\|killed' — то же в kernel log\n"
            "3. journalctl -u service | grep -i 'signal\\|killed\\|segfault'\n"
            "4. free -h — сколько памяти доступно сейчас\n"
            "5. ps aux --sort=-%mem | head -10 — кто потребляет RAM\n"
            "6. watch -n 5 'ps aux --sort=-%mem | head -5' — мониторинг в динамике"
        ),
        "key_insight": (
            "Если в логах приложения ничего нет — причина снаружи приложения. "
            "OOM killer убивает без предупреждения, логов в приложении не будет. "
            "Ищи в kernel log (dmesg, journalctl -k). "
            "После OOM событие: 'Out of memory: Kill process PID (name) score X'."
        ),
        "framework": "Kernel logs first: если приложение молчит — смотри за его пределы",
    },
    {
        "id": "after_deploy",
        "symptom": (
            "Только что задеплоили новую версию приложения.\n"
            "Теперь половина запросов возвращает 500 Internal Server Error."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Код: баг в новой версии, необработанное исключение\n"
            "Конфигурация: новая переменная окружения не добавлена в prod\n"
            "Зависимости: новая библиотека не установлена, версия несовместима\n"
            "БД: схема изменилась, миграция не применена\n"
            "Интеграции: изменился формат API, внешний сервис не обновлён"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. Первый вопрос: что именно изменилось? git log --oneline -5\n"
            "2. Логи приложения — какие конкретно ошибки 500, traceback\n"
            "3. Проверяешь env переменные — все ли заданы для новой версии\n"
            "4. Проверяешь зависимости — pip freeze или npm list\n"
            "5. Если есть — откат на предыдущую версию (rollback)\n"
            "6. После отката — спокойно разбираешь причину"
        ),
        "key_insight": (
            "Первый вопрос при инциденте после деплоя: 'что изменилось?' — не 'почему сломалось'. "
            "Откат — это не поражение, это инструмент. Сначала восстановить работу, "
            "потом разбираться. 50% ошибок после деплоя — забытая env переменная или "
            "неприменённая миграция БД."
        ),
        "framework": "What changed? → Rollback if needed → Root cause",
    },
    {
        "id": "network_slow",
        "symptom": (
            "Запросы между сервисами внутри сети стали медленными.\n"
            "Latency выросла с 1-2ms до 50-100ms. Внешний интернет работает нормально."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Физика: перегруженный сетевой коммутатор, битый кабель\n"
            "Пакеты: потери пакетов (retransmit = x2 latency)\n"
            "DNS: медленный DNS резолвинг внутри сети\n"
            "Буферы: переполнение сетевых буферов под нагрузкой\n"
            "Конкуренция: другой процесс забивает канал (backup, синхронизация)\n"
            "NTP: рассинхронизация времени вызывает странные задержки в TLS"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. ping server_ip -c 20 — базовый RTT и потери пакетов\n"
            "2. mtr server_ip — трассировка с статистикой потерь на каждом хопе\n"
            "3. ss -s — статистика сокетов: много retransmits?\n"
            "4. ip -s link — ошибки на сетевом интерфейсе\n"
            "5. iftop или nethogs — кто занимает полосу прямо сейчас\n"
            "6. dig внутренний_хост — время DNS резолвинга"
        ),
        "key_insight": (
            "Высокая latency внутри сети часто маскируется под проблему приложения. "
            "Проверяй сеть если логи приложения чистые. "
            "Потеря пакетов 1% = TCP retransmit = задержка 200-1000ms. "
            "mtr лучше traceroute: показывает статистику потерь на каждом hop в реальном времени."
        ),
        "framework": "Connectivity (ping) → Path (mtr) → Bandwidth (iftop) → DNS",
    },
    {
        "id": "db_down",
        "symptom": (
            "Приложение падает с ошибкой:\n"
            "'Connection refused' при попытке подключиться к PostgreSQL на localhost."
        ),
        "layers": (
            "Где может быть причина:\n\n"
            "Сервис: PostgreSQL не запущен или упал\n"
            "Диск: /var/lib/postgresql заполнен, БД не может писать\n"
            "Память: OOM killer убил postgres\n"
            "Конфиг: pg_hba.conf не разрешает подключение\n"
            "Порт: что-то другое занимает 5432\n"
            "Пользователь: нет роли или пароль изменился"
        ),
        "ideal_plan": (
            "Правильный порядок диагностики:\n\n"
            "1. systemctl status postgresql — запущен ли, exit code\n"
            "2. ss -tlnp | grep 5432 — слушает ли порт\n"
            "3. psql -U postgres — подключиться локально под системным пользователем\n"
            "4. journalctl -u postgresql -n 50 — логи БД\n"
            "5. df -h /var/lib/postgresql — есть ли место для БД\n"
            "6. dmesg | grep -i oom — не убил ли OOM killer"
        ),
        "key_insight": (
            "Connection refused = порт не слушает (сервис не запущен или упал). "
            "Connection timeout = файрвол или сеть. "
            "Разные сообщения об ошибке — разные проблемы. Читай сообщение внимательно. "
            "PostgreSQL часто падает из-за заполненного диска — это первое что проверяй."
        ),
        "framework": "Service status → Port → Local connect → Logs → Resources",
    },
]


def init_thinking_db() -> None:
    with db.connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thinking_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                wrote_plan INTEGER NOT NULL,
                covered_pct INTEGER
            )
        """)


def log_thinking_session(
    chat_id: int,
    scenario_id: str,
    wrote_plan: bool,
    covered_pct: Optional[int] = None,
) -> None:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    with db.connect() as conn:
        conn.execute(
            """INSERT INTO thinking_sessions
               (chat_id, date, scenario_id, wrote_plan, covered_pct)
               VALUES (?, ?, ?, ?, ?)""",
            (chat_id, today, scenario_id, int(wrote_plan), covered_pct),
        )


def get_scenario() -> Dict[str, Any]:
    return random.choice(SCENARIOS)


def format_symptom(scenario: Dict[str, Any]) -> str:
    return (
        f"Сценарий SRE\n\n"
        f"Симптом:\n{scenario['symptom']}\n\n"
        f"Как ты подходишь к диагностике?\n"
        f"Напиши своими словами — что проверишь первым, вторым, почему именно так."
    )


def format_full_breakdown(scenario: Dict[str, Any]) -> str:
    return (
        f"{scenario['layers']}\n\n"
        f"{scenario['ideal_plan']}\n\n"
        f"Ключевой инсайт:\n{scenario['key_insight']}\n\n"
        f"Фреймворк: {scenario['framework']}"
    )


def evaluate_user_plan(
    user_plan: str,
    scenario: Dict[str, Any],
) -> str:
    tone = "Отвечай как опытный SRE-ментор — конкретно, честно, без лишней мотивации."

    prompt = f"""Ты оцениваешь план диагностики Junior SRE.

Сценарий: {scenario['symptom']}

Эталонный план диагностики:
{scenario['ideal_plan']}

Ключевой инсайт: {scenario['key_insight']}

План пользователя:
{user_plan}

{tone}

Ответь в формате:
Что правильно: [что совпало с эталоном]
Что упущено: [важные шаги которых нет]
Главная ошибка в мышлении: [если есть — одна ключевая]
Инсайт: [главное что нужно запомнить из этого сценария]

Будь конкретен. Без общих слов. Максимум 150 слов."""

    try:
        response = client.responses.create(
            model=OPENAI_CHAT_MODEL,
            input=prompt,
            max_output_tokens=300,
            store=False,
        )
        return response.output_text.strip()
    except Exception:
        logger.exception("evaluate_user_plan: OpenAI call failed")
        return "Не удалось получить оценку. Попробуй ещё раз."

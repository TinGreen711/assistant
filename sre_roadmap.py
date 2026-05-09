import db
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional

from config import USER_TIMEZONE

TZ = ZoneInfo(USER_TIMEZONE)

# Каждый скилл: id, label, sessions (целевое кол-во сессий), criteria (что нужно знать)
ROADMAP: Dict[str, Dict[str, Any]] = {
    "linux": {
        "label": "Linux",
        "skills": [
            {"id": "linux_processes", "label": "Процессы", "sessions": 25,
             "criteria": "kill -9/-15, ps aux, /proc, top, strace"},
            {"id": "linux_filesystem", "label": "Файловая система", "sessions": 35,
             "criteria": "chmod, find, df/du, inodes, mount, ln"},
            {"id": "linux_network", "label": "Сеть и сокеты", "sessions": 35,
             "criteria": "ss, ip addr, /etc/hosts, resolv.conf, iptables"},
            {"id": "linux_security", "label": "Безопасность", "sessions": 25,
             "criteria": "sudo, /etc/passwd, SSH-ключи, umask, SELinux"},
        ],
    },
    "networks": {
        "label": "Сети",
        "skills": [
            {"id": "net_basics", "label": "TCP/IP основы", "sessions": 20,
             "criteria": "IP, MAC, ARP, ICMP, ping, OSI"},
            {"id": "net_dns_http", "label": "DNS и HTTP", "sessions": 25,
             "criteria": "DNS-записи, HTTP-методы, статус-коды, TLS"},
            {"id": "net_routing", "label": "Маршрутизация", "sessions": 20,
             "criteria": "route table, NAT, CIDR, traceroute, BGP-basics"},
            {"id": "net_debug", "label": "Диагностика", "sessions": 15,
             "criteria": "tcpdump, curl -v, nmap, Wireshark, ss -tlnp"},
        ],
    },
    "docker": {
        "label": "Docker",
        "skills": [
            {"id": "docker_basics", "label": "Контейнеры", "sessions": 20,
             "criteria": "run, ps, logs, exec, rm, inspect"},
            {"id": "docker_images", "label": "Images / Dockerfile", "sessions": 25,
             "criteria": "build, FROM/RUN/CMD/COPY, layers, registry"},
            {"id": "docker_compose", "label": "Compose", "sessions": 20,
             "criteria": "docker-compose up/down, services, depends_on"},
            {"id": "docker_volumes", "label": "Volumes и сети", "sessions": 15,
             "criteria": "volume, bind mount, bridge/host сеть, port mapping"},
        ],
    },
    "git": {
        "label": "Git",
        "skills": [
            {"id": "git_basics", "label": "Основы", "sessions": 15,
             "criteria": "init, add, commit, status, log, diff"},
            {"id": "git_branches", "label": "Ветки", "sessions": 15,
             "criteria": "branch, checkout, merge, rebase, cherry-pick"},
            {"id": "git_workflow", "label": "Workflow", "sessions": 12,
             "criteria": "PR, stash, reset, revert, bisect, blame"},
            {"id": "git_remote", "label": "Remote и CI", "sessions": 8,
             "criteria": "push/fetch, origin/upstream, GitHub Actions, hooks"},
        ],
    },
    "ai": {
        "label": "AI",
        "skills": [
            {"id": "ai_api", "label": "API и токены", "sessions": 10,
             "criteria": "токены, context window, API-вызовы, стоимость"},
            {"id": "ai_models", "label": "Модели", "sessions": 15,
             "criteria": "GPT-4, Claude, температура, top-p, streaming"},
            {"id": "ai_tools", "label": "Tool use / RAG", "sessions": 10,
             "criteria": "function calling, embeddings, векторный поиск"},
            {"id": "ai_arch", "label": "Архитектура", "sessions": 5,
             "criteria": "fine-tuning, RLHF, inference latency, quantization"},
        ],
    },
    "prompt": {
        "label": "Prompt Eng",
        "skills": [
            {"id": "prompt_basics", "label": "Основы", "sessions": 8,
             "criteria": "zero-shot, few-shot, role prompting, delimiters"},
            {"id": "prompt_chain", "label": "Цепочки", "sessions": 8,
             "criteria": "chain-of-thought, step-by-step, self-consistency"},
            {"id": "prompt_struct", "label": "Структура", "sessions": 5,
             "criteria": "JSON mode, format constraints, output parsing"},
            {"id": "prompt_adv", "label": "Продвинутые", "sessions": 4,
             "criteria": "injection defense, prompt eval, meta-prompting"},
        ],
    },
}


def get_skill_progress(chat_id: int, topic_key: str) -> List[Dict[str, Any]]:
    """Возвращает список скиллов топика с текущим прогрессом (pct, done, current)."""
    topic = ROADMAP.get(topic_key)
    if not topic:
        return []

    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM study_sessions WHERE chat_id = ? AND topic = ?",
            (chat_id, topic_key),
        ).fetchone()
    sessions_done = row[0] if row else 0

    result = []
    remaining = sessions_done
    for skill in topic["skills"]:
        target = skill["sessions"]
        done = min(remaining, target)
        remaining = max(0, remaining - target)
        pct = min(100.0, done / target * 100) if target else 0
        result.append({
            **skill,
            "done": done,
            "pct": pct,
            "completed": pct >= 100,
            "current": done > 0 and pct < 100,  # активный скилл
        })

    # Если все скиллы завершены, последний помечаем как «current»
    if all(s["completed"] for s in result) and result:
        result[-1]["current"] = True

    return result


def get_current_skill(chat_id: int, topic_key: str) -> Optional[Dict[str, Any]]:
    """Возвращает скилл который сейчас изучается (первый незавершённый)."""
    skills = get_skill_progress(chat_id, topic_key)
    for s in skills:
        if not s["completed"]:
            return s
    return skills[-1] if skills else None


def format_topic_skills(chat_id: int, topic_key: str) -> str:
    """Компактная строка с прогрессом по скиллам внутри топика."""
    skills = get_skill_progress(chat_id, topic_key)
    if not skills:
        return ""
    parts = []
    for s in skills:
        if s["completed"]:
            parts.append(f"✓ {s['label']}")
        elif s["current"]:
            parts.append(f"→ {s['label']} {round(s['pct'])}%")
        else:
            parts.append(f"  {s['label']}")
    return " | ".join(parts)

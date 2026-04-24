import re
from typing import Dict, List


DOMAINS = {
    "assistant_project": "Проект ассистента",
    "income": "Доход",
    "learning": "Обучение",
    "work": "Работа",
    "health": "Здоровье и восстановление",
    "family": "Семья и быт",
    "admin": "Организация и рутина",
    "general": "Общее",
}


DOMAIN_KEYWORDS = {
    "assistant_project": [
        "ассистент",
        "бот",
        "telegram",
        "телеграм",
        "openai",
        "обсидиан",
        "obsidian",
        "router",
        "brain",
        "бот.py",
        "brain.py",
        "project",
        "проект",
        "код бота",
    ],
    "income": [
        "доход",
        "деньги",
        "заработ",
        "монет",
        "клиент",
        "продаж",
        "прибыль",
        "услуга",
        "заработок",
    ],
    "learning": [
        "учить",
        "изуч",
        "обуч",
        "linux",
        "линукс",
        "devops",
        "docker",
        "python",
        "код",
        "программ",
        "практика",
    ],
    "work": [
        "работа",
        "смена",
        "магазин",
        "сервис",
        "мастерская",
        "ремонт",
        "клиент",
        "заказ",
    ],
    "health": [
        "устал",
        "силы",
        "энергия",
        "восстановление",
        "сон",
        "отдых",
        "йога",
        "колено",
        "здоровье",
    ],
    "family": [
        "семья",
        "жена",
        "сын",
        "лев",
        "дом",
        "быт",
        "ребёнок",
        "ребенок",
    ],
    "admin": [
        "план",
        "расписание",
        "организация",
        "порядок",
        "рутина",
        "документы",
        "заметки",
        "таблица",
        "weekly",
        "summary",
    ],
}


RELATED_DOMAINS = {
    "assistant_project": {"learning", "income", "admin"},
    "income": {"work", "assistant_project", "admin"},
    "learning": {"assistant_project", "admin"},
    "work": {"income", "admin"},
    "health": {"family"},
    "family": {"health", "admin"},
    "admin": {"assistant_project", "income", "learning", "work", "family"},
    "general": set(),
}


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _contains_any(text: str, keywords: List[str]) -> List[str]:
    found = []
    for kw in keywords:
        if kw in text:
            found.append(kw)
    return found


def classify_domain(user_text: str) -> Dict:
    text = _normalize(user_text)

    scores = {domain: 0 for domain in DOMAINS}
    signals = {domain: [] for domain in DOMAINS}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        found = _contains_any(text, keywords)
        if found:
            scores[domain] += len(found) * 2
            signals[domain].extend(found)

    if all(score == 0 for score in scores.values()):
        scores["general"] = 1
        signals["general"].append("default")

    best_domain = "general"
    best_score = -1

    for domain, score in scores.items():
        if score > best_score:
            best_score = score
            best_domain = domain

    confidence = "low"
    if best_score >= 6:
        confidence = "high"
    elif best_score >= 3:
        confidence = "medium"

    summary_map = {
        "assistant_project": "Запрос относится к проекту ассистента.",
        "income": "Запрос относится к доходу или деньгам.",
        "learning": "Запрос относится к обучению или практике.",
        "work": "Запрос относится к работе.",
        "health": "Запрос относится к ресурсу, здоровью или восстановлению.",
        "family": "Запрос относится к семье или быту.",
        "admin": "Запрос относится к организации, планированию или рутине.",
        "general": "Запрос без ярко выраженной области.",
    }

    return {
        "domain": best_domain,
        "label": DOMAINS[best_domain],
        "confidence": confidence,
        "signals": signals[best_domain],
        "summary": summary_map[best_domain],
        "scores": scores,
    }


def assess_domain_alignment(active_focus_domain: str, request_domain: str) -> Dict:
    active_focus_domain = (active_focus_domain or "general").strip()
    request_domain = (request_domain or "general").strip()

    if not active_focus_domain or active_focus_domain == "general":
        return {
            "relation": "unknown",
            "summary": "Главный фокус дня пока не задан.",
        }

    if active_focus_domain == request_domain:
        return {
            "relation": "aligned",
            "summary": "Запрос совпадает с главным фокусом дня.",
        }

    related = RELATED_DOMAINS.get(active_focus_domain, set())
    if request_domain in related:
        return {
            "relation": "related",
            "summary": "Запрос связан с главным фокусом дня, но не совпадает с ним напрямую.",
        }

    return {
        "relation": "off_focus",
        "summary": "Запрос уводит в сторону от главного фокуса дня.",
    }

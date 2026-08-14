from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable


CITY_ALIASES = {
    "gurgaon": "gurugram",
    "new delhi": "delhi",
    "delhi": "delhi",
    "delhi ncr": "ncr",
    "bangalore": "bengaluru",
}


TRUE_VALUES = {"y", "yes", "true", "1", "verified"}
FALSE_VALUES = {"n", "no", "false", "0", "unverified"}


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    elif len(digits) == 10:
        digits = "91" + digits
    return digits


def normalize_name(value: str | None) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    return value.title()


def name_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def normalize_city(value: str | None) -> str:
    city = re.sub(r"\s+", " ", (value or "").strip().lower())
    return CITY_ALIASES.get(city, city)


def parse_date(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_ctc_lpa(value: str | None) -> float | None:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        amount = float(raw)
    except ValueError:
        return None
    if amount > 1000:
        return round(amount / 100000, 2)
    return round(amount, 2)


def parse_rate(value: str | None) -> tuple[float | None, str | None]:
    raw = (value or "").strip().lower().replace(",", "")
    if not raw:
        return None, None
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(k)?\s*/\s*(hr|hour|month)$", raw)
    if not match:
        return None, None
    amount = float(match.group(1))
    if match.group(2):
        amount *= 1000
    unit = "hour" if match.group(3) in {"hr", "hour"} else "month"
    return round(amount, 2), unit


def parse_bool(value: str | None) -> bool | None:
    raw = (value or "").strip().lower()
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    return None


def normalize_status(value: str | None) -> str | None:
    raw = (value or "").strip().lower()
    if raw in {"active", "inactive", "paused"}:
        return raw
    return None


def split_skills(value: str | None) -> list[str]:
    seen: set[str] = set()
    skills: list[str] = []
    for item in (value or "").split(","):
        skill = re.sub(r"\s+", " ", item.strip().lower())
        if skill and skill not in seen:
            seen.add(skill)
            skills.append(skill)
    return skills


def skill_category(skills: Iterable[str]) -> str:
    skill_set = {s.lower() for s in skills}
    if skill_set & {"n8n", "zapier", "langchain"}:
        return "automation-heavy"
    if skill_set & {"react", "javascript", "fastapi", "rest apis"}:
        return "web-dev"
    if skill_set & {"sql", "mysql", "mongodb", "pandas", "python", "web scraping", "selenium"}:
        return "data"
    return "uncategorized"

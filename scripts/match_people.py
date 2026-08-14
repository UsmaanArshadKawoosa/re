from __future__ import annotations

from database import USE_POSTGRES
from normalize import name_key, normalize_city, normalize_email, normalize_phone


def find_existing_person(
    conn,
    *,
    email: str | None = None,
    phone: str | None = None,
) -> int | None:
    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)

    if normalized_email:
        row = conn.execute(
            "SELECT person_id FROM person_emails WHERE normalized_email = ?",
            (normalized_email,),
        ).fetchone()
        if row:
            return int(row["person_id"])

    if normalized_phone:
        row = conn.execute(
            "SELECT person_id FROM person_phones WHERE normalized_phone = ?",
            (normalized_phone,),
        ).fetchone()
        if row:
            return int(row["person_id"])

    return None


def create_or_get_person(
    conn,
    *,
    name: str,
    email: str | None,
    phone: str | None,
    city: str | None,
) -> int:
    existing_id = find_existing_person(conn, email=email, phone=phone)
    if existing_id:
        return existing_id

    normalized_name = name_key(name)
    normalized_city_val = normalize_city(city)

    if USE_POSTGRES:
        # PostgreSQL: use RETURNING id to get the new row's id
        row = conn.execute(
            """
            INSERT INTO people (canonical_name, normalized_name, primary_email, primary_phone, normalized_city)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            (name, normalized_name, normalize_email(email) or None, normalize_phone(phone) or None, normalized_city_val or None),
        ).fetchone()
        return int(row["id"])
    else:
        # SQLite: use cursor.lastrowid
        cursor = conn.execute(
            """
            INSERT INTO people (canonical_name, normalized_name, primary_email, primary_phone, normalized_city)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, normalized_name, normalize_email(email) or None, normalize_phone(phone) or None, normalized_city_val or None),
        )
        return int(cursor.lastrowid)


def update_person_basics(
    conn,
    *,
    person_id: int,
    name: str,
    email: str | None,
    phone: str | None,
    city: str | None,
) -> None:
    row = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if not row:
        return
    primary_email = row["primary_email"] or normalize_email(email) or None
    primary_phone = row["primary_phone"] or normalize_phone(phone) or None
    normalized_city_val = row["normalized_city"] or normalize_city(city) or None
    canonical_name = row["canonical_name"] if row["canonical_name"] else name
    conn.execute(
        """
        UPDATE people
        SET canonical_name = ?, primary_email = ?, primary_phone = ?, normalized_city = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (canonical_name, primary_email, primary_phone, normalized_city_val, person_id),
    )

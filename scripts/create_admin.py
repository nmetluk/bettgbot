"""CLI для создания первого админа веб-админки (TASK-019).

Использование:
    PYTHONPATH=. uv run python scripts/create_admin.py --login admin --password "secret"
    PYTHONPATH=. uv run python scripts/create_admin.py --login admin --password "secret" --full-name "Имя"

Хеширует пароль через `bcrypt` напрямую с cost=12 (по docs/05-admin-spec.md).
Если админ с таким login уже есть — отказ с понятным сообщением, exit 1.

Примечание: passlib 1.7.4 несовместима с bcrypt 5.x (внутри passlib падает
на «password cannot be longer than 72 bytes» даже на коротких паролях из-за
изменения API bcrypt). Поэтому используем bcrypt напрямую — формат хэша
тот же (`$2b$...`), `bcrypt.checkpw(...)` в TASK-020 сверит как обычно.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import bcrypt
from sqlalchemy import select
from src.shared.db import SessionLocal
from src.shared.models import AdminUser

_BCRYPT_ROUNDS = 12
_BCRYPT_MAX_BYTES = 72  # bcrypt jam limit


def _hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raise ValueError(
            f"password is {len(raw)} bytes (max {_BCRYPT_MAX_BYTES} for bcrypt); "
            "сократите или используйте argon2 (отдельная задача)"
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("ascii")


async def create_admin(*, login: str, password: str, full_name: str | None) -> None:
    async with SessionLocal() as session:
        exists = await session.execute(select(AdminUser).where(AdminUser.login == login))
        if exists.scalar_one_or_none() is not None:
            print(f"❌ Админ с login={login!r} уже существует.", file=sys.stderr)
            sys.exit(1)

        admin = AdminUser(
            login=login,
            password_hash=_hash_password(password),
            full_name=full_name,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        print(f"✅ Создан админ id={admin.id} login={admin.login}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Создать админа.")
    parser.add_argument("--login", required=True, help="Уникальный логин (1-64 chars)")
    parser.add_argument(
        "--password", required=True, help="Пароль в открытом виде; будет хеширован bcrypt cost=12"
    )
    parser.add_argument("--full-name", default=None, help="Полное имя (опционально)")
    args = parser.parse_args()

    asyncio.run(
        create_admin(
            login=args.login,
            password=args.password,
            full_name=args.full_name,
        )
    )


if __name__ == "__main__":
    main()

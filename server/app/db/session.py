# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


logger = logging.getLogger(__name__)


_SQLITE_FALLBACK_PATH = Path(__file__).resolve().parents[2] / "local_demo.db"
_SQLITE_FALLBACK_URL = f"sqlite:///{_SQLITE_FALLBACK_PATH.as_posix()}"


def _create_engine(database_url: str):
    engine_kwargs: dict[str, object] = {}

    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_pre_ping"] = True
        if database_url.startswith("postgresql"):
            engine_kwargs["connect_args"] = {"connect_timeout": 2}

    return create_engine(database_url, **engine_kwargs)


def _build_engine():
    primary_url = settings.resolved_database_url
    try:
        # Local name distinct from the module-level ``engine`` below to avoid
        # shadowing it inside this factory.
        eng = _create_engine(primary_url)
        if not primary_url.startswith("sqlite"):
            with eng.connect() as connection:
                connection.execute(text("SELECT 1"))
        return eng
    except Exception:
        if settings.is_production_like or not primary_url.startswith("postgresql"):
            logger.exception("Primary database unavailable; refusing unsafe fallback.")
            raise
        logger.warning(
            "Development PostgreSQL unavailable. Falling back to local SQLite database at %s",
            _SQLITE_FALLBACK_PATH,
            exc_info=True,
        )
        return _create_engine(_SQLITE_FALLBACK_URL)


engine = _build_engine()
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, class_=Session, expire_on_commit=False
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

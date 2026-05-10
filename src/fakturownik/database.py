from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from fakturownik.config import get_app_paths
from fakturownik.models import Base, DEFAULT_SETTLEMENT_TYPE, DEFAULT_SETTLEMENT_TYPE_COLORS


paths = get_app_paths()
engine = create_engine(f"sqlite:///{paths.database_path}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_legacy_schema()
    _seed_settlement_type_configs()


def _migrate_legacy_schema() -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        client_columns = {column["name"] for column in inspector.get_columns("clients")}
        if "settlement_type" not in client_columns:
            connection.execute(
                text(
                    "ALTER TABLE clients "
                    f"ADD COLUMN settlement_type VARCHAR(64) NOT NULL DEFAULT '{DEFAULT_SETTLEMENT_TYPE}'"
                )
            )


def _seed_settlement_type_configs() -> None:
    with engine.begin() as connection:
        existing_count = connection.execute(
            text("SELECT COUNT(*) FROM settlement_type_configs")
        ).scalar_one()
        if existing_count:
            return
        for settlement_type, color_hex in DEFAULT_SETTLEMENT_TYPE_COLORS.items():
            connection.execute(
                text(
                    "INSERT INTO settlement_type_configs (settlement_type, color_hex) "
                    "VALUES (:settlement_type, :color_hex)"
                ),
                {
                    "settlement_type": settlement_type,
                    "color_hex": color_hex,
                },
            )


@contextmanager
def session_scope() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
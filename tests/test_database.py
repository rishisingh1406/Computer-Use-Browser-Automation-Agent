from sqlalchemy import text

from app.database.connection import create_tables, engine


def test_database_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_create_tables():
    create_tables()
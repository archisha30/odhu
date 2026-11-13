"""
SQLite database setup with SQLAlchemy.

The database is a single file, backend/data/odhu.db, with four tables:
  documents     one row per scanned document
  explanations  a document's explanation in another language, made on request
  questions     one row per voice question asked about a document
  api_calls     one row per Gnani or Gemini call, to track credits and quota

Tables are created when this module is first imported, if they don't exist yet.
New columns are added by add_missing_columns() below; for bigger changes, delete
odhu.db and restart.
"""

from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.data_dir / 'odhu.db'}",
    # FastAPI may use the connection from a different thread than the one that opened it.
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DocumentRecord(Base):
    """
    One scanned document. We store the extracted facts and the explanation,
    NOT the photo itself, so private bills aren't kept on disk.
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    language: Mapped[str] = mapped_column(String(8))
    # SHA-256 of the photo. If the exact same photo is scanned again in the same
    # language, we reuse this row instead of calling Gemini again.
    image_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16))  # "ok", "unclear" or "unsupported"
    extracted_json: Mapped[str | None] = mapped_column(Text)  # ExtractedDocument as JSON
    explanation: Mapped[str] = mapped_column(Text)
    audio_id: Mapped[str | None] = mapped_column(String(64))

    questions: Mapped[list["QuestionRecord"]] = relationship(
        back_populates="document", order_by="QuestionRecord.created_at"
    )
    explanations: Mapped[list["ExplanationRecord"]] = relationship()


class QuestionRecord(Base):
    """One voice question about a document, and the answer we gave."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    transcript: Mapped[str] = mapped_column(Text)  # what Gnani STT heard
    # The language the person spoke in; the answer is in this language too.
    language: Mapped[str | None] = mapped_column(String(8))
    answer: Mapped[str] = mapped_column(Text)
    audio_id: Mapped[str | None] = mapped_column(String(64))

    document: Mapped[DocumentRecord] = relationship(back_populates="questions")


class ExplanationRecord(Base):
    """
    A document's explanation in another language (e.g. a bill scanned in Kannada,
    heard later in English). Made from the saved facts once, then reused.
    """

    __tablename__ = "explanations"
    __table_args__ = (UniqueConstraint("document_id", "language"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    language: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    audio_id: Mapped[str | None] = mapped_column(String(64))


class ApiCallRecord(Base):
    """One call to an outside API. Lets us count Gnani credits and Gemini quota."""

    __tablename__ = "api_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    service: Mapped[str] = mapped_column(String(16))  # "gnani_stt", "gnani_tts" or "gemini"
    model: Mapped[str] = mapped_column(String(64), default="")  # Gemini model name
    duration_ms: Mapped[float] = mapped_column(Float)
    ok: Mapped[bool] = mapped_column(Boolean)


Base.metadata.create_all(engine)


def add_missing_columns() -> None:
    """
    create_all() makes new tables but never changes existing ones. If we add a
    column to a table later, add it here so older databases keep working.
    """
    new_columns = {"questions": {"language": "VARCHAR(8)"}}
    existing_tables = inspect(engine).get_table_names()
    with engine.begin() as connection:
        for table, columns in new_columns.items():
            if table not in existing_tables:
                continue
            have = {column["name"] for column in inspect(engine).get_columns(table)}
            for name, sql_type in columns.items():
                if name not in have:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))


add_missing_columns()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

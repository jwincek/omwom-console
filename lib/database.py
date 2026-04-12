from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_PATH = Path(__file__).parent.parent / "console.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


class Base(DeclarativeBase):
    pass


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    category = Column(String(50))
    action = Column(String(100))
    detail = Column(Text, default="")
    status = Column(String(20), default="success")


def init_db():
    Base.metadata.create_all(engine)


init_db()


def get_session() -> Session:
    return sessionmaker(bind=engine)()


def log_activity(category: str, action: str, detail: str = "", status: str = "success"):
    session = get_session()
    try:
        entry = ActivityLog(
            category=category,
            action=action,
            detail=detail,
            status=status,
        )
        session.add(entry)
        session.commit()
    finally:
        session.close()


def get_recent_activity(limit: int = 20):
    session = get_session()
    try:
        rows = (
            session.query(ActivityLog)
            .order_by(ActivityLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "timestamp": row.timestamp,
                "category": row.category,
                "action": row.action,
                "detail": row.detail,
                "status": row.status,
            }
            for row in rows
        ]
    finally:
        session.close()

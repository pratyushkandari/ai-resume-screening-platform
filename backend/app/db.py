# backend/app/db.py

import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://resume_user1:Resume123@localhost:5432/resume_db1"
)

# Connect pool parameters for production scalability
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _mask_url(url: str) -> str:
    try:
        if "@" in url:
            left, right = url.split("@", 1)
            if "//" in left:
                userinfo = left.split("//", 1)[1]
                user = userinfo.split(":")[0]
                return f"{user}:****@{right}"
        return "redacted"
    except Exception:
        return "redacted"


logger.info("[DB] Configured host: %s", _mask_url(SQLALCHEMY_DATABASE_URL))

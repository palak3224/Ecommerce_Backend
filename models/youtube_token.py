from sqlalchemy import Column, Integer, String, Boolean, DateTime
from common.database import db, BaseModel
import datetime

class YouTubeToken(BaseModel):
    __tablename__ = "youtube_tokens"
    id = Column(Integer, primary_key=True)
    access_token = Column(String(512), nullable=False)
    refresh_token = Column(String(512), nullable=False)
    token_type = Column(String(32), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow) 
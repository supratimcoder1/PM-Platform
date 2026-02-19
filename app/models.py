from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    score: int = Field(default=0)
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)
    time_taken_seconds: Optional[float] = Field(default=None)
    roll_number: Optional[str] = Field(default=None)
    rc_number: Optional[str] = Field(default=None)
    status: str = Field(default="pending")  # approved, rejected, pending

class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content_text: Optional[str] = Field(default=None)
    content_image: Optional[str] = Field(default=None)
    answer: str
    difficulty: str  # "Easy", "Medium", "Hard"
    points: int
    options: Optional[str] = Field(default=None)  # "A|B|C|D" for MCQ

class Admin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str

class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

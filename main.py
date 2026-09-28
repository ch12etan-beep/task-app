import os
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# --- Database setup -------------------------------------------------------
# Locally this uses a SQLite file. In production, set DATABASE_URL to your
# Postgres connection string (Neon / Supabase) and nothing else changes.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")
for prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(prefix):
        DATABASE_URL = DATABASE_URL.replace(prefix, "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="todo")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)  # creates tables on first run


def get_db():
    with SessionLocal() as db:
        yield db


# --- Request schemas ------------------------------------------------------
class UserIn(BaseModel):
    name: str


class TaskIn(BaseModel):
    title: str
    user_id: int


class StatusIn(BaseModel):
    status: Literal["todo", "in_progress", "done"]


def task_out(t: Task) -> dict:
    return {"id": t.id, "title": t.title, "status": t.status, "user_id": t.user_id}


# --- API routes -----------------------------------------------------------
app = FastAPI(title="Task Manager")


@app.post("/api/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if db.scalar(select(User).where(User.name == name)):
        raise HTTPException(409, "That name is already taken")
    user = User(name=name)
    db.add(user)
    db.commit()
    return {"id": user.id, "name": user.name}


@app.get("/api/users")
def list_users(db: Session = Depends(get_db)):
    return [{"id": u.id, "name": u.name} for u in db.scalars(select(User))]


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskIn, db: Session = Depends(get_db)):
    if not db.get(User, body.user_id):
        raise HTTPException(404, "User not found")
    if not body.title.strip():
        raise HTTPException(400, "Title is required")
    task = Task(title=body.title.strip(), user_id=body.user_id)
    db.add(task)
    db.commit()
    return task_out(task)


@app.get("/api/tasks")
def list_tasks(user_id: int, db: Session = Depends(get_db)):
    q = select(Task).where(Task.user_id == user_id).order_by(Task.id.desc())
    return [task_out(t) for t in db.scalars(q)]


@app.patch("/api/tasks/{task_id}")
def update_status(task_id: int, body: StatusIn, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    task.status = body.status
    db.commit()
    return task_out(task)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    db.delete(task)
    db.commit()


# Serve the frontend from the same server (must come last)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

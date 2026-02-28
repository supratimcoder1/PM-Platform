from contextlib import asynccontextmanager
from fastapi import FastAPI
import os
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from app.database import create_db_and_tables, engine
from app.routers import auth, admin, game
from app.routers.auth import create_initial_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        create_initial_admin(session)
    yield

from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="super-secret-puzzle-mania-key")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(game.router)


from fastapi import Request, Depends, HTTPException, status
import os
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models import Admin

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

def get_current_user(request: Request, session: Session = Depends(get_session)):
    username = request.session.get("user")
    if not username:
        return None
    statement = select(Admin).where(Admin.username == username)
    user = session.exec(statement).first()
    return user

def require_admin(request: Request, user: Admin = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

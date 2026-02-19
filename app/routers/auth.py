from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from passlib.context import CryptContext
from app.database import get_session
from app.models import Admin
from app.dependencies import templates

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})

@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    statement = select(Admin).where(Admin.username == username)
    user = session.exec(statement).first()
    
    if not user or not pwd_context.verify(password, user.password_hash):
        return templates.TemplateResponse("admin/login.html", {"request": request, "error": "Invalid credentials"})
    
    request.session["user"] = user.username
    return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

# Helper to create initial admin (can be called manually or via script)
def create_initial_admin(session: Session):
    if not session.exec(select(Admin)).first():
        hashed = pwd_context.hash("admin123")
        admin = Admin(username="admin", password_hash=hashed)
        session.add(admin)
        session.commit()

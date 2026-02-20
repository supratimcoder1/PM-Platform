import shutil
import uuid
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Request, Form, File, UploadFile, Depends, status
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Question, Team
from app.dependencies import templates, get_current_user

UPLOAD_DIR = Path("static/img/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
from app.dependencies import templates, get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/dashboard")
def dashboard(request: Request, user = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    
    questions = session.exec(select(Question)).all()
    # Only show approved teams in leaderboard on dashboard (or all, but maybe separate pending)
    teams = session.exec(select(Team).where(Team.status == "approved").order_by(Team.score.desc())).all()
    pending_teams = session.exec(select(Team).where(Team.status == "pending")).all()
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request, 
        "user": user, 
        "questions": questions,
        "teams": teams,
        "pending_teams": pending_teams
    })

@router.get("/export/csv") # Keeping URL simple, returning excel
def export_leaderboard(session: Session = Depends(get_session)):
    import pandas as pd
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    
    # Fetch all approved teams sorted by rank
    teams = session.exec(select(Team).where(Team.status == "approved").order_by(Team.score.desc(), Team.time_taken_seconds.asc())).all()
    
    data = []
    for i, team in enumerate(teams):
        time_str = "0s"
        if team.time_taken_seconds:
            m = int(team.time_taken_seconds // 60)
            s = int(team.time_taken_seconds % 60)
            ms = int((team.time_taken_seconds * 1000) % 1000)
            time_str = f"{m}m {s}s {ms}ms"
            
        data.append({
            "Rank": i + 1,
            "Team Name": team.name,
            "Roll Number": team.roll_number,
            "RC Number": team.rc_number,
            "Score": team.score,
            "Time Taken": time_str,
            "Start Time": team.start_time,
            "End Time": team.end_time
        })
        
    df = pd.DataFrame(data)
    
    # Create Excel buffer
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Leaderboard')
        
    buffer.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="puzzlemania_leaderboard.xlsx"'
    }
    
    return StreamingResponse(buffer, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@router.get("/team/approve/{team_id}")
def approve_team(team_id: int, user = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
        
    team = session.get(Team, team_id)
    if team:
        team.status = "approved"
        team.start_time = datetime.now() # Reset start time to approval time
        session.add(team)
        session.commit()
    return RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/team/reject/{team_id}")
def reject_team(team_id: int, user = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
        
    team = session.get(Team, team_id)
    if team:
        team.status = "rejected"
        session.add(team)
        session.commit()
    return RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/team/approve_all")
def approve_all_teams(user = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    
    pending_teams = session.exec(select(Team).where(Team.status == "pending")).all()
    for team in pending_teams:
        team.status = "approved"
        team.start_time = datetime.now()
        session.add(team)
    session.commit()
    return RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/leaderboard/export")
def export_leaderboard(user = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
        
    teams = session.exec(select(Team).where(Team.status == "approved").order_by(Team.score.desc())).all()
    
    data = []
    for i, t in enumerate(teams):
        time_str = "0s"
        if t.time_taken_seconds is not None:
            m = int(t.time_taken_seconds // 60)
            s = int(t.time_taken_seconds % 60)
            ms = int((t.time_taken_seconds * 1000) % 1000)
            time_str = f"{m}m {s}s {ms}ms"
            
        data.append({
            "Rank": i + 1,
            "Team Name": t.name,
            "Roll Number": t.roll_number,
            "RC Number": t.rc_number,
            "Score": t.score,
            "Time Taken": time_str,
            "Start Time": t.start_time,
            "End Time": t.end_time
        })
        
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Leaderboard')
        
    output.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="leaderboard_export.xlsx"'
    }
    return StreamingResponse(output, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@router.post("/question/add")
async def add_question(
    request: Request,
    content_text: str = Form(None),
    answer: str = Form(...),
    difficulty: str = Form(...),
    image_file: UploadFile = File(None),
    options: str = Form(None),
    user = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    
    # Handle Image Upload
    image_path = None
    if image_file and image_file.filename:
        # Generate unique filename
        file_extension = Path(image_file.filename).suffix
        if not file_extension:
            file_extension = ".png" # Default fallback
            
        new_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = UPLOAD_DIR / new_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
            
        image_path = f"/static/img/uploads/{new_filename}"

    # Auto-assign points
    if difficulty == "Easy":
        points = 10
    elif difficulty == "Medium":
        points = 15
    else:
        points = 20 # Hard
    
    question = Question(
        content_text=content_text,
        content_image=image_path,
        answer=answer,
        difficulty=difficulty,
        points=points,
        options=options
    )
    session.add(question)
    session.commit()
    return RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/question/delete/{q_id}")
def delete_question(q_id: int, user = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    
    question = session.get(Question, q_id)
    if question:
        session.delete(question)
        session.commit()
    return RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/leaderboard/clear")
def clear_leaderboard(user = Depends(get_current_user), session: Session = Depends(get_session)):
    if not user:
        return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    
    # Delete all teams
    teams = session.exec(select(Team)).all()
    for team in teams:
        session.delete(team)
    session.commit()
    
    return RedirectResponse("/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)

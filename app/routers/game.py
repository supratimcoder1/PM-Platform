from datetime import datetime, timedelta
from typing import List, Dict
from fastapi import APIRouter, Request, Form, Depends, status, Body
from fastapi.responses import RedirectResponse, JSONResponse
from sqlmodel import Session, select, SQLModel
from app.database import get_session
from app.models import Question, Team, Feedback
from app.dependencies import templates

router = APIRouter(tags=["Game"])

class FeedbackInput(SQLModel):
    content: str

@router.get("/health")
def health_check():
    """Lightweight health check — no DB queries. Used by keep-alive pinger."""
    return {"status": "ok"}

@router.post("/api/feedback")
def submit_feedback(data: FeedbackInput, session: Session = Depends(get_session)):
    feedback_entry = Feedback(content=data.content)
    session.add(feedback_entry)
    session.commit()
    return JSONResponse({"success": True})

@router.get("/")
def landing_page(request: Request):
    request.session.pop("team_id", None)
    return templates.TemplateResponse("game/index.html", {"request": request})

@router.post("/start")
def start_game(
    request: Request, 
    team_name: str = Form(...), 
    roll_number: str = Form(...),
    rc_number: str = Form(...),
    session: Session = Depends(get_session)
):
    # Check if team exists
    existing_team = session.exec(select(Team).where(Team.name == team_name)).first()
    if existing_team:
        # If rejected, reset and allow re-application
        if existing_team.status == "rejected":
            existing_team.status = "pending"
            existing_team.roll_number = roll_number
            existing_team.rc_number = rc_number
            existing_team.start_time = datetime.now()
            session.add(existing_team)
            session.commit()
            session.refresh(existing_team)
            request.session["team_id"] = existing_team.id
            return RedirectResponse(f"/waiting/{existing_team.id}", status_code=status.HTTP_303_SEE_OTHER)
            
        # If approved, go to quiz
        if existing_team.status == "approved":
            request.session["team_id"] = existing_team.id
            return RedirectResponse("/quiz", status_code=status.HTTP_303_SEE_OTHER)
            
        # If pending, go to waiting
        request.session["team_id"] = existing_team.id
        return RedirectResponse(f"/waiting/{existing_team.id}", status_code=status.HTTP_303_SEE_OTHER)
    
    # Create new team
    new_team = Team(
        name=team_name, 
        roll_number=roll_number,
        rc_number=rc_number,
        status="pending",
        start_time=datetime.now()
    )
    session.add(new_team)
    session.commit()
    session.refresh(new_team)
    
    request.session["team_id"] = new_team.id
    return RedirectResponse(f"/waiting/{new_team.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/waiting/{team_id}")
def waiting_page(request: Request, team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if not team:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        
    if team.status == "approved":
        return RedirectResponse("/quiz", status_code=status.HTTP_303_SEE_OTHER)
        
    return templates.TemplateResponse("game/waiting.html", {"request": request, "team": team})

@router.get("/api/status/{team_id}")
def check_status(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if not team:
        return JSONResponse({"status": "unknown"})
    return JSONResponse({"status": team.status})

@router.get("/quiz")
def quiz_page(request: Request, session: Session = Depends(get_session)):
    team_id = request.session.get("team_id")
    if not team_id:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    
    team = session.get(Team, team_id)
    if not team or team.end_time:
        return RedirectResponse("/result", status_code=status.HTTP_303_SEE_OTHER)
    
    # Calculate initial time remaining
    now = datetime.now()
    duration = 20 * 60 # 20 minutes in seconds
    elapsed = (now - team.start_time).total_seconds()
    remaining = max(0, duration - elapsed)
    
    return templates.TemplateResponse("game/quiz.html", {
        "request": request,
        "team": team,
        "remaining_seconds": int(remaining)
    })

@router.get("/api/questions")
def get_questions(session: Session = Depends(get_session)):
    questions = session.exec(select(Question)).all()
    # Filter out answers obviously
    return [
        {
            "id": q.id,
            "content_text": q.content_text,
            "content_image": q.content_image,
            "difficulty": q.difficulty,
            "points": q.points,
            "options": q.options
        }
        for q in questions
    ]

@router.post("/api/submit")
def submit_quiz(
    request: Request,
    answers: Dict[str, str] = Body(...), # {question_id: answer}
    session: Session = Depends(get_session)
):
    team_id = request.session.get("team_id")
    if not team_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
    team = session.get(Team, team_id)
    if not team or team.end_time:
        return JSONResponse({"message": "Already submitted"}, status_code=200)

    # Calculate Score
    score = 0
    questions = session.exec(select(Question)).all()
    q_map = {str(q.id): q for q in questions}
    
    for q_id, user_answer in answers.items():
        if q_id in q_map:
            q = q_map[q_id]
            # Simple exact match, case insensitive
            if user_answer and user_answer.strip().lower() == q.answer.strip().lower():
                score += q.points
                
    team.score = score
    team.end_time = datetime.now()
    team.time_taken_seconds = (team.end_time - team.start_time).total_seconds()
    
    session.add(team)
    session.commit()
    
    return JSONResponse({"redirect": "/result"})

@router.get("/result")
def result_page(request: Request, session: Session = Depends(get_session)):
    team_id = request.session.get("team_id")
    team = session.get(Team, team_id) if team_id else None
    
    time_formatted = "0s"
    if team and team.time_taken_seconds is not None:
        m = int(team.time_taken_seconds // 60)
        s = int(team.time_taken_seconds % 60)
        ms = int((team.time_taken_seconds * 1000) % 1000)
        time_formatted = f"{m}m {s}s {ms}ms"
    
    return templates.TemplateResponse("game/result.html", {
        "request": request, 
        "team": team,
        "time_formatted": time_formatted
    })

@router.get("/leaderboard")
def leaderboard_page(request: Request):
    return templates.TemplateResponse("game/leaderboard.html", {"request": request})

@router.get("/api/leaderboard")
def leaderboard_data(session: Session = Depends(get_session)):
    teams = session.exec(
        select(Team)
        .where(Team.end_time.is_not(None))
        .order_by(Team.score.desc(), Team.time_taken_seconds.asc())
    ).all()
    return [
        {
            "name": t.name,
            "score": t.score,
            "time_taken": (
                f"{int(t.time_taken_seconds // 60)}m "
                f"{int(t.time_taken_seconds % 60)}s "
                f"{int((t.time_taken_seconds * 1000) % 1000)}ms"
            )
        }
        for t in teams
    ]

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from sqlalchemy import Column, Integer, String, Float
import requests


SUBMISSION_SERVICE_URL = "http://localhost:5004"
QUESTION_SERVICE_URL = "http://localhost:5001"

app = FastAPI(title="Evaluation Service")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True)
    exam_id = Column(String, index=True)
    score = Column(Integer)
    total = Column(Integer)
    percentage = Column(Float)


Base.metadata.create_all(bind=engine)


class EvaluationRequest(BaseModel):
    student_id: str
    exam_id: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def fetch_submissions(student_id: str):
    try:
        res = requests.get(
            f"{SUBMISSION_SERVICE_URL}/submissions/{student_id}", timeout=8
        )
        res.raise_for_status()
        return res.json()
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Submission service not running")


def fetch_questions(exam_id: str):
    try:
        res = requests.get(f"{QUESTION_SERVICE_URL}/questions/{exam_id}", timeout=8)
        res.raise_for_status()
        return res.json()
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Question service not running")


def calculate_score(submissions, questions):
    correct_map = {}
    for q in questions:
        qid = str(q.get("id"))
        correct_map[qid] = q.get("correct_answer")

    score = 0
    for sub in submissions:
        qid = str(sub.get("question_id"))
        ans = sub.get("answer")
        if qid in correct_map and correct_map[qid] == ans:
            score += 1

    total = len(correct_map)
    percentage = (score / total) * 100 if total > 0 else 0.0
    return score, total, percentage


@app.get("/")
def root():
    return {"message": "Evaluation Service Running"}


@app.post("/evaluate")
def evaluate(data: EvaluationRequest, db: Session = Depends(get_db)):
    submissions = fetch_submissions(data.student_id)
    filtered = [s for s in submissions if str(s.get("exam_id")) == str(data.exam_id)]
    questions = fetch_questions(data.exam_id)
    score, total, percentage = calculate_score(filtered, questions)

    existing = (
        db.query(Evaluation)
        .filter(
            Evaluation.student_id == data.student_id,
            Evaluation.exam_id == data.exam_id,
        )
        .first()
    )

    if existing:
        existing.score = score
        existing.total = total
        existing.percentage = percentage
        db.commit()
        db.refresh(existing)
        return {
            "message": "Evaluation updated",
            "student_id": existing.student_id,
            "exam_id": existing.exam_id,
            "score": existing.score,
            "total": existing.total,
            "percentage": existing.percentage,
        }

    record = Evaluation(
        student_id=data.student_id,
        exam_id=data.exam_id,
        score=score,
        total=total,
        percentage=percentage,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "message": "Evaluation stored",
        "student_id": record.student_id,
        "exam_id": record.exam_id,
        "score": record.score,
        "total": record.total,
        "percentage": record.percentage,
    }


@app.get("/evaluations/{student_id}")
def get_student_evaluations(student_id: str, db: Session = Depends(get_db)):
    rows = db.query(Evaluation).filter(Evaluation.student_id == student_id).all()
    return rows


@app.get("/health")
def health():
    return {"status": "Evaluation Service Running"}

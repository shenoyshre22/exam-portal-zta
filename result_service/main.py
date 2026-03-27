from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, DateTime
import requests
from database import SessionLocal, engine, Base

EVALUATION_SERVICE_URL = "http://localhost:5005"

app = FastAPI(title="Result Service")


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True)
    exam_id = Column(String, index=True)
    score = Column(Integer)
    total = Column(Integer)
    percentage = Column(Float)
    grade = Column(String)
    generated_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class ResultRequest(BaseModel):
    student_id: str
    exam_id: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def grade_from_percentage(percentage: float) -> str:
    if percentage >= 90:
        return "A"
    if percentage >= 80:
        return "B"
    if percentage >= 70:
        return "C"
    if percentage >= 60:
        return "D"
    return "F"


def evaluate(student_id: str, exam_id: str):
    try:
        response = requests.post(
            f"{EVALUATION_SERVICE_URL}/evaluate",
            json={"student_id": student_id, "exam_id": exam_id},
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Evaluation service unavailable")

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Unable to evaluate student")

    return response.json()


@app.get("/")
def root():
    return {"message": "Result Service Running"}


@app.post("/publish-result")
def publish_result(payload: ResultRequest, db: Session = Depends(get_db)):
    evaluation = evaluate(payload.student_id, payload.exam_id)

    score = int(evaluation.get("score", 0))
    total = int(evaluation.get("total", 0))
    percentage = float(evaluation.get("percentage", 0.0))
    grade = grade_from_percentage(percentage)

    existing = (
        db.query(Result)
        .filter(
            Result.student_id == payload.student_id,
            Result.exam_id == payload.exam_id,
        )
        .first()
    )

    if existing:
        existing.score = score
        existing.total = total
        existing.percentage = percentage
        existing.grade = grade
        existing.generated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    result = Result(
        student_id=payload.student_id,
        exam_id=payload.exam_id,
        score=score,
        total=total,
        percentage=percentage,
        grade=grade,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


@app.get("/results/{student_id}")
def get_results(student_id: str, db: Session = Depends(get_db)):
    return db.query(Result).filter(Result.student_id == student_id).all()


@app.get("/health")
def health():
    return {"status": "Result Service Running"}

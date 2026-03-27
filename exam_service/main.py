from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String
from database import SessionLocal, engine, Base

app = FastAPI(title="Exam Service")


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    total_marks = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=False)


Base.metadata.create_all(bind=engine)


class ExamCreate(BaseModel):
    title: str
    description: str = ""
    total_marks: int
    duration_minutes: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "Exam Service Running"}


@app.post("/exams")
def create_exam(payload: ExamCreate, db: Session = Depends(get_db)):
    exam = Exam(
        title=payload.title,
        description=payload.description,
        total_marks=payload.total_marks,
        duration_minutes=payload.duration_minutes,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@app.get("/exams")
def list_exams(db: Session = Depends(get_db)):
    return db.query(Exam).all()


@app.get("/exams/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@app.get("/health")
def health():
    return {"status": "Exam Service Running"}

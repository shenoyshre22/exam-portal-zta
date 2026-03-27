#making all the imports from requirements.txt
from fastapi import FastAPI,Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, engine,Base
from sqlalchemy import Column, Integer, String, Float
import requests
app= FastAPI(title="Evaluation Service")

#--- now for the database model----
class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String)
    exam_id = Column(String)
    total = Column(Integer)
    percentage = Column(Float)

    #create table automatically
    Base.metadata.create_all(bind=engine)
    #---the schema for the request body---
class EvaluationRequest(BaseModel):
    student_id: str
    exam_id: str
#---dependency to get the database session---
def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()
#---the helper functions----
def fetch_submissions(student_id):
    #---fetching the submissions from the submission service---
    try:
        res=requests.get(f"http://localhost:5004/submissions/{student_id}")
        return res.json()
    except:
        raise HTTPException(status_code=500,detail="Submission service not running")
    
def fetch_questions(exam_id):
    #---fetching the questions from the question service---
    try:
        res=requests.get(f"http://localhost:5001/questions/{exam_id}")
        return res.json()
    except:
        raise HTTPException(status_code=500,detail="Question service not running")
def calculate_score(submissions,questions):
    correct_map={}
    #build correct answer map
    for q in questions:
        correct_map[q['id']]=q['correct_answer']
    score=0
    for sub in submissions:
        qid=sub["question_id"]
        ans=sub["answer"]
        if qid in correct_map and correct_map[qid]==ans:
            score+=1
    total=len(correct_map)
    percentage=(score/total)*100 if total>0 else 0 # to calculate percentage for grades
    return score,total,percentage
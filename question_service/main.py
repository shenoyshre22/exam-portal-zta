from sqlalchemy.orm import Session
import shutil
from database import SessionLocal, engine
import models,schemas
from pdf_parser import get_from_pdf
from auth_client import verify_token
from fastapi import FastAPI

models.Base.metadata.create_all(bind=engine)
app=FastAPI()

#connection to DB

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

#check authorization

def get_curr_teacher(token:str=""):
    user=verify_token(token)
    if user["role"]!="teacher":
        raise HTTPException(status_code=403,detail='NOT AUTHORIZED')
    return user

#pdf upload

@app.post("/upload-pdf")
def uploading_pdf(exam_id:int,file:UploadFile=File(),db:Session=Depends(get_db),user=Depends(get_curr_teacher)):
    filepath=f"temp_{file.filename}"
    with open(file_path,"wb") as buffer:
        shutil.copyfileobj(file.file,buffer)
    questions=extract_questions_from_pdf(filepath)

    for qs in questions:
        db.add(models.Question(exam_id=exam_id,question_type="THEORY",question_text=qs))
        db.commit()
        return {"questions_added":len(questions)}


#mcq upload

@app.post("/add-mcq")
def add_mcqs(mcq:schemas.MCQCreation, db: Session=Depends(get_db), user=Depends(get_curr_teacher)):
    new=models.Question(exam_id=mcq.exam_id,question_type="MCQ",question_text=mcq.question_text,option_a=mcq.option_a,option_b=mcq.option_b,option_c=mcq.option_c,option_d=mcq.option_d,correct_answer=mcq.correct_answer)
    db.add(new)
    db.commit()
    db.refresh(new)
    return new

@app.get("/questions/{exam_id}")
def get_questions(exam_id:int,db:Session=Depends(get_db)):
    return db.query(models.Question).filter(
        models.Question.exam_id==exam_id
    ).all()

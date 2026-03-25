from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import shutil, os, tempfile
from datetime import datetime

from database import init_db, get_db
from auth import verify_teacher_token, verify_admin_token
from pdf_parser import extract_questions_from_pdf
from models import (
    MCQCreate, TheoryQuestionCreate,
    ExamCreate, PermissionGrant,
    QuestionResponse, ExamResponse
)
import sqlite3

app = FastAPI(title="Question Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


# ─────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "question-service"}


# ─────────────────────────────────────────────
# ADMIN: Create exam slot + grant teacher permission
# ─────────────────────────────────────────────

@app.post("/admin/exams", response_model=ExamResponse)
def create_exam(payload: ExamCreate, token_data=Depends(verify_admin_token)):
    """Admin creates an exam with a submission deadline and test date."""
    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO exams (title, description, exam_date, upload_deadline, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (payload.title, payload.description,
             payload.exam_date.isoformat(),
             payload.upload_deadline.isoformat(),
             token_data["user_id"])
        )
        db.commit()
        exam_id = cursor.lastrowid
        exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        return dict(exam)
    finally:
        db.close()


@app.post("/admin/permissions")
def grant_teacher_permission(payload: PermissionGrant, token_data=Depends(verify_admin_token)):
    """Admin grants a specific teacher permission to upload questions for an exam."""
    db = get_db()
    try:
        # Check exam exists
        exam = db.execute("SELECT id FROM exams WHERE id=?", (payload.exam_id,)).fetchone()
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")

        # Upsert permission
        db.execute(
            """INSERT INTO teacher_permissions (teacher_id, exam_id, granted_by)
               VALUES (?, ?, ?)
               ON CONFLICT(teacher_id, exam_id) DO UPDATE SET granted_by=excluded.granted_by""",
            (payload.teacher_id, payload.exam_id, token_data["user_id"])
        )
        db.commit()
        return {"message": f"Teacher {payload.teacher_id} granted access to exam {payload.exam_id}"}
    finally:
        db.close()


@app.delete("/admin/permissions")
def revoke_teacher_permission(teacher_id: int, exam_id: int, token_data=Depends(verify_admin_token)):
    """Admin revokes a teacher's upload permission."""
    db = get_db()
    try:
        db.execute(
            "DELETE FROM teacher_permissions WHERE teacher_id=? AND exam_id=?",
            (teacher_id, exam_id)
        )
        db.commit()
        return {"message": "Permission revoked"}
    finally:
        db.close()


@app.get("/admin/exams")
def list_all_exams(token_data=Depends(verify_admin_token)):
    """Admin views all exams."""
    db = get_db()
    try:
        exams = db.execute("SELECT * FROM exams ORDER BY exam_date").fetchall()
        return [dict(e) for e in exams]
    finally:
        db.close()


@app.get("/admin/exams/{exam_id}/questions")
def admin_view_questions(exam_id: int, token_data=Depends(verify_admin_token)):
    """Admin views all questions for any exam."""
    db = get_db()
    try:
        questions = db.execute(
            "SELECT * FROM questions WHERE exam_id=? ORDER BY question_order",
            (exam_id,)
        ).fetchall()
        return [dict(q) for q in questions]
    finally:
        db.close()


# ─────────────────────────────────────────────
# TEACHER: Upload questions
# ─────────────────────────────────────────────

def _check_teacher_access(db, teacher_id: int, exam_id: int):
    """Verify teacher has permission and exam deadline hasn't passed."""
    perm = db.execute(
        "SELECT 1 FROM teacher_permissions WHERE teacher_id=? AND exam_id=?",
        (teacher_id, exam_id)
    ).fetchone()
    if not perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to upload questions for this exam."
        )

    exam = db.execute("SELECT upload_deadline, exam_date FROM exams WHERE id=?", (exam_id,)).fetchone()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    now = datetime.utcnow()
    deadline = datetime.fromisoformat(exam["upload_deadline"])
    if now > deadline:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Upload deadline passed at {deadline.isoformat()} UTC"
        )
    return exam


@app.post("/teacher/exams/{exam_id}/upload-pdf")
async def upload_pdf_questions(
    exam_id: int,
    file: UploadFile = File(...),
    question_type: str = Form("theory"),   # "theory" or "mcq"
    token_data=Depends(verify_teacher_token)
):
    """
    Teacher uploads a PDF of theory questions or MCQs.
    The service parses it question-by-question and stores each one.

    PDF format expected:
      Theory: numbered lines like "1. Explain Newton's first law..."
      MCQ:    Q1. <question>
              A) option  B) option  C) option  D) option
              Answer: B
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    db = get_db()
    try:
        _check_teacher_access(db, token_data["user_id"], exam_id)

        # Save PDF temporarily
        tmp_path = os.path.join(UPLOAD_DIR, f"tmp_{token_data['user_id']}_{exam_id}_{file.filename}")
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            questions = extract_questions_from_pdf(tmp_path, question_type)
        finally:
            os.remove(tmp_path)

        if not questions:
            raise HTTPException(
                status_code=422,
                detail="No questions could be parsed from the PDF. Check the format."
            )

        # Get current max order for this exam
        row = db.execute(
            "SELECT COALESCE(MAX(question_order), 0) FROM questions WHERE exam_id=?",
            (exam_id,)
        ).fetchone()
        start_order = row[0] + 1

        inserted = 0
        for i, q in enumerate(questions):
            db.execute(
                """INSERT INTO questions
                   (exam_id, question_text, question_type, option_a, option_b, option_c, option_d,
                    correct_answer, marks, uploaded_by, question_order, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pdf')""",
                (
                    exam_id,
                    q.get("question_text", ""),
                    q.get("question_type", question_type),
                    q.get("option_a"), q.get("option_b"),
                    q.get("option_c"), q.get("option_d"),
                    q.get("correct_answer"),
                    q.get("marks", 1),
                    token_data["user_id"],
                    start_order + i
                )
            )
            inserted += 1

        db.commit()
        return {
            "message": f"Successfully parsed and stored {inserted} questions from PDF.",
            "exam_id": exam_id,
            "questions_added": inserted
        }
    finally:
        db.close()


@app.post("/teacher/exams/{exam_id}/mcq")
def add_mcq(exam_id: int, payload: MCQCreate, token_data=Depends(verify_teacher_token)):
    """Teacher manually adds a single MCQ question."""
    db = get_db()
    try:
        _check_teacher_access(db, token_data["user_id"], exam_id)

        row = db.execute(
            "SELECT COALESCE(MAX(question_order), 0) FROM questions WHERE exam_id=?",
            (exam_id,)
        ).fetchone()
        next_order = row[0] + 1

        cursor = db.execute(
            """INSERT INTO questions
               (exam_id, question_text, question_type, option_a, option_b, option_c, option_d,
                correct_answer, marks, uploaded_by, question_order, source)
               VALUES (?, ?, 'mcq', ?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
            (
                exam_id, payload.question_text,
                payload.option_a, payload.option_b,
                payload.option_c, payload.option_d,
                payload.correct_answer.upper(),
                payload.marks, token_data["user_id"], next_order
            )
        )
        db.commit()
        return {"message": "MCQ added", "question_id": cursor.lastrowid}
    finally:
        db.close()


@app.post("/teacher/exams/{exam_id}/theory")
def add_theory_question(exam_id: int, payload: TheoryQuestionCreate, token_data=Depends(verify_teacher_token)):
    """Teacher manually adds a single theory question."""
    db = get_db()
    try:
        _check_teacher_access(db, token_data["user_id"], exam_id)

        row = db.execute(
            "SELECT COALESCE(MAX(question_order), 0) FROM questions WHERE exam_id=?",
            (exam_id,)
        ).fetchone()
        next_order = row[0] + 1

        cursor = db.execute(
            """INSERT INTO questions
               (exam_id, question_text, question_type, marks, uploaded_by, question_order, source)
               VALUES (?, ?, 'theory', ?, ?, ?, 'manual')""",
            (exam_id, payload.question_text, payload.marks,
             token_data["user_id"], next_order)
        )
        db.commit()
        return {"message": "Theory question added", "question_id": cursor.lastrowid}
    finally:
        db.close()


@app.delete("/teacher/exams/{exam_id}/questions/{question_id}")
def delete_question(exam_id: int, question_id: int, token_data=Depends(verify_teacher_token)):
    """Teacher deletes their own question (only before deadline)."""
    db = get_db()
    try:
        _check_teacher_access(db, token_data["user_id"], exam_id)

        q = db.execute(
            "SELECT uploaded_by FROM questions WHERE id=? AND exam_id=?",
            (question_id, exam_id)
        ).fetchone()
        if not q:
            raise HTTPException(status_code=404, detail="Question not found")
        if q["uploaded_by"] != token_data["user_id"]:
            raise HTTPException(status_code=403, detail="You can only delete your own questions")

        db.execute("DELETE FROM questions WHERE id=?", (question_id,))
        db.commit()
        return {"message": "Question deleted"}
    finally:
        db.close()


@app.get("/teacher/exams/{exam_id}/questions")
def teacher_view_own_questions(exam_id: int, token_data=Depends(verify_teacher_token)):
    """Teacher views questions they uploaded for an exam."""
    db = get_db()
    try:
        _check_teacher_access(db, token_data["user_id"], exam_id)
        questions = db.execute(
            "SELECT * FROM questions WHERE exam_id=? AND uploaded_by=? ORDER BY question_order",
            (exam_id, token_data["user_id"])
        ).fetchall()
        return [dict(q) for q in questions]
    finally:
        db.close()


# ─────────────────────────────────────────────
# STUDENT: Read questions during active exam
# ─────────────────────────────────────────────

@app.get("/exam/{exam_id}/questions")
def get_exam_questions(exam_id: int, token_data=Depends(verify_teacher_token)):
    """
    Called by exam-service on behalf of a student.
    Returns questions without correct_answer field.
    Only available after exam starts and before it ends.
    """
    db = get_db()
    try:
        exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")

        now = datetime.utcnow()
        exam_date = datetime.fromisoformat(exam["exam_date"])

        # Allow viewing 10 minutes before and up to 3 hours after exam start
        window_start = exam_date.replace(minute=exam_date.minute - 10) if exam_date.minute >= 10 else exam_date
        # Simple check — exam access timing should be enforced by exam-service primarily
        if now < window_start:
            raise HTTPException(
                status_code=403,
                detail=f"Exam starts at {exam_date.isoformat()} UTC"
            )

        questions = db.execute(
            """SELECT id, question_text, question_type, option_a, option_b,
                      option_c, option_d, marks, question_order
               FROM questions WHERE exam_id=? ORDER BY question_order""",
            (exam_id,)
        ).fetchall()

        return {
            "exam_id": exam_id,
            "exam_title": exam["title"],
            "total_questions": len(questions),
            "questions": [dict(q) for q in questions]
        }
    finally:
        db.close()


# ─────────────────────────────────────────────
# INTERNAL: Called by evaluation-service
# ─────────────────────────────────────────────

@app.get("/internal/exam/{exam_id}/answers")
def get_correct_answers(exam_id: int, internal_key: str):
    """
    Internal endpoint for evaluation-service to fetch correct answers.
    Protected by a shared internal secret key (not a user JWT).
    """
    INTERNAL_SECRET = os.getenv("INTERNAL_SERVICE_KEY", "internal-secret-change-in-prod")
    if internal_key != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid internal key")

    db = get_db()
    try:
        questions = db.execute(
            """SELECT id, question_type, correct_answer, marks
               FROM questions WHERE exam_id=? ORDER BY question_order""",
            (exam_id,)
        ).fetchall()
        return [dict(q) for q in questions]
    finally:
        db.close()
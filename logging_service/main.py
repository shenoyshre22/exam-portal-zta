#Stores events from different service
#filtering by the user as well 
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from pydantic import BaseModel

app = FastAPI(title="Logging Service")

# ---------------- DATABASE MODEL ----------------
# This model defines the structure of the logs table in the database. Each log entry will have an id, user_id, service name, event type, description, and timestamp.
class Log(Base):
    __tablename__ = "logs"
#details of the user to be taken 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    service = Column(String)
    event_type = Column(String)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)


# ---------------- Pydantic Schema ----------------
# This schema is used to validate incoming log data when a log event is created.
class LogCreate(BaseModel):
    user_id: str
    service: str
    event_type: str
    description: str


# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- ROUTES ----------------
# Basic route to check if service is running
# This will be used by other services to check if logging service is up before sending logs


@app.get("/")
def root():
    return {"message": "Logging Service Running"}
# 🔹 1. Add log
@app.post("/log-event")
def log_event(log: LogCreate, db: Session = Depends(get_db)):
    try:
        new_log = Log(
            user_id=log.user_id,
            service=log.service,
            event_type=log.event_type,
            description=log.description
        )

        db.add(new_log)
        db.commit()
        db.refresh(new_log)

        return {"message": "Log stored successfully", "id": new_log.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🔹 2. Get all logs
@app.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(Log).all()
    return logs


# 🔹 3. Get logs by user
@app.get("/logs/{user_id}")
def get_user_logs(user_id: str, db: Session = Depends(get_db)):
    logs = db.query(Log).filter(Log.user_id == user_id).all()
    return logs


# 🔹 4. Health check
@app.get("/health")
def health():
    return {"status": "Logging Service Running"}
from fastapi import FastAPI, HTTPException, Header, Depends
import requests


SERVICES = {
    "login": "http://localhost:5000",
    "question": "http://localhost:5001",
    "exam": "http://localhost:5002",
    "logging": "http://localhost:5003",
    "submission": "http://localhost:5004",
    "evaluation": "http://localhost:5005",
    "result": "http://localhost:5006",
}

app = FastAPI(title="API Gateway")


def proxy(method: str, url: str, payload=None, token: str = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(method, url, json=payload, headers=headers, timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Downstream service unavailable")

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)
    return data


# NEW — validates token before any protected route
def validate_token(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        response = requests.get(
            f"{SERVICES['login']}/verify-token",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Login service unavailable")
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return response.json()


@app.get("/")
def root():
    return {"message": "API Gateway Running", "services": SERVICES}


@app.get("/health")
def health():
    return {"status": "API Gateway Running"}


# --- Auth routes (open — no token needed) ---

@app.post("/auth/signup")
def signup(payload: dict):
    return proxy("POST", f"{SERVICES['login']}/signup", payload)


@app.post("/auth/login")
def login(payload: dict):
    return proxy("POST", f"{SERVICES['login']}/login", payload)


# --- Question routes (protected) ---

@app.get("/questions/{exam_id}")
def questions(exam_id: int, authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("GET", f"{SERVICES['question']}/questions/{exam_id}", token=token)


@app.post("/questions/add-mcq")
def add_mcq(payload: dict, authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("POST", f"{SERVICES['question']}/add-mcq", payload, token=token)


@app.post("/questions/upload-pdf")
def upload_pdf(authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("POST", f"{SERVICES['question']}/upload-pdf", token=token)


# --- Exam routes (NEW + protected) ---

@app.post("/exams")
def create_exam(payload: dict, authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("POST", f"{SERVICES['exam']}/exams", payload, token=token)


@app.get("/exams")
def list_exams(authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("GET", f"{SERVICES['exam']}/exams", token=token)


@app.get("/exams/{exam_id}")
def get_exam(exam_id: int, authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("GET", f"{SERVICES['exam']}/exams/{exam_id}", token=token)


# --- Submission routes (protected at gateway, no auth inside service) ---

@app.post("/submit-answer")
def submit_answer(payload: dict, user=Depends(validate_token)):
    return proxy("POST", f"{SERVICES['submission']}/submit-answer", payload)


# --- Evaluation routes (protected) ---

@app.post("/evaluate")
def evaluate(payload: dict, authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("POST", f"{SERVICES['evaluation']}/evaluate", payload, token=token)


# --- Result routes (protected) ---

@app.post("/publish-result")
def publish_result(payload: dict, authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("POST", f"{SERVICES['result']}/publish-result", payload, token=token)


@app.get("/results/{student_id}")
def results(student_id: str, authorization: str = Header(default=""), user=Depends(validate_token)):
    token = authorization.split(" ", 1)[1].strip()
    return proxy("GET", f"{SERVICES['result']}/results/{student_id}", token=token)


from fastapi import FastAPI, HTTPException
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


def proxy(method: str, url: str, payload=None):
    try:
        response = requests.request(method, url, json=payload, timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Downstream service unavailable")

    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)
    return data
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


@app.post("/auth/signup")
def signup(payload: dict):
    return proxy("POST", f"{SERVICES['login']}/signup", payload)


@app.post("/auth/login")
def login(payload: dict):
    return proxy("POST", f"{SERVICES['login']}/login", payload)


@app.get("/questions/{exam_id}")
def questions(exam_id: int):
    return proxy("GET", f"{SERVICES['question']}/questions/{exam_id}")


@app.post("/submit-answer")
def submit_answer(payload: dict):
    return proxy("POST", f"{SERVICES['submission']}/submit-answer", payload)


@app.post("/evaluate")
def evaluate(payload: dict):
    return proxy("POST", f"{SERVICES['evaluation']}/evaluate", payload)


@app.post("/publish-result")
def publish_result(payload: dict):
    return proxy("POST", f"{SERVICES['result']}/publish-result", payload)


@app.get("/results/{student_id}")
def results(student_id: str):
    return proxy("GET", f"{SERVICES['result']}/results/{student_id}")

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/dashboard")
def get_dashboard():
    return {"status": "ok"}

client = TestClient(app)
response = client.options("/api/dashboard", headers={
    "Origin": "http://localhost:5175",
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "Authorization"
})
print(f"Status: {response.status_code}")
print(f"Content: {response.text}")
print(f"Headers: {dict(response.headers)}")

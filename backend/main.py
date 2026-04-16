from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "backend running"}

@app.post("/ai-proposal")
def ai():
    return {
        "voorstel": "Voorziening toegekend",
        "onderbouwing": "Voldoet aan beleid",
        "risico_score": 0.2
    }
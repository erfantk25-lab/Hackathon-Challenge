from fastapi import FastAPI


app = FastAPI(title="Hackathon Backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

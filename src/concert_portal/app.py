from fastapi import FastAPI

app = FastAPI(title="Concert Registration and Ticketing Portal", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Simple health check endpoint used by tests and monitoring."""
    return {"status": "ok"}

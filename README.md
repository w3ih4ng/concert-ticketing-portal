# Concert Registration and Ticketing Portal

A FastAPI application for concert registration and ticketing, built with a
Scrum workflow and a GitHub Actions CI/CD pipeline.

## Setup
```
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Run locally
```
python3 -m uvicorn concert_portal.app:app --reload
```
Then open http://localhost:8000/health — you should see {"status": "ok"}.

## Checks before pushing
```
pytest
black .
ruff check .
```

## Team
- Member 1 — <Lee Wei Hang> (<GitHub handle>)
- Member 2 — <Alyssa Loh Yi Hui> (<GitHub handle>)
- Member 3 — <Ong Yi Jia> (<GitHub handle>)
"""FastAPI token server for the mock interview frontend.

Provides a token endpoint so the browser can join a LiveKit room,
and serves the React frontend as static files.
"""

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from livekit.api import AccessToken, VideoGrants
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Mock Interview API")

# Allow the Vite dev server (localhost:5173) during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root of the data directory where per-interview folders live.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TokenRequest(BaseModel):
    participant_name: str
    interview_code: str
    room_name: str = ""


class TokenResponse(BaseModel):
    token: str
    livekit_url: str
    room_name: str
    interview_code: str


@app.post("/api/token", response_model=TokenResponse)
async def create_token(req: TokenRequest) -> TokenResponse:
    """Generate a LiveKit access token for the participant."""
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL", "")

    if not api_key or not api_secret or not livekit_url:
        raise HTTPException(
            status_code=500,
            detail="LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL must be set",
        )

    # Validate the interview code exists on disk.
    code = req.interview_code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Interview code is required")

    interview_dir = _DATA_DIR / code
    if not interview_dir.is_dir():
        raise HTTPException(status_code=404, detail="Invalid interview code")

    # Each click gets a unique room so the LiveKit server dispatches a fresh
    # agent job.  Format: "interview--{code}--{uuid}" — double-dash separators
    # let the agent extract the code reliably.
    room_name = req.room_name or f"interview--{code}--{uuid.uuid4().hex[:8]}"

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(f"user-{uuid.uuid4().hex[:6]}")
        .with_name(req.participant_name)
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )

    return TokenResponse(
        token=token,
        livekit_url=livekit_url,
        room_name=room_name,
        interview_code=code,
    )


# Serve the React build if it exists (production mode).
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

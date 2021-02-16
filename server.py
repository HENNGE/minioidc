from __future__ import annotations

import dataclasses
import logging
import secrets
import time
from typing import Dict, Optional, Tuple

from fastapi import Depends, FastAPI, Query, Response
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logging.basicConfig(level=logging.INFO)
app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def homepage():
    return f"""
    <html>
        <head>
            <title>Example client that implements OpenID Connect confidential client using code flow</title>
            <link rel="shortcut icon" href="{ICON}"/>
            <script>{JS}</script>
        </head>
        <body>
            <div>FIXME</div>
            <button onclick="logout">Logout</button>
            <button onclick="status">Check status</button>
            <button onclick="test">Test</button>
        </body>
    </html>
    """.strip()


@dataclasses.dataclass
class Session:
    created: float
    fastapi_token: str
    refresh_token: Optional[str]
    access_token: Optional[Dict]
    id_token: Optional[Dict]
    error: Optional[str]
    error_description: Optional[str]


auth = HTTPBearer()


def valid_session(
    authorization: HTTPAuthorizationCredentials = Depends(auth),
) -> Session:
    try:
        session = sessions[authorization.credentials[:8]]
        if not secrets.compare_digest(authorization.credentials, session.fastapi_token):
            raise KeyError()
        return session
    except KeyError:
        raise HTTPException(403, "Not authenticated")


@app.post("/status")
async def status(session: Session = Depends(valid_session)):
    tmp = dataclasses.asdict(session)
    del tmp["fastapi_token"]
    del tmp["refresh_token"]
    return tmp


@app.post("/logout")
def logout(session: Session = Depends(valid_session)):
    try:
        del sessions[session.fastapi_token[:8]]
    except KeyError:
        logging.exception("WTF")
    return RedirectResponse("/")


@app.get("/cb", response_class=HTMLResponse)
async def callback(
    response: Response,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    fastapi_token = secrets.token_hex(20)
    refresh_token, access_token, id_token = await get_tokens(code)
    sessions[fastapi_token[:8]] = Session(
        time.time(),
        fastapi_token,
        refresh_token,
        access_token,
        id_token,
        error,
        error_description,
    )
    cleanup_sessions()
    return RedirectResponse(f"/#{fastapi_token}")


@dataclasses.dataclass
class State:
    created: float


sessions: Dict[str, Session] = {}
states: Dict[str, State] = {}
COOKIE_DURATION = 3600
COOKIE_LIMIT = 1000


def cleanup_sessions():
    def clean(expiry):
        for k, s in sessions.items():
            if s.created < expiry:
                del sessions[k]

    duration = COOKIE_DURATION
    now = time.time()
    clean(now - duration)

    while len(sessions) > COOKIE_LIMIT and duration:
        duration //= 2
        clean(now - duration)


async def get_tokens(code) -> Tuple:
    return "rrr", {"a": 42}, {"id": 42}


JS = """
"use strict";
const new_token = window.location.hash.split("#")[1];
if (new_token) {
  window.location.hash = "";
  localStorage.setItem("fastapi_token", new_token);
}
const fastapi_token = localStorage.getItem("fastapi_token");
console.log("FastAPI token is", fastapi_token);

const logout = async () => {
  await fetch("/logout", {method: "POST", headers: {Authorization: `Bearer ${ fastapi_token }`}});
};

const status = async () => {
  const rv = await fetch("/status", {method: "POST", headers: {Authorization: `Bearer ${ fastapi_token }`}});
  console.log(rv);
};

const test = () => {
  console.log("test!");
};

status();
"""


ICON = """data:image/png;base64,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"""

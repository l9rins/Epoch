"""
src/api/auth_endpoints.py
JWT auth routes: register, login, me, refresh, logout.
Wired to src/api/auth.py — no logic here, just HTTP layer.

Tiers:
  ROSTRA  — Roster mode only (gamer tier)
  SIGNAL  — Bettor mode + Roster
  API     — Full access (Analyst + Bettor + Roster)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import Optional

from src.api.auth import (
    create_user,
    authenticate_user,
    create_access_token,
    get_user_from_token,
    get_subscription_status,
    check_and_increment_api_calls,
    require_tier,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Request / Response models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    tier: str = "ROSTRA"


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    tier: str
    subscription: dict


# ── Dependency: extract + validate JWT from header ────────────────────────────

def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Dependency that extracts user from Authorization: Bearer <token> header.
    Raises 401 if missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or malformed")

    token = authorization.removeprefix("Bearer ").strip()
    user = get_user_from_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user


def require_signal_tier(user=Depends(get_current_user)):
    """Dependency: requires SIGNAL tier or higher."""
    if not require_tier("SIGNAL", user.tier):
        raise HTTPException(
            status_code=403,
            detail=f"SIGNAL tier required. Your tier: {user.tier}. Upgrade at /api/stripe/checkout"
        )
    return user


def require_api_tier(user=Depends(get_current_user)):
    """Dependency: requires API tier (full access)."""
    if not require_tier("API", user.tier):
        raise HTTPException(
            status_code=403,
            detail=f"API tier required. Your tier: {user.tier}. Upgrade at /api/stripe/checkout"
        )
    return user


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    """Create a new account. 14-day trial auto-applied."""
    if req.tier not in ("ROSTRA", "SIGNAL", "API"):
        raise HTTPException(status_code=400, detail="Invalid tier. Choose ROSTRA, SIGNAL, or API.")

    user = create_user(req.email, req.password, req.tier)
    if not user:
        raise HTTPException(status_code=409, detail="Email already registered.")

    token = create_access_token(user)
    return AuthResponse(
        token=token,
        user_id=user.user_id,
        email=user.email,
        tier=user.tier,
        subscription=get_subscription_status(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Authenticate and receive a JWT token."""
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(user)
    return AuthResponse(
        token=token,
        user_id=user.user_id,
        email=user.email,
        tier=user.tier,
        subscription=get_subscription_status(user),
    )


@router.get("/me")
def me(user=Depends(get_current_user)):
    """Get current user profile + subscription status."""
    return {
        "user_id":     user.user_id,
        "email":       user.email,
        "tier":        user.tier,
        "subscription": get_subscription_status(user),
        "last_active": user.last_active,
    }


@router.post("/refresh")
def refresh(user=Depends(get_current_user)):
    """Refresh a valid token. Returns a new token with extended expiry."""
    new_token = create_access_token(user)
    return {"token": new_token}


@router.get("/check/{required_tier}")
def check_access(required_tier: str, user=Depends(get_current_user)):
    """Check if current user has access to a specific tier."""
    has_access = require_tier(required_tier, user.tier)
    return {
        "has_access":    has_access,
        "user_tier":     user.tier,
        "required_tier": required_tier,
    }

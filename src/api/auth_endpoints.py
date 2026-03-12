from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    email: str
    password: str
    tier: str = "ROSTRA"

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register(req: RegisterRequest):
    from src.api.auth import create_user, create_access_token, get_subscription_status
    if req.tier not in ("ROSTRA", "SIGNAL", "API"):
        raise HTTPException(status_code=400, detail="Invalid tier")
    user = create_user(req.email, req.password, req.tier)
    if not user:
        raise HTTPException(status_code=409, detail="Email already registered")
    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "tier": user.tier,
        "subscription": get_subscription_status(user),
    }

@router.post("/login")
async def login(req: LoginRequest):
    from src.api.auth import authenticate_user, create_access_token, get_subscription_status
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.user_id,
        "tier": user.tier,
        "subscription": get_subscription_status(user),
    }

@router.get("/me")
async def get_me(authorization: Optional[str] = None):
    from fastapi import Header
    from src.api.auth import get_user_from_token, get_subscription_status
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.replace("Bearer ", "")
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {
        "user_id": user.user_id,
        "email": user.email,
        "tier": user.tier,
        "subscription": get_subscription_status(user),
    }

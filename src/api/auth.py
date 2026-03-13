import os
import json
import uuid
import bcrypt
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    print("Warning: PyJWT not installed. Auth endpoints will be degraded.")

USERS_PATH = Path("data/users.json")

# Read from environment — never hardcode in production
JWT_SECRET = os.environ.get(
    "JWT_SECRET_KEY",
    "epoch-engine-dev-secret-do-not-use-in-prod"
)
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24 * 7  # 7 days

TIER_LEVELS = {"ROSTRA": 1, "SIGNAL": 2, "API": 3}
TIER_API_LIMITS = {"ROSTRA": 100, "SIGNAL": 1000, "API": 10000}

@dataclass
class User:
    user_id: str
    email: str
    password_hash: str
    tier: str
    created_at: str
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    subscription_status: str
    trial_ends_at: Optional[str]
    api_calls_today: int
    api_calls_limit: int
    last_active: str

def _load_users() -> dict:
    if not USERS_PATH.exists():
        _save_users({})
        return {}
    try:
        with open(USERS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _save_users({})
        return {}
    except Exception:
        return {}

def _save_users(users: dict) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_PATH, "w") as f:
        json.dump(users, f, indent=2)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed.encode("utf-8")
        )
    except Exception:
        return False

def create_user(
    email: str,
    password: str,
    tier: str = "ROSTRA",
) -> Optional[User]:
    """Create a new user. Returns None if email already exists."""
    users = _load_users()
    if any(u["email"] == email for u in users.values()):
        return None

    user = User(
        user_id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(password),
        tier=tier,
        created_at=datetime.utcnow().isoformat(),
        stripe_customer_id=None,
        stripe_subscription_id=None,
        subscription_status="trial",
        trial_ends_at=(datetime.utcnow() + timedelta(days=14)).isoformat(),
        api_calls_today=0,
        api_calls_limit=TIER_API_LIMITS.get(tier, 100),
        last_active=datetime.utcnow().isoformat(),
    )
    users[user.user_id] = asdict(user)
    _save_users(users)
    return user

def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate and return user. Returns None if invalid credentials."""
    users = _load_users()
    for user_data in users.values():
        if user_data["email"] == email:
            if verify_password(password, user_data["password_hash"]):
                user_data["last_active"] = datetime.utcnow().isoformat()
                users[user_data["user_id"]] = user_data
                _save_users(users)
                return User(**user_data)
    return None

def create_access_token(user: User) -> str:
    """Create JWT access token for authenticated user."""
    if not JWT_AVAILABLE:
        return f"dev-token-{user.user_id}"
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "tier": user.tier,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token. Returns payload or None."""
    if not JWT_AVAILABLE:
        if token.startswith("dev-token-"):
            user_id = token.replace("dev-token-", "")
            users = _load_users()
            user_data = users.get(user_id)
            if user_data:
                return {"sub": user_id, "tier": user_data["tier"]}
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None

def get_user_from_token(token: str) -> Optional[User]:
    """Full token → user lookup with freshness check."""
    payload = decode_access_token(token)
    if not payload:
        return None
    users = _load_users()
    user_data = users.get(payload.get("sub"))
    if not user_data:
        return None
    return User(**user_data)

def require_tier(required_tier: str, user_tier: str) -> bool:
    """Check if user_tier meets or exceeds required_tier."""
    return TIER_LEVELS.get(user_tier, 0) >= TIER_LEVELS.get(required_tier, 99)

def check_and_increment_api_calls(user_id: str) -> bool:
    """
    Check if user is within API call limit.
    Increments counter and returns True if allowed.
    Returns False if over limit.
    """
    users = _load_users()
    user_data = users.get(user_id)
    if not user_data:
        return False
    today = datetime.utcnow().date().isoformat()
    if user_data.get("last_api_call_date") != today:
        user_data["api_calls_today"] = 0
        user_data["last_api_call_date"] = today
    if user_data["api_calls_today"] >= user_data.get("api_calls_limit", 100):
        return False
    user_data["api_calls_today"] += 1
    users[user_id] = user_data
    _save_users(users)
    return True

def get_subscription_status(user: User) -> dict:
    """Get full subscription status for a user."""
    is_trial = user.subscription_status == "trial"
    trial_active = False
    trial_days_remaining = 0
    if is_trial and user.trial_ends_at:
        try:
            trial_end = datetime.fromisoformat(user.trial_ends_at)
            trial_active = trial_end > datetime.utcnow()
            if trial_active:
                trial_days_remaining = (trial_end - datetime.utcnow()).days
        except Exception:
            pass
    return {
        "tier": user.tier,
        "subscription_status": user.subscription_status,
        "is_trial": is_trial,
        "trial_active": trial_active,
        "trial_days_remaining": trial_days_remaining,
        "api_calls_today": user.api_calls_today,
        "api_calls_limit": user.api_calls_limit,
        "stripe_linked": user.stripe_customer_id is not None,
    }

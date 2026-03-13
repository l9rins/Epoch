import os
from src.api.auth import (
    create_user,
    authenticate_user,
    create_access_token,
    decode_access_token,
    require_tier,
    check_and_increment_api_calls,
    get_subscription_status,
    _load_users,
    _save_users,
)

def _delete_user_by_email(email: str):
    """Helper to ensure tests are idempotent."""
    users = _load_users()
    to_delete = [uid for uid, u in users.items() if u["email"] == email]
    for uid in to_delete:
        del users[uid]
    _save_users(users)

def test_user_creation_and_auth():
    email = "test@epoch-engine.com"
    pwd = "securepassword123"
    _delete_user_by_email(email)
    
    # Create
    user = create_user(email, pwd, "SIGNAL")
    assert user is not None
    assert user.email == email
    assert user.tier == "SIGNAL"
    
    # Duplicate fails
    dup = create_user(email, "other", "ROSTRA")
    assert dup is None
    
    # Authenticate
    auth_user = authenticate_user(email, pwd)
    assert auth_user is not None
    assert auth_user.user_id == user.user_id
    
    # Bad auth
    bad_auth = authenticate_user(email, "wrong")
    assert bad_auth is None

def test_tier_requirements():
    assert require_tier("ROSTRA", "SIGNAL") == True
    assert require_tier("SIGNAL", "SIGNAL") == True
    assert require_tier("API", "SIGNAL") == False
    assert require_tier("SIGNAL", "API") == True

def test_api_rate_limits():
    email = "limit@epoch.com"
    _delete_user_by_email(email)
    user = create_user(email, "pwd", "ROSTRA") # limit 100
    
    # Simulate hitting limit
    from src.api.auth import _load_users, _save_users
    users = _load_users()
    users[user.user_id]["api_calls_today"] = 99
    # Also set today's date so it doesn't reset it
    from datetime import datetime
    users[user.user_id]["last_api_call_date"] = datetime.utcnow().date().isoformat()
    _save_users(users)
    
    assert check_and_increment_api_calls(user.user_id) == True # 100th call
    assert check_and_increment_api_calls(user.user_id) == False # 101st call blocked

def test_token_flow():
    email = "token@test.com"
    _delete_user_by_email(email)
    user = create_user(email, "pwd", "API")
    token = create_access_token(user)
    assert token is not None
    
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user.user_id
    assert payload["tier"] == "API"

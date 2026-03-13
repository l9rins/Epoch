"""
Stripe Endpoints — SESSION C
Handles checkout session creation and webhook tier upgrades.

Tiers:
  Rostra  $29/mo  → tier = "ROSTRA"
  Signal  $149/mo → tier = "SIGNAL"
  API     $499/mo → tier = "API"

Rules:
  - Never log full card data
  - Always verify webhook signature before processing
  - Pure functions for tier mapping
"""

from __future__ import annotations

import os
import logging
from typing import Any

import stripe
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.auth import (
    get_user_from_token,
    _load_users,
    _save_users,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TIER_ROSTRA: str = "ROSTRA"
TIER_SIGNAL: str = "SIGNAL"
TIER_API: str = "API"

PRICE_TO_TIER: dict[str, str] = {}  # populated at startup from env


def _init_price_map() -> None:
    """Build price_id → tier mapping from environment variables."""
    global PRICE_TO_TIER
    PRICE_TO_TIER = {
        os.environ.get("STRIPE_PRICE_ROSTRA", ""): TIER_ROSTRA,
        os.environ.get("STRIPE_PRICE_SIGNAL", ""): TIER_SIGNAL,
        os.environ.get("STRIPE_PRICE_API", ""): TIER_API,
    }
    # Remove empty keys
    PRICE_TO_TIER = {k: v for k, v in PRICE_TO_TIER.items() if k}


_init_price_map()


def _get_stripe_client() -> stripe:
    """Configure and return stripe module."""
    secret = os.environ.get("STRIPE_SECRET_KEY", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    stripe.api_key = secret
    return stripe


def tier_from_price_id(price_id: str) -> str | None:
    """Map a Stripe price ID to an Epoch tier. Returns None if unknown."""
    return PRICE_TO_TIER.get(price_id)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    authorization: str = Header(default=""),
) -> CheckoutResponse:
    """
    Create a Stripe Checkout session for the given price.
    Requires valid JWT in Authorization header.
    """
    token = authorization.replace("Bearer ", "").strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    tier = tier_from_price_id(body.price_id)
    if not tier:
        raise HTTPException(status_code=400, detail="Invalid price ID")

    s = _get_stripe_client()

    try:
        session = s.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": body.price_id, "quantity": 1}],
            mode="subscription",
            success_url=body.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=body.cancel_url,
            client_reference_id=user.user_id,
            customer_email=user.email,
            metadata={
                "user_id": user.user_id,
                "tier": tier,
            },
        )
        logger.info("Checkout session created for user %s tier %s", user.user_id, tier)
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
    except s.error.StripeError as exc:
        logger.error("Stripe checkout error: %s", exc)
        raise HTTPException(status_code=502, detail="Stripe error") from exc


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="stripe-signature"),
) -> JSONResponse:
    """
    Stripe webhook handler.
    Verifies signature, then upgrades user tier on successful subscription.
    """
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    payload = await request.body()
    s = _get_stripe_client()

    try:
        event = s.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except s.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_cancelled(event["data"]["object"])

    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event["data"]["object"])

    return JSONResponse(content={"received": True})


# ---------------------------------------------------------------------------
# Webhook handlers — pure functions
# ---------------------------------------------------------------------------

def _handle_checkout_completed(session: dict[str, Any]) -> None:
    """Upgrade user tier after successful checkout."""
    user_id = session.get("metadata", {}).get("user_id")
    tier = session.get("metadata", {}).get("tier")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id or not tier:
        logger.error("Checkout completed but missing metadata: %s", session)
        return

    users = _load_users()
    user_data = users.get(user_id)
    if not user_data:
        logger.error("User %s not found after checkout", user_id)
        return

    user_data["tier"] = tier
    user_data["stripe_customer_id"] = customer_id
    user_data["stripe_subscription_id"] = subscription_id
    user_data["subscription_status"] = "active"

    # Update API call limit for new tier
    from src.api.auth import TIER_API_LIMITS
    user_data["api_calls_limit"] = TIER_API_LIMITS.get(tier, 100)

    users[user_id] = user_data
    _save_users(users)
    logger.info("User %s upgraded to tier %s", user_id, tier)


def _handle_subscription_cancelled(subscription: dict[str, Any]) -> None:
    """Downgrade user to ROSTRA on cancellation."""
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    users = _load_users()
    for uid, user_data in users.items():
        if user_data.get("stripe_customer_id") == customer_id:
            user_data["tier"] = TIER_ROSTRA
            user_data["subscription_status"] = "cancelled"
            users[uid] = user_data
            _save_users(users)
            logger.info("User %s downgraded to ROSTRA after cancellation", uid)
            return


def _handle_payment_failed(invoice: dict[str, Any]) -> None:
    """Mark subscription as past_due on failed payment."""
    customer_id = invoice.get("customer")
    if not customer_id:
        return

    users = _load_users()
    for uid, user_data in users.items():
        if user_data.get("stripe_customer_id") == customer_id:
            user_data["subscription_status"] = "past_due"
            users[uid] = user_data
            _save_users(users)
            logger.warning("Payment failed for user %s", uid)
            return


# ---------------------------------------------------------------------------
# Pricing info endpoint (public — no auth)
# ---------------------------------------------------------------------------

@router.get("/prices")
def get_prices() -> dict[str, Any]:
    """Return tier pricing for the frontend pricing page."""
    return {
        "tiers": [
            {
                "id": TIER_ROSTRA,
                "name": "Rostra",
                "price_monthly": 29,
                "price_id": os.environ.get("STRIPE_PRICE_ROSTRA", ""),
                "features": [
                    "Full roster intelligence",
                    "Daily game predictions",
                    "Win probability model",
                    "100 API calls/day",
                ],
            },
            {
                "id": TIER_SIGNAL,
                "name": "The Signal",
                "price_monthly": 149,
                "price_id": os.environ.get("STRIPE_PRICE_SIGNAL", ""),
                "features": [
                    "Everything in Rostra",
                    "Live Tier 1/2/3 alerts",
                    "Kelly criterion bet sizing",
                    "Mid-game injury hot-swap",
                    "Causal explanation engine",
                    "Betting journal + edge profile",
                    "1,000 API calls/day",
                ],
                "highlighted": True,
            },
            {
                "id": TIER_API,
                "name": "Epoch API",
                "price_monthly": 499,
                "price_id": os.environ.get("STRIPE_PRICE_API", ""),
                "features": [
                    "Everything in Signal",
                    "Raw simulation API access",
                    "WebSocket game streams",
                    "Bulk historical data",
                    "10,000 API calls/day",
                    "Priority support",
                ],
            },
        ]
    }

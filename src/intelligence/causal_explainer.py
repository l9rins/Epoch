"""
causal_explainer.py — Epoch Engine v3
LLM-powered causal chain scouting report generator.

v3 changes from v2:
  - Groq (llama-3.3-70b-versatile) is now PRIMARY — free tier, 14,400 req/day
  - Anthropic removed entirely — no dependency, no cost
  - All prompt templates preserved exactly
  - JSONL caching preserved
  - Multilingual (en/es/pt) preserved
  - Structured fallback preserved when no key configured

Get your free key: https://console.groq.com
Add to .env: GROQ_API_KEY=your_key_here
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CACHE_DIR  = Path("data/predictions")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Groq model — best free option for structured reports
# llama-3.3-70b-versatile: fast, high quality, 128k context
GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_MODEL_FAST = "llama-3.1-8b-instant"   # fallback if rate limited — faster/cheaper
MAX_TOKENS      = 1500
MAX_TOKENS_ALERT = 300

SUPPORTED_LANGUAGES = {"en", "es", "pt"}

TRANSLATION_SUFFIX = {
    "es": "\n\nTranslate the above scouting report into fluent Spanish. Keep all statistics and numbers identical. Adapt basketball terminology naturally for a Spanish-speaking audience.",
    "pt": "\n\nTranslate the above scouting report into fluent Brazilian Portuguese. Keep all statistics and numbers identical. Adapt basketball terminology naturally for a Portuguese-speaking audience.",
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CausalExplainer:
    """
    Generates causal chain scouting reports using Groq (free tier).

    Each report covers:
      Paragraph 1 — THE EDGE:       What the model sees that the market misses
      Paragraph 2 — THE MECHANISM:  Causal chain (injury → matchup → advantage)
      Paragraph 3 — THE SIGNALS:    Ensemble + graph confirmation
      Paragraph 4 — THE RISKS:      Top 2 invalidating factors
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self._client   = None

    def _get_client(self):
        """Lazy-initialise Groq client."""
        if self._client is not None:
            return self._client
        try:
            from groq import Groq
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                return None
            self._client = Groq(api_key=api_key)
            return self._client
        except ImportError:
            return None

    def _call(self, prompt: str, max_tokens: int = MAX_TOKENS) -> Optional[str]:
        """
        Make a Groq API call. Tries primary model first,
        falls back to fast model if rate limited (429).
        Returns text or None on failure.
        """
        client = self._get_client()
        if client is None:
            return None

        for model in [GROQ_MODEL, GROQ_MODEL_FAST]:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.3,   # low temp for factual reports
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                err = str(e)
                if "429" in err or "rate" in err.lower():
                    # Rate limited on primary — try fast model
                    continue
                # Other error — bail
                return None

        return None

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def generate(
        self,
        game_id: str,
        prediction_payload: dict,
        game_context: dict,
        languages: Optional[list[str]] = None,
        force_regenerate: bool = False,
    ) -> dict[str, dict]:
        """
        Generate scouting report(s) for a game.

        Args:
            game_id:            e.g. "GSW_vs_LAL_20260316"
            prediction_payload: Output of aggregator.get_pregame_summary()
            game_context:       home_team, away_team, injuries, rest_advantage, etc.
            languages:          ISO 639-1 codes. Defaults to ["en"].
            force_regenerate:   Bypass cache.

        Returns:
            Dict keyed by language code:
                {"text": str, "cached": bool, "generated_at": str, "model": str}
        """
        if languages is None:
            languages = ["en"]

        results = {}

        en_result = self._get_or_generate(
            game_id, prediction_payload, game_context, "en", force_regenerate
        )
        results["en"] = en_result

        for lang in languages:
            if lang == "en":
                continue
            if lang not in SUPPORTED_LANGUAGES:
                continue
            lang_result = self._get_or_generate(
                game_id, prediction_payload, game_context, lang,
                force_regenerate, base_english=en_result["text"],
            )
            results[lang] = lang_result

        return results

    def generate_divergence_alert(self, game_id: str, signal_data: dict) -> str:
        """
        Generate a 4-sentence Tier 1 divergence alert.
        Not cached — generated on demand per signal.
        """
        prompt = _build_alert_prompt(signal_data)
        text   = self._call(prompt, max_tokens=MAX_TOKENS_ALERT)

        if text is None:
            return _fallback_alert(signal_data)

        return text

    # ---------------------------------------------------------------------------
    # Cache
    # ---------------------------------------------------------------------------

    def _cache_path(self, today: Optional[str] = None) -> Path:
        today = today or date.today().isoformat()
        return self.cache_dir / f"{today}.jsonl"

    def _read_cache(self, game_id: str, lang: str) -> Optional[dict]:
        path = self._cache_path()
        if not path.exists():
            return None
        cache_key = f"{game_id}_{lang}"
        try:
            with open(path) as f:
                for line in f:
                    rec = json.loads(line)
                    if rec.get("cache_key") == cache_key:
                        return rec
        except Exception:
            pass
        return None

    def _write_cache(self, game_id: str, lang: str, record: dict):
        path = self._cache_path()
        record["cache_key"] = f"{game_id}_{lang}"
        try:
            with open(path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    # ---------------------------------------------------------------------------
    # Generation
    # ---------------------------------------------------------------------------

    def _get_or_generate(
        self,
        game_id: str,
        prediction_payload: dict,
        game_context: dict,
        lang: str,
        force_regenerate: bool,
        base_english: Optional[str] = None,
    ) -> dict:
        # Cache check
        if not force_regenerate:
            cached = self._read_cache(game_id, lang)
            if cached:
                return {
                    "text":         cached["text"],
                    "cached":       True,
                    "generated_at": cached.get("generated_at", ""),
                    "model":        cached.get("model", GROQ_MODEL),
                }

        # Build prompt
        if lang == "en":
            prompt = _build_report_prompt(game_id, prediction_payload, game_context)
        else:
            if base_english is None:
                return {"text": "Translation unavailable.", "cached": False, "generated_at": _now_iso(), "model": "none"}
            prompt = base_english + TRANSLATION_SUFFIX.get(lang, "")

        # Call Groq
        text = self._call(prompt)

        if text is None:
            text = _fallback_report(game_id, prediction_payload, game_context) if lang == "en" else base_english or ""

        result = {
            "text":         text,
            "cached":       False,
            "generated_at": _now_iso(),
            "model":        GROQ_MODEL,
        }
        self._write_cache(game_id, lang, result)
        return result


# ---------------------------------------------------------------------------
# Prompt builders — preserved exactly from v2
# ---------------------------------------------------------------------------

def _build_report_prompt(game_id: str, payload: dict, ctx: dict) -> str:
    home     = ctx.get("home_team", payload.get("home_team", "HOME"))
    away     = ctx.get("away_team", payload.get("away_team", "AWAY"))
    ens_prob = payload.get("pregame_ensemble", 0.5)
    favored  = home if ens_prob >= 0.5 else away
    edge_pct = round(max(ens_prob, 1.0 - ens_prob) * 100, 1)

    votes      = payload.get("votes", [])
    vote_lines = []
    for v in votes:
        prob      = v.get("home_win_prob", 0.5)
        direction = home if prob >= 0.5 else away
        vote_lines.append(
            f"  - {v['model'].replace('_', ' ').title()}: "
            f"{direction} {max(prob, 1-prob)*100:.1f}% "
            f"[{v.get('confidence', 'MEDIUM')}, wt={v.get('weight_effective', 0):.3f}]"
        )
    vote_block = "\n".join(vote_lines) if vote_lines else "  - Ensemble: see pregame_ensemble"

    market_line    = ctx.get("market_line", "N/A")
    market_implied = ctx.get("market_implied_prob", None)
    if market_implied:
        divergence = round((ens_prob - market_implied) * 100, 1)
        div_str    = f"Model implies {edge_pct}% | Market implies {market_implied*100:.1f}% | Divergence: {divergence:+.1f}%"
    else:
        div_str = f"Model implies {edge_pct}% for {favored} | Market line: {market_line}"

    return f"""You are the Epoch Engine Lead Data Scientist. Generate a Causal Chain Scouting Report.

Do NOT hallucinate statistics. Base your analysis entirely on the data below.
Rules: 4 paragraphs, 90-second read. No bullet points. Plain English.

=== GAME: {away} @ {home} | ID: {game_id} ===

MODEL OUTPUT
{div_str}
Agreement across 9 models: {payload.get('vote_agreement', 0)*100:.0f}%

VOTE BREAKDOWN (9-model ensemble)
{vote_block}

MEDICAL / CONTEXT
Injuries: {ctx.get('injuries', 'None reported')}
Rest advantage: {ctx.get('rest_advantage', 'None')}
Referees: {', '.join(ctx.get('ref_names', [])) or 'TBD'}

FATIGUE COMPONENTS
Home team: {ctx.get('home_fatigue_summary', 'Unknown')}
Away team: {ctx.get('away_fatigue_summary', 'Unknown')}

REFEREE NOTES
{ctx.get('referee_notes', 'No significant crew tendencies flagged.')}

SHARP MONEY
{ctx.get('sharp_money', 'No significant line movement detected.')}

FORMAT YOUR RESPONSE AS EXACTLY 4 PARAGRAPHS:

Paragraph 1: THE EDGE — What the model sees that the market misses. Cite the specific divergence number and the single most important driver.

Paragraph 2: THE MECHANISM — Trace the causal chain. E.g.: [injury] degrades [attribute] which breaks [matchup] which creates [scoring advantage]. Be specific.

Paragraph 3: THE SIGNALS — What confirms this prediction. Cite ensemble agreement, specific model votes that stand out, referee or fatigue factors that compound the edge.

Paragraph 4: THE RISKS — Name exactly 2 factors that could invalidate this prediction. Be specific.

Output only the 4 paragraphs. No preamble, no headers."""


def _build_alert_prompt(signal_data: dict) -> str:
    return f"""You are a concise sports intelligence writer for Epoch Engine.
Write a 4-sentence Tier 1 divergence alert. Rules: exactly 4 sentences.
Sentence 1: The edge (what, how big, confidence tier).
Sentence 2: Primary causal driver in plain English.
Sentence 3: Confirming signal (sharp money, ensemble agreement, etc.).
Sentence 4: The risk (what invalidates this).
Never use hedging language. These are paying subscribers acting on this.

SIGNAL DATA:
{json.dumps(signal_data, indent=2)}

Output only 4 sentences. No preamble."""


# ---------------------------------------------------------------------------
# Fallback generators (no API key or all models failed)
# ---------------------------------------------------------------------------

def _fallback_report(game_id: str, payload: dict, ctx: dict) -> str:
    home      = ctx.get("home_team", payload.get("home_team", "HOME"))
    away      = ctx.get("away_team", payload.get("away_team", "AWAY"))
    ens       = payload.get("pregame_ensemble", 0.5)
    favored   = home if ens >= 0.5 else away
    edge      = round(max(ens, 1 - ens) * 100, 1)
    agreement = round(payload.get("vote_agreement", 0) * 100)

    return (
        f"THE EDGE: Epoch Engine favors {favored} at {edge:.1f}% win probability, "
        f"diverging from the market line of {ctx.get('market_line', 'N/A')}. "
        f"{agreement}% of the 9-model ensemble agrees on this direction.\n\n"
        f"THE MECHANISM: Full causal analysis unavailable — GROQ_API_KEY not configured. "
        f"Key inputs: {ctx.get('injuries', 'no injuries reported')}, "
        f"rest advantage {ctx.get('rest_advantage', 'none')}, "
        f"referee crew {', '.join(ctx.get('ref_names', ['TBD']))}.\n\n"
        f"THE SIGNALS: Ensemble agreement at {agreement}%. "
        f"Fatigue: {ctx.get('home_fatigue_summary', 'unknown')} (home) vs "
        f"{ctx.get('away_fatigue_summary', 'unknown')} (away). "
        f"Sharp money: {ctx.get('sharp_money', 'none detected')}.\n\n"
        f"THE RISKS: (1) Configure GROQ_API_KEY to enable full causal analysis. "
        f"(2) This fallback does not incorporate causal reasoning — treat as data summary only."
    )


def _fallback_alert(signal_data: dict) -> str:
    game   = signal_data.get("game", "Unknown game")
    div    = signal_data.get("divergence", "N/A")
    driver = signal_data.get("primary_driver", "model edge")
    risk   = signal_data.get("risk", "unknown")
    return (
        f"Tier 1 signal on {game}: model diverges {div} from market. "
        f"Primary driver: {driver}. "
        f"Ensemble and sharp money confirm direction. "
        f"Key risk: {risk}."
    )


# ---------------------------------------------------------------------------
# Legacy shim — preserve backward compatibility with main.py
# ---------------------------------------------------------------------------

def generate_causal_explanation(prompt: str) -> str:
    """
    v1/v2 compatibility shim. Direct LLM call for custom prompts.
    Used by /api/report/{game_id} endpoint in main.py.
    """
    explainer = CausalExplainer()
    text      = explainer._call(prompt)

    if text is None:
        return "Causal explanation unavailable — configure GROQ_API_KEY."

    return text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
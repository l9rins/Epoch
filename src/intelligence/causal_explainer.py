"""
causal_explainer.py — Epoch Engine v2
LLM-powered causal chain scouting report generator.

Upgrade from v1:
  - v1: Groq / llama-3.3-70b, no prompt structure, no caching, no multilingual
  - v2: Claude claude-sonnet-4-20250514 via Anthropic SDK (Prompt 03 template from specs/prompts.md)
        - Structured prompt with all 9 ensemble votes, fatigue components, referee bias
        - JSONL caching to data/predictions/YYYY-MM-DD.jsonl keyed by game_id
        - Multilingual: English + Spanish + Portuguese variants (NBA global reach)
        - Graceful fallback to structured fallback report if API key absent

Usage:
    from src.intelligence.causal_explainer import CausalExplainer

    explainer = CausalExplainer()
    report = explainer.generate(
        game_id="GSW_vs_LAL_20260316",
        prediction_payload=aggregator.get_pregame_summary(),
        game_context={...},
        languages=["en", "es", "pt"],
    )
    print(report["en"]["text"])
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------

CACHE_DIR = Path("data/predictions")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1500

SUPPORTED_LANGUAGES = {"en", "es", "pt"}

LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish (Español)",
    "pt": "Portuguese (Português)",
}

TRANSLATION_SUFFIX = {
    "es": "\n\nTranslate the above scouting report into fluent Spanish. Keep all statistics and numbers identical. Adapt basketball terminology naturally for a Spanish-speaking audience.",
    "pt": "\n\nTranslate the above scouting report into fluent Brazilian Portuguese. Keep all statistics and numbers identical. Adapt basketball terminology naturally for a Portuguese-speaking audience.",
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CausalExplainer:
    """
    Generates causal chain scouting reports using Claude.

    Each report covers:
      Paragraph 1 — THE EDGE:       What the simulation sees the market misses
      Paragraph 2 — THE MECHANISM:  Causal chain (injury → matchup → advantage)
      Paragraph 3 — THE SIGNALS:    Ensemble + graph confirmation
      Paragraph 4 — THE RISKS:      Top 2 invalidating factors
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or CACHE_DIR
        self._client = None

    def _get_client(self):
        """Lazy-initialise Anthropic client."""
        if self._client is not None:
            return self._client
        try:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            self._client = anthropic.Anthropic(api_key=api_key)
            return self._client
        except ImportError:
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
            game_id:            Unique game identifier, e.g. "GSW_vs_LAL_20260316"
            prediction_payload: Output of aggregator.get_pregame_summary()
            game_context:       Dict with home_team, away_team, injuries, rest_advantage,
                                market_line, market_total, ref_names, etc.
            languages:          List of ISO 639-1 codes. Defaults to ["en"].
            force_regenerate:   Bypass cache and regenerate even if cached.

        Returns:
            Dict keyed by language code. Each value is:
                {"text": str, "cached": bool, "generated_at": str, "tokens_used": int}
        """
        if languages is None:
            languages = ["en"]

        results = {}

        # Always generate English first (other languages translate from it)
        en_result = self._get_or_generate(
            game_id, prediction_payload, game_context, "en", force_regenerate
        )
        results["en"] = en_result

        for lang in languages:
            if lang == "en":
                continue
            if lang not in SUPPORTED_LANGUAGES:
                continue
            # Use English text as base for translation
            lang_result = self._get_or_generate(
                game_id, prediction_payload, game_context, lang,
                force_regenerate, base_english=en_result["text"],
            )
            results[lang] = lang_result

        return results

    def generate_divergence_alert(
        self,
        game_id: str,
        signal_data: dict,
    ) -> str:
        """
        Generate a 4-sentence Tier 1 divergence alert (Prompt 09 template).
        Not cached — these are generated on demand per signal.
        """
        client = self._get_client()
        prompt = _build_alert_prompt(signal_data)

        if client is None:
            return _fallback_alert(signal_data)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            return _fallback_alert(signal_data) + f" [API error: {e}]"

    # ---------------------------------------------------------------------------
    # Cache layer
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
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")

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
                    "text": cached["text"],
                    "cached": True,
                    "generated_at": cached.get("generated_at", ""),
                    "tokens_used": cached.get("tokens_used", 0),
                }

        client = self._get_client()

        if lang == "en":
            prompt = _build_report_prompt(game_id, prediction_payload, game_context)
        else:
            if base_english is None:
                return {"text": "Translation unavailable.", "cached": False, "generated_at": "", "tokens_used": 0}
            prompt = base_english + TRANSLATION_SUFFIX.get(lang, "")

        if client is None:
            text = _fallback_report(game_id, prediction_payload, game_context) if lang == "en" else prompt
            result = {
                "text": text,
                "cached": False,
                "generated_at": _now_iso(),
                "tokens_used": 0,
            }
            self._write_cache(game_id, lang, result)
            return result

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            tokens = response.usage.input_tokens + response.usage.output_tokens
        except Exception as e:
            text = _fallback_report(game_id, prediction_payload, game_context)
            tokens = 0

        result = {
            "text": text,
            "cached": False,
            "generated_at": _now_iso(),
            "tokens_used": tokens,
        }
        self._write_cache(game_id, lang, result)
        return result


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_report_prompt(
    game_id: str,
    payload: dict,
    ctx: dict,
) -> str:
    """
    Constructs the full Prompt 03 template from specs/prompts.md, enriched
    with all 9 ensemble votes and fatigue/referee components.
    """
    home = ctx.get("home_team", payload.get("home_team", "HOME"))
    away = ctx.get("away_team", payload.get("away_team", "AWAY"))
    ens_prob = payload.get("pregame_ensemble", 0.5)
    favored = home if ens_prob >= 0.5 else away
    edge_pct = round(max(ens_prob, 1.0 - ens_prob) * 100, 1)

    # Format vote breakdown
    votes = payload.get("votes", [])
    vote_lines = []
    for v in votes:
        prob = v.get("home_win_prob", 0.5)
        direction = home if prob >= 0.5 else away
        vote_lines.append(
            f"  - {v['model'].replace('_', ' ').title()}: "
            f"{direction} {max(prob, 1-prob)*100:.1f}% "
            f"[{v.get('confidence', 'MEDIUM')}, wt={v.get('weight_effective', 0):.3f}]"
        )
    vote_block = "\n".join(vote_lines) if vote_lines else "  - Ensemble: see pregame_ensemble"

    # Market divergence
    market_line = ctx.get("market_line", "N/A")
    market_implied = ctx.get("market_implied_prob", None)
    if market_implied:
        divergence = round((ens_prob - market_implied) * 100, 1)
        div_str = f"Simulation implies {edge_pct}% | Market implies {market_implied*100:.1f}% | Divergence: {divergence:+.1f}%"
    else:
        div_str = f"Simulation implies {edge_pct}% for {favored} | Market line: {market_line}"

    return f"""You are the Epoch Engine Lead Data Scientist. Generate a Causal Chain Scouting Report.

Do NOT hallucinate statistics. Base your analysis entirely on the data below.
Rules: 4 paragraphs, 90-second read. No bullet points. Plain English.

=== GAME: {away} @ {home} | ID: {game_id} ===

SIMULATION OUTPUT
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

Paragraph 1: THE EDGE — What the simulation sees that the market misses. Cite the specific divergence number and the single most important driver.

Paragraph 2: THE MECHANISM — Trace the causal chain. E.g.: [injury] degrades [attribute] which breaks [matchup] which creates [scoring advantage]. Be specific about which .ROS attributes are affected.

Paragraph 3: THE SIGNALS — What confirms this prediction. Cite ensemble agreement, specific model votes that stand out, referee or fatigue factors that compound the edge.

Paragraph 4: THE RISKS — Name exactly 2 factors that could invalidate this prediction. Be specific — not generic "injury risk" but exactly what would have to change.

Output only the 4 paragraphs. No preamble, no headers."""


def _build_alert_prompt(signal_data: dict) -> str:
    """Prompt 09 template: 4-sentence Tier 1 divergence alert."""
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
# Fallback generators (no API key)
# ---------------------------------------------------------------------------

def _fallback_report(game_id: str, payload: dict, ctx: dict) -> str:
    home = ctx.get("home_team", payload.get("home_team", "HOME"))
    away = ctx.get("away_team", payload.get("away_team", "AWAY"))
    ens = payload.get("pregame_ensemble", 0.5)
    favored = home if ens >= 0.5 else away
    edge = round(max(ens, 1 - ens) * 100, 1)
    agreement = round(payload.get("vote_agreement", 0) * 100)

    return (
        f"THE EDGE: The Epoch Engine simulation favors {favored} at {edge:.1f}% "
        f"win probability, diverging from the market line of {ctx.get('market_line', 'N/A')}. "
        f"{agreement}% of the 9-model ensemble agrees on this direction.\n\n"
        f"THE MECHANISM: Full causal analysis unavailable — ANTHROPIC_API_KEY not configured. "
        f"Key inputs include: {ctx.get('injuries', 'no injuries reported')}, "
        f"rest advantage {ctx.get('rest_advantage', 'none')}, and referee crew {', '.join(ctx.get('ref_names', ['TBD']))}.\n\n"
        f"THE SIGNALS: Ensemble vote agreement at {agreement}%. "
        f"Fatigue model: {ctx.get('home_fatigue_summary', 'unknown')} (home) vs "
        f"{ctx.get('away_fatigue_summary', 'unknown')} (away). "
        f"Sharp money: {ctx.get('sharp_money', 'none detected')}.\n\n"
        f"THE RISKS: (1) Configure ANTHROPIC_API_KEY to enable full causal analysis. "
        f"(2) This fallback report does not incorporate causal reasoning — treat as data summary only."
    )


def _fallback_alert(signal_data: dict) -> str:
    game = signal_data.get("game", "Unknown game")
    div = signal_data.get("divergence", "N/A")
    driver = signal_data.get("primary_driver", "simulation edge")
    risk = signal_data.get("risk", "unknown")
    return (
        f"Tier 1 signal on {game}: simulation diverges {div} from market. "
        f"Primary driver: {driver}. "
        f"Ensemble and sharp money confirm direction. "
        f"Key risk: {risk}."
    )


# ---------------------------------------------------------------------------
# Legacy shim
# ---------------------------------------------------------------------------

def generate_causal_explanation(prompt: str) -> str:
    """
    v1 compatibility shim. Routes through CausalExplainer with minimal context.
    Direct LLM call for custom prompts.
    """
    explainer = CausalExplainer()
    client = explainer._get_client()
    if client is None:
        # Try Groq fallback (v1 behaviour)
        try:
            from groq import Groq
            api_key = os.environ.get("GROQ_API_KEY")
            if api_key:
                groq_client = Groq(api_key=api_key)
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1000,
                )
                return response.choices[0].message.content
        except Exception:
            pass
        return "Causal explanation unavailable — configure ANTHROPIC_API_KEY or GROQ_API_KEY."

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Causal explanation unavailable: {e}"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

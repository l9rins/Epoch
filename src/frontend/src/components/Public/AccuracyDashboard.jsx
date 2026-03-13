import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

const API = import.meta.env.VITE_API_URL || "";

function fetchAccuracy() {
  return fetch(`${API}/api/public/accuracy`).then((r) => r.json());
}
function fetchTrackRecord() {
  return fetch(`${API}/api/public/track-record`).then((r) => r.json());
}
function fetchSignalSample() {
  return fetch(`${API}/api/public/signal-sample`).then((r) => r.json());
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div className="bg-terminal-surface border border-terminal-border rounded-lg p-5 flex flex-col gap-1">
      <span className="text-terminal-muted text-xs font-mono uppercase tracking-widest">
        {label}
      </span>
      <span
        className={`text-3xl font-mono font-bold ${
          accent === "green"
            ? "text-terminal-green"
            : accent === "red"
            ? "text-terminal-red"
            : accent === "accent"
            ? "text-terminal-accent"
            : "text-terminal-text"
        }`}
      >
        {value ?? "—"}
      </span>
      {sub && (
        <span className="text-terminal-muted text-xs font-mono">{sub}</span>
      )}
    </div>
  );
}

function TierBadge({ tier }) {
  const colors = {
    1: "bg-terminal-red/20 text-terminal-red border-terminal-red/40",
    2: "bg-terminal-yellow/20 text-terminal-yellow border-terminal-yellow/40",
    3: "bg-terminal-muted/20 text-terminal-muted border-terminal-muted/40",
  };
  return (
    <span
      className={`text-xs font-mono px-2 py-0.5 rounded border ${
        colors[tier] || colors[3]
      }`}
    >
      T{tier}
    </span>
  );
}

function ResultBadge({ result }) {
  if (result === "WIN")
    return (
      <span className="text-terminal-green font-mono text-sm font-bold">
        ✓ WIN
      </span>
    );
  if (result === "LOSS")
    return (
      <span className="text-terminal-red font-mono text-sm font-bold">
        ✗ LOSS
      </span>
    );
  return (
    <span className="text-terminal-muted font-mono text-sm">PENDING</span>
  );
}

export default function AccuracyDashboard() {
  const { data: accuracy, isLoading: loadingAcc } = useQuery({
    queryKey: ["public-accuracy"],
    queryFn: fetchAccuracy,
    refetchInterval: 60_000,
  });

  const { data: trackRecord, isLoading: loadingTR } = useQuery({
    queryKey: ["track-record"],
    queryFn: fetchTrackRecord,
  });

  const { data: signalSample } = useQuery({
    queryKey: ["signal-sample"],
    queryFn: fetchSignalSample,
  });

  const hitRatePct = accuracy?.hit_rate
    ? `${(accuracy.hit_rate * 100).toFixed(1)}%`
    : null;

  return (
    <div className="min-h-screen bg-terminal-bg text-terminal-text font-mono">
      {/* Header */}
      <div className="border-b border-terminal-border px-8 py-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-terminal-accent tracking-tight">
            EPOCH ENGINE
          </h1>
          <p className="text-terminal-muted text-sm mt-0.5">
            NBA Prediction Intelligence · Public Track Record
          </p>
        </div>
        <a
          href="/login"
          className="bg-terminal-accent text-terminal-bg px-5 py-2 rounded font-mono text-sm font-bold hover:opacity-90 transition"
        >
          Subscribe →
        </a>
      </div>

      <div className="max-w-5xl mx-auto px-8 py-10 space-y-10">
        {/* Hero claim */}
        <div className="text-center space-y-2">
          <p className="text-terminal-muted text-sm uppercase tracking-widest">
            Verified · Timestamped before tip-off · No retroactive edits
          </p>
          <h2 className="text-4xl font-bold text-terminal-text">
            {hitRatePct ? (
              <>
                <span className="text-terminal-green">{hitRatePct}</span> hit
                rate — last 30 days
              </>
            ) : (
              "Loading track record..."
            )}
          </h2>
          <p className="text-terminal-muted text-sm">
            {accuracy?.completed ?? "—"} graded predictions ·{" "}
            {accuracy?.calibration_samples?.toLocaleString() ?? "—"} calibration
            samples · Brier score{" "}
            <span className="text-terminal-accent">
              {accuracy?.brier_score ?? "—"}
            </span>
          </p>
        </div>

        {/* Stat grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="30-Day Hit Rate"
            value={hitRatePct}
            sub={`${accuracy?.wins ?? 0}W ${accuracy?.losses ?? 0}L`}
            accent="green"
          />
          <StatCard
            label="Brier Score"
            value={accuracy?.brier_score}
            sub="Lower = better calibrated"
            accent="accent"
          />
          <StatCard
            label="Predictions"
            value={accuracy?.total_predictions}
            sub="Last 30 days"
          />
          <StatCard
            label="Samples"
            value={accuracy?.calibration_samples?.toLocaleString()}
            sub="Total calibration history"
          />
        </div>

        {/* Tier breakdown */}
        {accuracy?.tier_breakdown?.length > 0 && (
          <div className="border border-terminal-border rounded-lg overflow-hidden">
            <div className="px-5 py-3 bg-terminal-surface border-b border-terminal-border">
              <span className="text-terminal-muted text-xs uppercase tracking-widest">
                Hit Rate by Signal Tier
              </span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-terminal-border text-terminal-muted text-xs">
                  <th className="text-left px-5 py-3">Tier</th>
                  <th className="text-right px-5 py-3">Hit Rate</th>
                  <th className="text-right px-5 py-3">W</th>
                  <th className="text-right px-5 py-3">L</th>
                  <th className="text-right px-5 py-3">Samples</th>
                </tr>
              </thead>
              <tbody>
                {accuracy.tier_breakdown.map((t) => (
                  <tr
                    key={t.tier}
                    className="border-b border-terminal-border/50 hover:bg-terminal-surface/50"
                  >
                    <td className="px-5 py-3">
                      <TierBadge tier={t.tier} />
                    </td>
                    <td className="text-right px-5 py-3 text-terminal-green font-bold">
                      {t.hit_rate
                        ? `${(t.hit_rate * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="text-right px-5 py-3 text-terminal-green">
                      {t.wins}
                    </td>
                    <td className="text-right px-5 py-3 text-terminal-red">
                      {t.losses}
                    </td>
                    <td className="text-right px-5 py-3 text-terminal-muted">
                      {t.sample_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Signal sample — acquisition hook */}
        {signalSample?.available && (
          <div className="border border-terminal-accent/30 rounded-lg overflow-hidden">
            <div className="px-5 py-3 bg-terminal-accent/10 border-b border-terminal-accent/20 flex items-center justify-between">
              <span className="text-terminal-accent text-xs uppercase tracking-widest font-bold">
                Sample T1 Signal
              </span>
              <TierBadge tier={1} />
            </div>
            <div className="px-5 py-4 space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-terminal-text font-bold">
                  {signalSample.signal.away_team} @{" "}
                  {signalSample.signal.home_team}
                </span>
                <ResultBadge result={signalSample.signal.result} />
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-terminal-muted">Win Probability </span>
                  <span className="text-terminal-accent font-bold">
                    {signalSample.signal.win_probability
                      ? `${(signalSample.signal.win_probability * 100).toFixed(1)}%`
                      : "—"}
                  </span>
                </div>
                <div>
                  <span className="text-terminal-muted">Confidence </span>
                  <span className="text-terminal-green font-bold">
                    {signalSample.signal.confidence}
                  </span>
                </div>
                <div>
                  <span className="text-terminal-muted">Kelly Sizing </span>
                  <span className="text-terminal-yellow">
                    {signalSample.signal.kelly_sizing}
                  </span>
                </div>
                <div>
                  <span className="text-terminal-muted">Date </span>
                  <span>{signalSample.signal.date}</span>
                </div>
              </div>
              <div className="pt-2 border-t border-terminal-border">
                <a
                  href="/login"
                  className="inline-block bg-terminal-accent text-terminal-bg px-5 py-2 rounded text-sm font-bold hover:opacity-90 transition"
                >
                  Get Kelly sizing on every T1 signal — $149/mo →
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Track record feed */}
        <div className="border border-terminal-border rounded-lg overflow-hidden">
          <div className="px-5 py-3 bg-terminal-surface border-b border-terminal-border flex items-center justify-between">
            <span className="text-terminal-muted text-xs uppercase tracking-widest">
              Last {trackRecord?.records?.length ?? 0} Graded Predictions
            </span>
            <span className="text-terminal-muted text-xs">
              {trackRecord?.summary?.hit_rate
                ? `${(trackRecord.summary.hit_rate * 100).toFixed(1)}% hit rate`
                : ""}
            </span>
          </div>
          {loadingTR ? (
            <div className="px-5 py-8 text-center text-terminal-muted text-sm">
              Loading predictions...
            </div>
          ) : trackRecord?.records?.length === 0 ? (
            <div className="px-5 py-8 text-center text-terminal-muted text-sm">
              No graded predictions yet. Check back after tonight's games.
            </div>
          ) : (
            <div className="divide-y divide-terminal-border/50 max-h-96 overflow-y-auto">
              {(trackRecord?.records ?? []).map((r, i) => (
                <div
                  key={r.game_id || i}
                  className="px-5 py-3 flex items-center justify-between hover:bg-terminal-surface/50 text-sm"
                >
                  <div className="flex items-center gap-3">
                    <TierBadge tier={r.tier} />
                    <span className="text-terminal-muted text-xs">
                      {r.date}
                    </span>
                    <span>
                      {r.away_team}{" "}
                      <span className="text-terminal-muted">@</span>{" "}
                      {r.home_team}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-terminal-muted text-xs">
                      {r.predicted_winner}{" "}
                      {r.win_probability
                        ? `${(r.win_probability * 100).toFixed(0)}%`
                        : ""}
                    </span>
                    <ResultBadge result={r.result} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer CTA */}
        <div className="text-center border border-terminal-border rounded-lg px-8 py-10 space-y-4">
          <h3 className="text-xl font-bold text-terminal-text">
            Ready to bet with an edge?
          </h3>
          <p className="text-terminal-muted text-sm max-w-md mx-auto">
            Signal subscribers get Kelly criterion bet sizing, live Tier 1
            alerts, mid-game injury hot-swap, and a personalized edge profile
            built from your own betting history.
          </p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <a
              href="/login?plan=SIGNAL"
              className="bg-terminal-accent text-terminal-bg px-6 py-2.5 rounded font-bold hover:opacity-90 transition"
            >
              Start Signal — $149/mo
            </a>
            <a
              href="/login?plan=ROSTRA"
              className="border border-terminal-border text-terminal-muted px-6 py-2.5 rounded hover:border-terminal-accent hover:text-terminal-accent transition text-sm"
            >
              Rostra — $29/mo
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

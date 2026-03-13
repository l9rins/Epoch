import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

const API = import.meta.env.VITE_API_URL || "";

function fetchPrices() {
  return fetch(`${API}/api/stripe/prices`).then((r) => r.json());
}

async function createCheckout(priceId, token) {
  const origin = window.location.origin;
  const res = await fetch(`${API}/api/stripe/checkout`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      price_id: priceId,
      success_url: `${origin}/dashboard?upgraded=true`,
      cancel_url: `${origin}/pricing`,
    }),
  });
  if (!res.ok) throw new Error("Checkout failed");
  return res.json();
}

function Check() {
  return (
    <svg className="w-4 h-4 text-terminal-green shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

export default function PricingPage({ accessToken }) {
  const [loading, setLoading] = useState(null);
  const [error, setError] = useState(null);

  const { data } = useQuery({
    queryKey: ["prices"],
    queryFn: fetchPrices,
  });

  const tiers = data?.tiers ?? [];

  async function handleSubscribe(tier) {
    if (!accessToken) {
      window.location.href = `/login?plan=${tier.id}`;
      return;
    }
    setLoading(tier.id);
    setError(null);
    try {
      const { checkout_url } = await createCheckout(tier.price_id, accessToken);
      window.location.href = checkout_url;
    } catch {
      setError("Something went wrong. Please try again.");
      setLoading(null);
    }
  }

  return (
    <div className="min-h-screen bg-terminal-bg text-terminal-text font-mono">
      <div className="max-w-5xl mx-auto px-8 py-16 space-y-12">
        {/* Header */}
        <div className="text-center space-y-3">
          <p className="text-terminal-muted text-xs uppercase tracking-widest">
            Epoch Engine Pricing
          </p>
          <h1 className="text-4xl font-bold text-terminal-text">
            One platform. Three tiers.
          </h1>
          <p className="text-terminal-muted text-sm max-w-lg mx-auto">
            From casual fan to professional bettor to quantitative developer.
            Cancel anytime.
          </p>
        </div>

        {error && (
          <div className="border border-terminal-red/40 bg-terminal-red/10 text-terminal-red text-sm px-4 py-3 rounded text-center">
            {error}
          </div>
        )}

        {/* Tier cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tiers.map((tier) => (
            <div
              key={tier.id}
              className={`border rounded-lg overflow-hidden flex flex-col ${
                tier.highlighted
                  ? "border-terminal-accent shadow-lg shadow-terminal-accent/10"
                  : "border-terminal-border"
              }`}
            >
              {tier.highlighted && (
                <div className="bg-terminal-accent text-terminal-bg text-xs font-bold text-center py-1.5 tracking-widest uppercase">
                  Most Popular
                </div>
              )}
              <div className="p-6 flex flex-col flex-1 gap-6">
                <div>
                  <h2 className="text-lg font-bold text-terminal-text">
                    {tier.name}
                  </h2>
                  <div className="mt-2 flex items-baseline gap-1">
                    <span className="text-3xl font-bold text-terminal-accent">
                      ${tier.price_monthly}
                    </span>
                    <span className="text-terminal-muted text-sm">/mo</span>
                  </div>
                </div>

                <ul className="space-y-2.5 flex-1">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <Check />
                      <span className="text-terminal-muted">{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSubscribe(tier)}
                  disabled={loading === tier.id}
                  className={`w-full py-2.5 rounded font-bold text-sm transition ${
                    tier.highlighted
                      ? "bg-terminal-accent text-terminal-bg hover:opacity-90"
                      : "border border-terminal-border text-terminal-muted hover:border-terminal-accent hover:text-terminal-accent"
                  } disabled:opacity-50`}
                >
                  {loading === tier.id
                    ? "Redirecting..."
                    : `Get ${tier.name}`}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Trust signals */}
        <div className="grid grid-cols-3 gap-6 text-center text-sm">
          <div className="space-y-1">
            <div className="text-terminal-green font-bold text-lg">239</div>
            <div className="text-terminal-muted text-xs">Tests passing</div>
          </div>
          <div className="space-y-1">
            <div className="text-terminal-green font-bold text-lg">0.837</div>
            <div className="text-terminal-muted text-xs">Model AUC</div>
          </div>
          <div className="space-y-1">
            <div className="text-terminal-green font-bold text-lg">3,685</div>
            <div className="text-terminal-muted text-xs">Calibration samples</div>
          </div>
        </div>

        <div className="text-center text-terminal-muted text-xs">
          <a href="/accuracy" className="hover:text-terminal-accent transition">
            View public track record →
          </a>
        </div>
      </div>
    </div>
  );
}

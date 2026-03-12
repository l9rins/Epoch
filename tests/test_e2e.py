from src.intelligence.causal_dag import run_causal_inference, CausalNode
r1 = run_causal_inference(away_interventions={CausalNode.PLAYER_HEALTH: 0.3})
print(f'Causal DAG: WP adj = {r1.win_probability_adjustment:+.4f} OK')

# System 2: Embeddings
from src.intelligence.player_embeddings import EmbeddingSpace
space = EmbeddingSpace()
space.seed_with_defaults(30)
sim = space.find_similar('player_000', top_k=3, exclude_same_season=False)
print(f'Embeddings: top match = {sim[0][0].player_name} ({sim[0][1]:.4f}) OK')

# System 3: Adversarial
from src.intelligence.adversarial_network import build_adversarial_system, generate_synthetic_training_games, run_adversarial_training_cycle
o, adv, mkt = build_adversarial_system()
games = generate_synthetic_training_games(100)
res = run_adversarial_training_cycle(o, adv, mkt, games, cycles=20)
print(f'Adversarial: {res["cycles_completed"]} cycles, error={res["final_avg_error"]} OK')

# System 4: Quantum
from src.simulation.quantum_roster import _build_synthetic_quantum_roster, run_quantum_monte_carlo
h = _build_synthetic_quantum_roster('GSW')
a = _build_synthetic_quantum_roster('LAL')
qr = run_quantum_monte_carlo(h, a, n_iterations=500, seed=42)
print(f'Quantum: WP={qr["win_probability"]}, CI={qr["confidence_interval_80pct"]}, profile={qr["variance_profile"]} OK')

print()
print('ALL 4 SYSTEMS OPERATIONAL')

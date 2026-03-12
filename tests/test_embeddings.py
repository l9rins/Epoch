import numpy as np
from src.intelligence.player_embeddings import (
    EmbeddingSpace, build_embedding_from_ros_player, EMBEDDING_DIM
)

def test_embedding_dimension():
    player_data = {"height_inches": 78, "weight_lbs": 215, "age": 26, "era_year": 2024}
    skills = [7.0] * 42
    tendencies = [50.0] * 57
    vec = build_embedding_from_ros_player(player_data, skills, tendencies)
    assert vec.shape == (EMBEDDING_DIM,)

def test_all_values_in_range():
    player_data = {"height_inches": 78, "weight_lbs": 215, "age": 26, "era_year": 2024}
    skills = [13.0] * 42
    tendencies = [99.0] * 57
    vec = build_embedding_from_ros_player(player_data, skills, tendencies)
    assert np.all(vec >= 0.0)

def test_similarity_self_is_one():
    space = EmbeddingSpace("data/test_embeddings_tmp.json")
    space.seed_with_defaults(10)
    emb = space.embeddings["player_000"]
    sim = emb.similarity(emb)
    assert abs(sim - 1.0) < 1e-5

def test_similar_players_returns_results():
    space = EmbeddingSpace("data/test_embeddings_tmp.json")
    space.seed_with_defaults(20)
    results = space.find_similar("player_000", top_k=3, exclude_same_season=False)
    assert len(results) == 3

def test_lineup_chemistry_keys():
    space = EmbeddingSpace("data/test_embeddings_tmp.json")
    space.seed_with_defaults(10)
    ids = [f"player_00{i}" for i in range(5)]
    result = space.compute_lineup_chemistry(ids)
    assert "synergy_score" in result
    assert "redundancy_score" in result

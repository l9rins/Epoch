import torch
import torch.nn.functional as F

try:
    from torch_geometric.nn import SAGEConv, Linear, to_hetero
    import torch_geometric.transforms as T
except ImportError:
    # Dummy classes for environments without torch_geometric
    class SAGEConv: pass
    class Linear: pass
    def to_hetero(model, metadata, aggr): return model

class GraphSAGE(torch.nn.Module):
    def __init__(self, hidden_channels: int, out_channels: int):
        super().__init__()
        # 2-layer GraphSAGE
        # SAGEConv aggregates neighbor features (mean/pool) and concatenates with target node
        self.conv1 = SAGEConv((-1, -1), hidden_channels)
        self.conv2 = SAGEConv((-1, -1), hidden_channels)
        
        # Final classification head
        self.lin = Linear(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        # Layer 1: message passing + ReLU + dropout
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = F.dropout(x, p=0.4, training=self.training)
        
        # Layer 2: message passing + ReLU
        x = self.conv2(x, edge_index)
        x = F.relu(x)
        
        # Output layer for node embedding/prediction
        return self.lin(x)

def build_hetero_model(metadata, hidden_channels: int = 64, out_channels: int = 2):
    """
    Wraps the homogeneous GraphSAGE model into a Heterogeneous GNN 
    capable of handling multiple node and edge types dynamically based on the graph metadata.
    """
    model = GraphSAGE(hidden_channels=hidden_channels, out_channels=out_channels)
    
    # to_hetero converts the base model to handle distinct message passing 
    # per edge type (e.g., PLAYS_FOR, OFFICIATED_BY)
    model = to_hetero(model, metadata, aggr='sum')
    return model

def create_prediction_edge(home_team_id: str, away_team_id: str, ref_id: str = None, arena_id: str = None):
    """
    Creates a GAME node and connects it to both teams (and optionally referee/arena).
    Returns a populated KnowledgeGraphBuilder instance ready for GNN inference.
    """
    from src.graph.builder import KnowledgeGraphBuilder
    from src.graph.schema import GraphNode, GraphEdge, NodeType, EdgeType

    builder = KnowledgeGraphBuilder()
    builder.build_poc_graph()

    game_id = f"game_{home_team_id}_vs_{away_team_id}"

    builder.add_node(GraphNode(
        id=game_id,
        type=NodeType.GAME,
        features=[0.5, 0.5, 0.0],
        metadata={"home": home_team_id, "away": away_team_id}
    ))

    # Connect teams to game node
    if builder.graph.has_node(home_team_id):
        builder.add_edge(GraphEdge(
            source_id=home_team_id,
            target_id=game_id,
            type=EdgeType.MATCHUP,
            weight=1.0
        ))
    if builder.graph.has_node(away_team_id):
        builder.add_edge(GraphEdge(
            source_id=away_team_id,
            target_id=game_id,
            type=EdgeType.MATCHUP,
            weight=1.0
        ))

    # Optionally connect referee
    if ref_id and builder.graph.has_node(ref_id):
        builder.add_edge(GraphEdge(
            source_id=ref_id,
            target_id=game_id,
            type=EdgeType.OFFICIATED_BY,
            weight=1.0
        ))

    # Optionally connect arena
    if arena_id and builder.graph.has_node(arena_id):
        builder.add_edge(GraphEdge(
            source_id=arena_id,
            target_id=game_id,
            type=EdgeType.PLAYS_AT,
            weight=1.0
        ))

    return builder

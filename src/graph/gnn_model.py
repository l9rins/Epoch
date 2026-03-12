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

def create_prediction_edge(home_team_id: str, away_team_id: str, ref_id: str, arena_id: str):
    """Creates a temporary MATCHUP edge for predicting a specific future game."""
    # This logic would dynamically attach a new GAME node to the two TEAM nodes,
    # run a forward pass on the GNN, and read the GAME node's predicted embedding.
    pass

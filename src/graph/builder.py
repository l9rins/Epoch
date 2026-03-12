import networkx as nx
from typing import List, Dict, Tuple
from .schema import GraphNode, GraphEdge, NodeType, EdgeType

class KnowledgeGraphBuilder:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        
    def add_node(self, node: GraphNode):
        self.graph.add_node(
            node.id, 
            type=node.type.value,
            features=node.features,
            **node.metadata
        )
        
    def add_edge(self, edge: GraphEdge):
        if not self.graph.has_node(edge.source_id):
            raise ValueError(f"Source node {edge.source_id} not in graph")
        if not self.graph.has_node(edge.target_id):
            raise ValueError(f"Target node {edge.target_id} not in graph")
            
        self.graph.add_edge(
            edge.source_id, 
            edge.target_id, 
            type=edge.type.value,
            weight=edge.weight,
            **edge.attributes
        )
        
    def get_pyg_data(self):
        """Converts the NetworkX graph into a PyTorch Geometric HeteroData object."""
        try:
            from torch_geometric.utils import from_networkx
            import torch
        except ImportError:
            raise ImportError("Please install torch and torch_geometric")
            
        # This is a simplified conversion for POC. 
        # A full implementation would separate by edge type for HeteroData.
        pyg_graph = from_networkx(self.graph)
        return pyg_graph
        
    def build_poc_graph(self):
        """Builds a small proof-of-concept graph for testing."""
        # Teams
        self.add_node(GraphNode("team_gsw", NodeType.TEAM, [0.65, 102.3, 115.4], {"name": "Warriors"}))
        self.add_node(GraphNode("team_lal", NodeType.TEAM, [0.55, 98.7, 110.2], {"name": "Lakers"}))
        
        # Players
        self.add_node(GraphNode("player_curry", NodeType.PLAYER, [0.99, 0.95, 0.88], {"name": "Stephen Curry"}))
        self.add_node(GraphNode("player_lebron", NodeType.PLAYER, [0.95, 0.90, 0.99], {"name": "LeBron James"}))
        
        # Referees / Arenas
        self.add_node(GraphNode("ref_foster", NodeType.REFEREE, [0.6, 0.4], {"name": "Scott Foster"}))
        self.add_node(GraphNode("arena_chase", NodeType.ARENA, [1.0, 0.9], {"name": "Chase Center"}))
        
        # Edges
        self.add_edge(GraphEdge("player_curry", "team_gsw", EdgeType.PLAYS_FOR, 1.0))
        self.add_edge(GraphEdge("player_lebron", "team_lal", EdgeType.PLAYS_FOR, 1.0))
        self.add_edge(GraphEdge("team_gsw", "arena_chase", EdgeType.PLAYS_AT, 1.0))
        self.add_edge(GraphEdge("team_lal", "arena_chase", EdgeType.PLAYS_AT, 1.0)) # Playing away
        self.add_edge(GraphEdge("ref_foster", "team_gsw", EdgeType.OFFICIATED_BY, -0.2)) # Negative bias

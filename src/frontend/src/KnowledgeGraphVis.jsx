import { useRef } from 'react';
import { Network } from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';

export default function KnowledgeGraphVis({ graphData }) {
  const graphRef = useRef(null);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg flex-1 flex flex-col overflow-hidden relative min-h-[500px]">
      <div className="absolute top-4 left-4 z-10 pointer-events-none">
        <h3 className="text-lg font-semibold text-slate-200 flex items-center gap-2">
          <Network className="w-5 h-5 text-blue-400" /> Relational Knowledge Graph
        </h3>
        <p className="text-xs text-slate-400 mt-1 max-w-sm">
          System B visualizer. Live topological embeddings feeding the GraphSAGE model. 
          Node color = entity type. Link = relationship constraint.
        </p>
      </div>
      
      <div className="flex-1 -mx-5 -mb-5 mt-8 bg-slate-950 rounded-b-xl overflow-hidden border-t border-slate-800">
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          nodeAutoColorBy="group"
          nodeCanvasObject={(node, ctx, globalScale) => {
            const label = node.name;
            const fontSize = 12/globalScale;
            ctx.font = `${fontSize}px Sans-Serif`;
            const textWidth = ctx.measureText(label).width;
            const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); 

            ctx.fillStyle = 'rgba(15, 23, 42, 0.8)';
            ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);

            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = node.color;
            ctx.fillText(label, node.x, node.y);

            node.__bckgDimensions = bckgDimensions; 
          }}
          nodePointerAreaPaint={(node, color, ctx) => {
            ctx.fillStyle = color;
            const bckgDimensions = node.__bckgDimensions;
            bckgDimensions && ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions);
          }}
          linkColor={() => '#334155'}
          linkDirectionalParticles={1}
          linkDirectionalParticleWidth={1.5}
          linkDirectionalParticleSpeed={0.01}
        />
      </div>
    </div>
  );
}

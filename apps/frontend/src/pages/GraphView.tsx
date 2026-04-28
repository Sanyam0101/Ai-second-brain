import { useState, useEffect, useCallback, useMemo } from 'react'
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    MarkerType,
    BackgroundVariant,
    Handle,
    Position,
    addEdge,
    Connection,
    Node,
    EdgeProps,
    getBezierPath,
    BaseEdge,
    EdgeLabelRenderer
} from 'reactflow'
import 'reactflow/dist/style.css'
import api from '../services/api'
import { Network, RefreshCw, X, Calendar, Tag, FileText, ExternalLink, Maximize2, Share2 } from 'lucide-react'
import * as d3 from 'd3-force'

/* ── Constants & Helpers ──────────────────────────── */
const COLORS = [
    '#f43f5e', '#ec4899', '#d946ef', '#a855f7', '#8b5cf6', 
    '#6366f1', '#3b82f6', '#0ea5e9', '#06b6d4', '#14b8a6', 
    '#10b981', '#22c55e', '#84cc16', '#eab308', '#f59e0b'
];

const getColor = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return COLORS[Math.abs(hash) % COLORS.length];
};

/* ── Custom Edge with Label ────────────────────────── */
function CustomEdge({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    markerEnd,
    data,
}: EdgeProps) {
    const [edgePath, labelX, labelY] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    });

    return (
        <>
            <BaseEdge path={edgePath} markerEnd={markerEnd} style={style} />
            <EdgeLabelRenderer>
                <div
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                        fontSize: 9,
                        background: 'rgba(15, 23, 42, 0.8)',
                        padding: '1px 5px',
                        borderRadius: 4,
                        color: '#94a3b8',
                        fontWeight: 700,
                        pointerEvents: 'none',
                        border: '1px solid rgba(51, 65, 85, 0.5)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                    }}
                    className="nodrag nopan backdrop-blur-sm"
                >
                    {data?.label || ''}
                </div>
            </EdgeLabelRenderer>
        </>
    );
}

/* ── Custom Node Components ─────────────────────────── */
const CircleNode = ({ data, selected, type }: any) => {
    const isIdea = type === 'idea';
    const baseColor = isIdea ? '#8b5cf6' : getColor(data.label);
    const glowColor = `${baseColor}66`; // 40% opacity hex

    return (
        <div className="relative flex flex-col items-center">
            {/* Outer Glow Ring */}
            <div 
                style={{
                    position: 'absolute',
                    width: isIdea ? 64 : 52,
                    height: isIdea ? 64 : 52,
                    borderRadius: '50%',
                    background: selected ? glowColor : 'transparent',
                    filter: 'blur(8px)',
                    transition: 'all 0.3s ease',
                    zIndex: 0
                }}
            />
            
            {/* Node Circle */}
            <div 
                style={{
                    width: isIdea ? 48 : 38,
                    height: isIdea ? 48 : 38,
                    background: selected ? baseColor : '#1e293b',
                    border: `3px solid ${baseColor}`,
                    boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
                    transition: 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                    zIndex: 10
                }}
                className="rounded-full flex items-center justify-center cursor-pointer hover:scale-110 active:scale-95"
            >
                <Handle type="target" position={Position.Top} className="opacity-0" />
                {isIdea ? (
                    <FileText className={`w-5 h-5 ${selected ? 'text-white' : 'text-purple-400'}`} />
                ) : (
                    <Tag className={`w-4 h-4 ${selected ? 'text-white' : ''}`} style={{ color: selected ? 'white' : baseColor }} />
                )}
                <Handle type="source" position={Position.Bottom} className="opacity-0" />
            </div>
            
            {/* Label Below Node */}
            <div className="mt-2 text-center pointer-events-none" style={{ maxWidth: '140px' }}>
                <div className={`text-[11px] font-black tracking-tight px-2 py-0.5 rounded-lg transition-all ${selected ? 'bg-white text-gray-900 shadow-xl scale-110' : 'text-gray-100 drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]'}`}>
                    {data.title}
                </div>
                <div className={`text-[8px] font-black uppercase tracking-[0.3em] mt-1 transition-colors ${selected ? 'text-white opacity-100' : 'text-gray-500 opacity-60'}`}>
                    {type}
                </div>
            </div>
        </div>
    );
};

function IdeaNodeComponent(props: any) { return <CircleNode {...props} type="idea" />; }
function TagNodeComponent(props: any) { return <CircleNode {...props} type="tag" />; }

/* ── D3 Force Layout ────────────────────────────────── */
function runD3Layout(nodes: any[], edges: any[]) {
    const d3Nodes = nodes.map(n => ({ ...n }));
    const d3Links = edges.map(e => ({ source: e.s, target: e.t }));

    const simulation = d3.forceSimulation(d3Nodes as any)
        .force("link", d3.forceLink(d3Links).id((d: any) => d.id).distance(150))
        .force("charge", d3.forceManyBody().strength(-800))
        .force("center", d3.forceCenter(1000, 750))
        .force("collision", d3.forceCollide().radius(100))
        .force("x", d3.forceX(1000).strength(0.1))
        .force("y", d3.forceY(750).strength(0.1))
        .stop();

    // Run simulation for enough iterations to stabilize
    for (let i = 0; i < 300; i++) simulation.tick();

    return Object.fromEntries(d3Nodes.map((n: any) => [n.id, { x: n.x, y: n.y }]));
}

/* ── Main Component ────────────────────────────────── */
export default function GraphView() {
    const [nodes, setNodes, onNodesChange] = useNodesState([])
    const [edges, setEdges, onEdgesChange] = useEdgesState([])
    const [loading, setLoading] = useState(true)
    const [stats, setStats] = useState({ ideas: 0, tags: 0, edges: 0 })
    const [selectedNode, setSelectedNode] = useState<any>(null)

    const nodeTypes = useMemo(() => ({
        idea: IdeaNodeComponent,
        tag: TagNodeComponent,
    }), [])

    const edgeTypes = useMemo(() => ({
        custom: CustomEdge,
    }), [])

    const fetchGraph = useCallback(async () => {
        setLoading(true)
        try {
            const res = await api.get('/graph/all')
            const rawN = res.data.nodes || []
            const rawE = res.data.edges || []

            const nds = rawN.map((n: any) => ({
                id: String(n.internal_id),
                t: n.label === 'Idea' ? 'idea' : 'tag',
                title: n.title || n.label || '?',
                data: n
            }))
            const eds = rawE.map((e: any) => ({ 
                s: String(e.source), 
                t: String(e.target), 
                type: e.type 
            }))
            
            const positions = runD3Layout(nds, eds)

            setNodes(nds.map((n: any) => ({
                id: n.id,
                type: n.t,
                position: positions[n.id] || { x: 1000, y: 750 },
                draggable: true,
                data: { label: n.title, ...n.data },
            })))

            setEdges(eds.map((e: any, i: number) => ({
                id: `e${i}`,
                source: e.s,
                target: e.t,
                type: 'custom',
                data: { label: e.type },
                animated: false,
                style: { stroke: '#475569', strokeWidth: 2, opacity: 0.5 },
                markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#475569' },
            })))

            setStats({
                ideas: rawN.filter((n: any) => n.label === 'Idea').length,
                tags: rawN.filter((n: any) => n.label === 'Tag').length,
                edges: rawE.length,
            })
        } catch (err) {
            console.error('Fetch error:', err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => { fetchGraph() }, [fetchGraph])

    const onNodeClick = (_: any, node: Node) => {
        setSelectedNode(node.data)
    }

    const onPaneClick = () => {
        setSelectedNode(null)
    }

    const onConnect = useCallback(async (params: Connection | any) => {
        if (!params.source || !params.target) return
        
        const newEdge = {
            id: `e-${params.source}-${params.target}-${Date.now()}`,
            source: params.source,
            target: params.target,
            type: 'custom',
            data: { label: 'LINKED_TO' },
            style: { stroke: '#8b5cf6', strokeWidth: 3 },
            markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#8b5cf6' },
        }
        setEdges((eds) => addEdge(newEdge, eds))
        
        try {
            await api.post('/graph/link', { src_id: params.source, dst_id: params.target })
            setStats(s => ({...s, edges: s.edges + 1}))
        } catch (err) {
            setEdges((eds) => eds.filter(e => e.id !== newEdge.id))
        }
    }, [setEdges])

    return (
        <div className="flex flex-col h-[calc(100vh-5rem)] gap-4 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-lg shadow-purple-500/20" style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' }}>
                        <Network className="w-6 h-6 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-black text-gray-900 dark:text-white tracking-tight">KNOWLEDGE GRAPH</h1>
                        <div className="flex items-center gap-2 mt-0.5">
                            <span className="px-2 py-0.5 rounded-lg bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 text-[10px] font-black uppercase tracking-wider">{stats.ideas} IDEAS</span>
                            <span className="px-2 py-0.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 text-[10px] font-black uppercase tracking-wider">{stats.tags} TAGS</span>
                            <span className="px-2 py-0.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-[10px] font-black uppercase tracking-wider">{stats.edges} LINKS</span>
                        </div>
                    </div>
                </div>
                <button onClick={fetchGraph}
                    className="px-4 py-2 rounded-xl text-sm font-bold bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 hover:border-purple-500 dark:hover:border-purple-500 hover:text-purple-600 transition-all flex items-center gap-2 shadow-sm">
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> RELOAD
                </button>
            </div>

            {/* Main Area */}
            <div className="flex-1 flex gap-4 overflow-hidden relative">
                {/* Graph Container */}
                <div className="flex-1 rounded-3xl overflow-hidden relative border border-gray-200 dark:border-gray-800 shadow-2xl bg-[#0c1222]">
                    <style>{`
                        .react-flow__node { background: transparent !important; border: none !important; box-shadow: none !important; padding: 0 !important; }
                        .react-flow__controls { background: #1e293b !important; border: 1px solid #334155 !important; border-radius: 12px !important; padding: 4px !important; overflow: hidden; }
                        .react-flow__controls button { background: transparent !important; color: #94a3b8 !important; border: none !important; width: 32px !important; height: 32px !important; margin: 0 !important; }
                        .react-flow__controls button:hover { background: #334155 !important; color: #fff !important; }
                        .react-flow__controls button svg { fill: currentColor !important; }
                        .react-flow__minimap { background: #111827 !important; border-radius: 16px !important; border: 1px solid #374151 !important; margin: 16px !important; overflow: hidden; }
                    `}</style>
                    
                    {loading ? (
                        <div className="absolute inset-0 flex flex-col items-center justify-center z-10 bg-[#0c1222]/80 backdrop-blur-md">
                            <div className="w-16 h-16 rounded-full animate-spin border-4 border-gray-800 border-t-purple-600" />
                            <p className="mt-4 text-sm font-black text-white uppercase tracking-widest animate-pulse">Initializing Neural Map...</p>
                        </div>
                    ) : nodes.length === 0 ? (
                        <div className="absolute inset-0 flex flex-col items-center justify-center z-10">
                            <Network className="w-16 h-16 text-gray-800 mb-4" />
                            <p className="text-lg font-bold text-gray-400">Empty Brain Space</p>
                            <p className="text-sm text-gray-500">Connect ideas to build your knowledge map</p>
                        </div>
                    ) : (
                        <ReactFlow
                            nodes={nodes}
                            edges={edges}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            onConnect={onConnect}
                            onNodeClick={onNodeClick}
                            onPaneClick={onPaneClick}
                            nodeTypes={nodeTypes}
                            edgeTypes={edgeTypes}
                            fitView
                            fitViewOptions={{ padding: 0.3, maxZoom: 1.2 }}
                            minZoom={0.05}
                            maxZoom={2}
                            proOptions={{ hideAttribution: true }}
                        >
                            <Background variant={BackgroundVariant.Dots} gap={30} size={1} color="#1e293b" />
                            <Controls showInteractive={false} position="bottom-left" />
                            <MiniMap
                                nodeColor={(n: any) => n.type === 'tag' ? getColor(n.data.label) : '#8b5cf6'}
                                maskColor="rgba(0,0,0,0.8)"
                                zoomable pannable
                            />
                        </ReactFlow>
                    )}
                </div>

                {/* Detail Panel */}
                <div className={`w-80 flex flex-col gap-4 transition-all duration-300 absolute lg:relative right-0 top-0 h-full z-50 lg:z-auto ${selectedNode ? 'translate-x-0' : 'translate-x-[calc(100%+2rem)] lg:translate-x-0 lg:opacity-0 lg:pointer-events-none'}`}>
                    <div className="flex-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-3xl overflow-hidden flex flex-col shadow-2xl">
                        {selectedNode ? (
                            <>
                                <div className="p-6 text-white relative overflow-hidden" style={{ background: selectedNode.label === 'Idea' ? '#8b5cf6' : getColor(selectedNode.title) }}>
                                    <div className="absolute top-0 right-0 p-8 opacity-10 transform translate-x-4 -translate-y-4">
                                        {selectedNode.label === 'Idea' ? <FileText className="w-24 h-24" /> : <Tag className="w-24 h-24" />}
                                    </div>
                                    <button onClick={() => setSelectedNode(null)} className="absolute top-4 right-4 p-1 rounded-lg hover:bg-black/20 transition-colors z-10">
                                        <X className="w-4 h-4" />
                                    </button>
                                    <div className="flex items-center gap-2 mb-3 relative z-10">
                                        {selectedNode.label === 'Idea' ? <FileText className="w-4 h-4" /> : <Tag className="w-4 h-4" />}
                                        <span className="text-[10px] font-black uppercase tracking-widest opacity-80">{selectedNode.label}</span>
                                    </div>
                                    <h2 className="text-xl font-black leading-tight mb-2 line-clamp-4 relative z-10">{selectedNode.title}</h2>
                                    {selectedNode.created_at && (
                                        <div className="flex items-center gap-2 text-xs opacity-80 font-medium relative z-10">
                                            <Calendar className="w-3.5 h-3.5" />
                                            {new Date(selectedNode.created_at).toLocaleDateString()}
                                        </div>
                                    )}
                                </div>
                                
                                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                                    {selectedNode.content && (
                                        <div>
                                            <h3 className="text-[10px] font-black text-gray-400 dark:text-gray-500 uppercase tracking-widest mb-3">Memory Content</h3>
                                            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
                                                {selectedNode.content}
                                            </p>
                                        </div>
                                    )}

                                    <div className="flex flex-wrap gap-2 pt-4">
                                        <button className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-xs font-bold hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
                                            <ExternalLink className="w-3.5 h-3.5" /> OPEN FULL NOTE
                                        </button>
                                        <button className="p-3 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
                                            <Share2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-gray-50/50 dark:bg-gray-800/20">
                                <Maximize2 className="w-12 h-12 text-gray-300 dark:text-gray-700 mb-4 animate-pulse" />
                                <p className="text-sm font-black text-gray-400 dark:text-gray-600 uppercase tracking-widest">Select Memory</p>
                                <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 max-w-[180px]">Expand individual nodes to traverse your deep neural connections</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

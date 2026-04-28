import { useState, useEffect } from 'react'
import { Plus, Github, FileText, BookOpen, MessageSquare, ArrowRight, Check, Loader2, X, ExternalLink, Download, Trash2, RefreshCw, AlertCircle, Link2, Clock, Zap, ChevronDown, ChevronUp } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'

interface IntegrationData {
    id: string; platform: string; last_synced: string | null; connected: boolean
}

/* ── Toast notification ── */
function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error' | 'info'; onClose: () => void }) {
    useEffect(() => { const t = setTimeout(onClose, 4000); return () => clearTimeout(t) }, [onClose])
    const colors = {
        success: 'bg-emerald-600 text-white',
        error: 'bg-red-600 text-white',
        info: 'bg-blue-600 text-white',
    }
    return (
        <div className={`fixed top-6 right-6 z-[100] px-5 py-3 rounded-xl shadow-2xl text-sm font-medium flex items-center gap-2 animate-slide-in ${colors[type]}`}>
            {type === 'success' && <Check className="w-4 h-4" />}
            {type === 'error' && <AlertCircle className="w-4 h-4" />}
            {type === 'info' && <Zap className="w-4 h-4" />}
            {message}
            <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100"><X className="w-3.5 h-3.5" /></button>
        </div>
    )
}

/* ── Source definitions ── */
const SOURCES = [
    {
        id: 'github', name: 'GitHub', icon: Github, color: '#6e40c9',
        desc: 'Import repos, READMEs, and gists',
        hint: 'Paste a repo URL — we\'ll grab the README and metadata',
        placeholder: 'https://github.com/username/repo',
        gradient: 'from-violet-600 to-purple-800',
        bgGlow: 'group-hover:shadow-violet-500/20',
        features: ['Auto-fetches README content', 'Extracts repo metadata & stars', 'Supports personal access tokens'],
        urlPattern: /^https?:\/\/github\.com\//,
        urlError: 'Must be a GitHub URL (https://github.com/...)',
    },
    {
        id: 'gdrive', name: 'Google Drive', icon: FileText, color: '#0F9D58',
        desc: 'Import docs, sheets, and PDFs',
        hint: 'Paste a shareable Google Drive or Docs link',
        placeholder: 'https://docs.google.com/document/d/...',
        gradient: 'from-emerald-500 to-green-700',
        bgGlow: 'group-hover:shadow-emerald-500/20',
        features: ['Imports Google Docs text content', 'Supports shared Drive links', 'Saves file reference for PDFs/Sheets'],
        urlPattern: /^https?:\/\/(docs|drive)\.google\.com\//,
        urlError: 'Must be a Google Drive or Docs URL',
    },
    {
        id: 'notion', name: 'Notion', icon: BookOpen, color: '#000000',
        desc: 'Import pages and databases',
        hint: 'Paste a public Notion page URL',
        placeholder: 'https://notion.so/page-name-...',
        gradient: 'from-gray-600 to-gray-900',
        bgGlow: 'group-hover:shadow-gray-500/20',
        features: ['Extracts public page text', 'Saves page title & content', 'Supports notion.so and notion.site links'],
        urlPattern: /^https?:\/\/(www\.)?notion\.(so|site)\//,
        urlError: 'Must be a Notion URL (https://notion.so/...)',
    },
    {
        id: 'slack', name: 'Slack', icon: MessageSquare, color: '#4A154B',
        desc: 'Import conversations and threads',
        hint: 'Paste a Slack webhook URL or bot token',
        placeholder: 'xoxb-your-bot-token or webhook URL',
        gradient: 'from-purple-600 to-fuchsia-800',
        bgGlow: 'group-hover:shadow-purple-500/20',
        features: ['Saves reference with token', 'Placeholder — full extraction coming soon', 'Bot token for channel access'],
        urlPattern: /./,
        urlError: '',
    },
    {
        id: 'web', name: 'Web Scraper', icon: ExternalLink, color: '#2563EB',
        desc: 'Scrape content from any public URL',
        hint: 'Paste any public website URL',
        placeholder: 'https://example.com/article',
        gradient: 'from-blue-500 to-indigo-700',
        bgGlow: 'group-hover:shadow-blue-500/20',
        features: ['Extracts readable text', 'Removes scripts and styling', 'Supports HTTP/HTTPS'],
        urlPattern: /^https?:\/\//,
        urlError: 'Must be a valid HTTP or HTTPS URL',
    },
]

export default function Integrations() {
    const queryClient = useQueryClient()
    const [activeSource, setActiveSource] = useState<string | null>(null)
    const [url, setUrl] = useState('')
    const [importStep, setImportStep] = useState<'input' | 'importing' | 'done'>('input')
    const [importResult, setImportResult] = useState<{ notes: number; message: string } | null>(null)
    const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'info' } | null>(null)
    const [expandedSource, setExpandedSource] = useState<string | null>(null)
    const [urlValid, setUrlValid] = useState<boolean | null>(null)

    const { data: integrations = [] } = useQuery<IntegrationData[]>({
        queryKey: ['integrations'],
        queryFn: async () => (await api.get('/integrations/')).data
    })

    /* ── URL validation ── */
    useEffect(() => {
        if (!url.trim() || !activeSource) { setUrlValid(null); return }
        const src = SOURCES.find(s => s.id === activeSource)
        if (!src) return
        setUrlValid(src.urlPattern.test(url.trim()))
    }, [url, activeSource])

    /* ── Mutations ── */
    const connectMutation = useMutation({
        mutationFn: async (data: { platform: string; access_token: string }) =>
            (await api.post('/integrations/connect', data)).data,
        onSuccess: (data) => {
            setImportStep('done')
            setImportResult({ notes: data?.synced_notes || 0, message: `Successfully imported from ${activeSource}` })
            queryClient.invalidateQueries({ queryKey: ['integrations'] })
            queryClient.invalidateQueries({ queryKey: ['notes'] })
            queryClient.invalidateQueries({ queryKey: ['dashboard'] })
        },
        onError: (err: any) => {
            setImportStep('input')
            setToast({ msg: err?.response?.data?.detail || 'Import failed. Check your link and try again.', type: 'error' })
        }
    })

    const disconnectMutation = useMutation({
        mutationFn: async (platform: string) => { await api.delete(`/integrations/${platform}`) },
        onSuccess: (_data, platform) => {
            queryClient.invalidateQueries({ queryKey: ['integrations'] })
            setToast({ msg: `Disconnected ${SOURCES.find(s => s.id === platform)?.name || platform}`, type: 'info' })
        }
    })

    const syncMutation = useMutation({
        mutationFn: async (platform: string) => (await api.post(`/integrations/${platform}/sync`)).data,
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['integrations'] })
            queryClient.invalidateQueries({ queryKey: ['notes'] })
            setToast({ msg: data.message, type: 'success' })
        },
        onError: () => setToast({ msg: 'Sync failed. Try again.', type: 'error' })
    })

    const handleImport = () => {
        if (!url.trim() || !activeSource) return
        setImportStep('importing')
        connectMutation.mutate({ platform: activeSource, access_token: url.trim() })
    }

    const closeModal = () => {
        setActiveSource(null); setUrl(''); setImportStep('input'); setImportResult(null); setUrlValid(null)
    }

    const connectedPlatforms = integrations.map(i => i.platform)
    const source = SOURCES.find(s => s.id === activeSource)

    return (
        <div className="max-w-5xl mx-auto space-y-8">
            {/* Toast */}
            {toast && <Toast message={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

            {/* Inline CSS for animations */}
            <style>{`
                @keyframes slide-in { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
                .animate-slide-in { animation: slide-in 0.3s ease-out; }
                @keyframes modal-up { from { transform: translateY(40px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
                .animate-modal-up { animation: modal-up 0.25s ease-out; }
                @keyframes pulse-ring { 0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); } 70% { box-shadow: 0 0 0 6px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
                .pulse-ring { animation: pulse-ring 2s infinite; }
                @keyframes shimmer { from { background-position: -200% 0; } to { background-position: 200% 0; } }
                .shimmer-btn { background-size: 200% 100%; animation: shimmer 2s linear infinite; }
            `}</style>

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-gradient-to-br from-violet-500 to-purple-600 rounded-xl shadow-lg">
                            <Link2 className="w-6 h-6 text-white" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Integrations</h1>
                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                Connect external sources to enrich your knowledge base
                            </p>
                        </div>
                    </div>
                </div>
                {integrations.length > 0 && (
                    <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 pulse-ring" />
                        <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                            {integrations.length} source{integrations.length > 1 ? 's' : ''} connected
                        </span>
                    </div>
                )}
            </div>

            {/* Source Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                {SOURCES.map(src => {
                    const isConnected = connectedPlatforms.includes(src.id)
                    const integration = integrations.find(i => i.platform === src.id)
                    const Icon = src.icon
                    const isExpanded = expandedSource === src.id

                    return (
                        <div key={src.id}
                            className={`group relative rounded-2xl border transition-all duration-300 overflow-hidden
                                bg-white dark:bg-gray-900/80 backdrop-blur-sm
                                ${isConnected
                                    ? 'border-emerald-500/50 dark:border-emerald-600/50 shadow-lg shadow-emerald-500/5'
                                    : 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}
                                hover:shadow-xl ${src.bgGlow}
                            `}
                        >
                            {/* Connected indicator bar */}
                            {isConnected && (
                                <div className={`h-1 w-full bg-gradient-to-r ${src.gradient}`} />
                            )}

                            <div className="p-5">
                                {/* Card Header */}
                                <div className="flex items-start justify-between mb-4">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${src.gradient} flex items-center justify-center shadow-lg transition-transform group-hover:scale-105`}>
                                            <Icon className="w-5 h-5 text-white" />
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-gray-900 dark:text-white">{src.name}</h3>
                                            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{src.desc}</p>
                                        </div>
                                    </div>
                                    {isConnected && (
                                        <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                                            <Check className="w-3 h-3" /> Active
                                        </span>
                                    )}
                                </div>

                                {/* Sync info */}
                                {isConnected && integration?.last_synced && (
                                    <div className="flex items-center gap-1.5 mb-4 text-[11px] text-gray-400 dark:text-gray-500">
                                        <Clock className="w-3 h-3" />
                                        Last synced: {new Date(integration.last_synced).toLocaleString()}
                                    </div>
                                )}

                                {/* Features toggle */}
                                <button
                                    onClick={() => setExpandedSource(isExpanded ? null : src.id)}
                                    className="flex items-center gap-1 text-[11px] text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors mb-3"
                                >
                                    {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                    {isExpanded ? 'Hide' : 'Show'} capabilities
                                </button>

                                {isExpanded && (
                                    <div className="mb-4 space-y-1.5 animate-modal-up">
                                        {src.features.map((f, i) => (
                                            <div key={i} className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                                                <Check className="w-3 h-3 text-emerald-500 shrink-0" />
                                                {f}
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Action buttons */}
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => { setActiveSource(src.id); setUrl(''); setImportStep('input'); setImportResult(null); setUrlValid(null) }}
                                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${isConnected
                                                ? 'bg-emerald-50 dark:bg-emerald-600/10 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-600/20 border border-emerald-200 dark:border-emerald-800'
                                                : `bg-gradient-to-r ${src.gradient} text-white shadow-md hover:shadow-lg hover:brightness-110`
                                            }`}
                                    >
                                        {isConnected ? <><Download className="w-4 h-4" />Import More</> : <><Plus className="w-4 h-4" />Connect & Import</>}
                                    </button>
                                    {isConnected && (
                                        <>
                                            <button onClick={() => syncMutation.mutate(src.id)}
                                                disabled={syncMutation.isPending}
                                                className="px-3 py-2.5 rounded-xl text-sm font-medium border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-all disabled:opacity-40"
                                                title="Re-sync latest data"
                                            >
                                                <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                                            </button>
                                            <button onClick={() => { if (confirm(`Disconnect ${src.name}? Your imported notes will remain.`)) disconnectMutation.mutate(src.id) }}
                                                className="px-3 py-2.5 rounded-xl text-sm border border-red-200 dark:border-red-900/50 text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-all"
                                                title="Disconnect source"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    )
                })}
            </div>

            {/* ── Import Modal ── */}
            {activeSource && source && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    style={{ backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
                    onClick={e => e.target === e.currentTarget && closeModal()}
                >
                    <div className="w-full max-w-lg rounded-2xl overflow-hidden shadow-2xl bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 animate-modal-up">
                        {/* Modal Header */}
                        <div className={`bg-gradient-to-r ${source.gradient} p-6 flex items-center justify-between`}>
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                                    <source.icon className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h2 className="text-white font-bold text-lg">Import from {source.name}</h2>
                                    <p className="text-white/70 text-xs mt-0.5">{source.hint}</p>
                                </div>
                            </div>
                            <button onClick={closeModal} className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white/60 hover:text-white transition-all">
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div className="p-6">
                            {importStep === 'input' && (
                                <div className="space-y-5">
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2 uppercase tracking-wider">
                                            Paste your link or token
                                        </label>
                                        <div className="relative">
                                            <input
                                                type="text"
                                                value={url}
                                                onChange={e => setUrl(e.target.value)}
                                                placeholder={source.placeholder}
                                                className={`w-full px-4 py-3.5 rounded-xl border text-sm text-gray-900 dark:text-white bg-gray-50 dark:bg-gray-800 focus:outline-none focus:ring-2 transition-all pr-10
                                                    ${urlValid === false
                                                        ? 'border-red-300 dark:border-red-700 focus:ring-red-500/30 focus:border-red-500'
                                                        : urlValid === true
                                                            ? 'border-emerald-300 dark:border-emerald-700 focus:ring-emerald-500/30 focus:border-emerald-500'
                                                            : 'border-gray-200 dark:border-gray-700 focus:ring-purple-500/30 focus:border-purple-500'
                                                    }`}
                                                autoFocus
                                                onKeyDown={e => e.key === 'Enter' && urlValid !== false && handleImport()}
                                            />
                                            {url.trim() && (
                                                <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                                    {urlValid
                                                        ? <Check className="w-4 h-4 text-emerald-500" />
                                                        : urlValid === false
                                                            ? <AlertCircle className="w-4 h-4 text-red-400" />
                                                            : null
                                                    }
                                                </div>
                                            )}
                                        </div>
                                        {urlValid === false && source.urlError && (
                                            <p className="mt-1.5 text-xs text-red-500 flex items-center gap-1">
                                                <AlertCircle className="w-3 h-3" /> {source.urlError}
                                            </p>
                                        )}
                                    </div>

                                    {/* Preview hint */}
                                    {url.trim() && urlValid && (
                                        <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-purple-50 dark:bg-purple-900/15 border border-purple-100 dark:border-purple-800/50">
                                            <ExternalLink className="w-4 h-4 text-purple-500 shrink-0" />
                                            <span className="text-xs text-purple-700 dark:text-purple-300 truncate">
                                                Will import from: <strong>{url.length > 45 ? url.slice(0, 45) + '...' : url}</strong>
                                            </span>
                                        </div>
                                    )}

                                    {/* Features list */}
                                    <div className="flex flex-wrap gap-2">
                                        {source.features.map((f, i) => (
                                            <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                                                <Zap className="w-2.5 h-2.5 text-amber-500" /> {f}
                                            </span>
                                        ))}
                                    </div>

                                    <button onClick={handleImport} disabled={!url.trim() || urlValid === false}
                                        className={`w-full py-3.5 rounded-xl text-sm font-bold text-white flex items-center justify-center gap-2 transition-all disabled:opacity-30 disabled:cursor-not-allowed
                                            bg-gradient-to-r ${source.gradient} hover:shadow-lg hover:brightness-110 shadow-md`}
                                    >
                                        Import to Knowledge Base <ArrowRight className="w-4 h-4" />
                                    </button>
                                </div>
                            )}

                            {importStep === 'importing' && (
                                <div className="flex flex-col items-center py-10">
                                    <div className="relative">
                                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500/20 to-violet-500/20 dark:from-purple-500/10 dark:to-violet-500/10 flex items-center justify-center">
                                            <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                                        </div>
                                    </div>
                                    <p className="mt-4 text-base font-semibold text-gray-800 dark:text-white">Importing content...</p>
                                    <p className="text-xs text-gray-400 mt-1.5">Fetching and processing your data from {source.name}</p>
                                    <div className="w-48 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full mt-5 overflow-hidden">
                                        <div className="h-full bg-gradient-to-r from-purple-500 to-violet-500 rounded-full shimmer-btn" style={{ width: '70%' }} />
                                    </div>
                                </div>
                            )}

                            {importStep === 'done' && importResult && (
                                <div className="flex flex-col items-center py-8">
                                    <div className="w-16 h-16 rounded-2xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
                                        <Check className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
                                    </div>
                                    <p className="text-lg font-bold text-gray-900 dark:text-white">Import Complete!</p>
                                    <p className="text-sm text-gray-500 mt-2">
                                        Added <strong className="text-purple-600 dark:text-purple-400">{importResult.notes} item{importResult.notes !== 1 ? 's' : ''}</strong> to your knowledge base
                                    </p>
                                    <p className="text-xs text-gray-400 mt-1">
                                        Notes are now searchable via AI Analyst & Knowledge Graph
                                    </p>
                                    <div className="flex gap-3 mt-6 w-full">
                                        <button onClick={closeModal}
                                            className="flex-1 py-2.5 rounded-xl text-sm font-medium border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-all">
                                            Done
                                        </button>
                                        <button onClick={() => { setUrl(''); setImportStep('input'); setImportResult(null); setUrlValid(null) }}
                                            className={`flex-1 py-2.5 rounded-xl text-sm font-bold text-white transition-all bg-gradient-to-r ${source.gradient} hover:brightness-110`}>
                                            Import Another
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Connected Sources Summary */}
            {integrations.length > 0 && (
                <div className="rounded-2xl border border-gray-200 dark:border-gray-800 overflow-hidden bg-white dark:bg-gray-900/80 backdrop-blur-sm shadow-sm">
                    <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Zap className="w-4 h-4 text-amber-500" />
                            <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200">Connected Sources</h3>
                        </div>
                        <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
                            {integrations.length} active
                        </span>
                    </div>
                    <div className="divide-y divide-gray-100 dark:divide-gray-800">
                        {integrations.map(i => {
                            const src = SOURCES.find(s => s.id === i.platform)
                            if (!src) return null
                            const Icon = src.icon
                            return (
                                <div key={i.id} className="flex items-center justify-between px-5 py-3.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${src.gradient} flex items-center justify-center shadow-sm`}>
                                            <Icon className="w-4 h-4 text-white" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-semibold text-gray-900 dark:text-white">{src.name}</p>
                                            <p className="text-[10px] text-gray-400 dark:text-gray-500 flex items-center gap-1">
                                                <Clock className="w-2.5 h-2.5" />
                                                {i.last_synced ? `Last synced ${new Date(i.last_synced).toLocaleString()}` : 'Never synced'}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <button onClick={() => syncMutation.mutate(src.id)}
                                            disabled={syncMutation.isPending}
                                            className="text-xs text-purple-600 dark:text-purple-400 hover:text-purple-700 font-medium flex items-center gap-1 transition-colors disabled:opacity-40"
                                        >
                                            <RefreshCw className={`w-3 h-3 ${syncMutation.isPending ? 'animate-spin' : ''}`} /> Sync
                                        </button>
                                        <div className="flex items-center gap-1.5">
                                            <span className="w-2 h-2 rounded-full bg-emerald-500 pulse-ring" />
                                            <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Active</span>
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            {/* Empty state */}
            {integrations.length === 0 && (
                <div className="text-center py-10">
                    <div className="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center mx-auto mb-4">
                        <Link2 className="w-8 h-8 text-gray-400" />
                    </div>
                    <p className="text-sm font-semibold text-gray-600 dark:text-gray-400">No sources connected yet</p>
                    <p className="text-xs text-gray-400 mt-1">Click any card above to start importing knowledge</p>
                </div>
            )}
        </div>
    )
}

import { Note } from '../services/notesService'
import { Trash2, Calendar, Lightbulb, Upload, FileText, Github, BookOpen } from 'lucide-react'

interface NoteCardProps {
  note: Note
  onDelete: () => void
  onClick: () => void
}

/** Strip HTML tags, markdown images, markdown headers, bold/italic, and URLs */
function stripMarkup(text: string): string {
  return text
    .replace(/<[^>]+>/g, '')                    // HTML tags
    .replace(/!\[.*?\]\(.*?\)/g, '')            // markdown images
    .replace(/\[([^\]]+)\]\(.*?\)/g, '$1')      // markdown links → text only
    .replace(/#{1,6}\s*/g, '')                  // markdown headers
    .replace(/\*{1,3}([^*]+)\*{1,3}/g, '$1')   // bold/italic
    .replace(/https?:\/\/\S+/g, '')             // raw URLs
    .replace(/\s+/g, ' ')
    .trim()
}

/** Extract a clean, human-readable title from note content */
function extractTitle(content: string): string {
  // Remove emoji prefixes using unicode property escapes
  let text = content.replace(/^[\p{Emoji_Presentation}\p{Extended_Pictographic}]\s*/u, '')

  // Known patterns
  const patterns: [RegExp, string][] = [
    [/^GitHub Repo:\s*(.+?)(?:\n|$)/i, '$1'],
    [/^README from\s*(.+?)(?:\n|$)/i, '$1'],
    [/^Google (?:Drive|Doc)[:\s]*(.+?)(?:\n|$)/i, '$1'],
    [/^Connected to\s*(.+?)(?:\n|$)/i, '$1'],
    [/^DOCX file:\s*(.+?)(?:\n|$)/i, '$1'],
    [/^PDF file:\s*(.+?)(?:\n|$)/i, '$1'],
    [/^Notion[:\s]*(.+?)(?:\n|$)/i, '$1'],
  ]

  for (const [pattern] of patterns) {
    const match = text.match(pattern)
    if (match) {
      return stripMarkup(match[1]).slice(0, 80)
    }
  }

  // Fallback: first meaningful line, skipping generic markers
  const lines = text.split('\n')
    .map(l => l.trim())
    .filter(l => l.length > 3 && !/^\(imported\)$|^\(uploaded\)$/i.test(l))
  
  if (lines.length > 0) {
    const title = stripMarkup(lines[0]).slice(0, 80)
    if (title.length > 0) return title
  }

  return stripMarkup(text).slice(0, 60) || 'Untitled note'
}

/** Extract a short preview (2nd line onward, cleaned) */
function extractPreview(content: string, maxLen = 100): string {
  const lines = content.split('\n').filter(l => l.trim().length > 3)
  const bodyLines = lines.length > 1 ? lines.slice(1) : lines
  let body = bodyLines.join(' ')
  body = stripMarkup(body)
  if (body.length > maxLen) {
    body = body.slice(0, maxLen).replace(/\s\S*$/, '') + '…'
  }
  return body || ''
}

/** Detect note type icon */
function getNoteIcon(content: string, tags?: string[]) {
  if (tags?.includes('github') || /GitHub Repo|README from/i.test(content))
    return { icon: Github, color: 'text-purple-500 dark:text-purple-400' }
  if (tags?.includes('gdrive') || /Google (Drive|Doc)/i.test(content))
    return { icon: FileText, color: 'text-green-500 dark:text-green-400' }
  if (tags?.includes('notion') || /Notion/i.test(content))
    return { icon: BookOpen, color: 'text-gray-500 dark:text-gray-400' }
  return null
}

export default function NoteCard({ note, onDelete, onClick }: NoteCardProps) {
  const isIdea = note.tags?.includes('idea') || note.content?.startsWith('💡')
  const isUploaded = note.tags?.includes('uploaded')

  const title = extractTitle(note.content)
  const preview = extractPreview(note.content)
  const sourceIcon = getNoteIcon(note.content, note.tags)

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (confirm('Are you sure you want to delete this note?')) {
      onDelete()
    }
  }

  const gradientClass = isIdea
    ? 'from-amber-400/20 to-orange-500/20'
    : isUploaded
      ? 'from-blue-400/20 to-cyan-500/20'
      : 'from-primary-400/20 to-purple-500/20'

  const borderAccent = isIdea
    ? 'border-l-amber-400'
    : isUploaded
      ? 'border-l-blue-400'
      : 'border-l-transparent'

  return (
    <div
      className={`group relative bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm hover:shadow-2xl hover:-translate-y-1 transition-all duration-300 border border-gray-100 dark:border-gray-700 overflow-hidden cursor-pointer border-l-4 ${borderAccent}`}
      onClick={onClick}
    >
      <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-br ${gradientClass} rounded-full blur-3xl -mr-16 -mt-16 transition-opacity duration-500 opacity-50 group-hover:opacity-100`}></div>

      {/* Type Badge */}
      {(isIdea || isUploaded) && (
        <div className="flex items-center gap-1.5 mb-3 relative z-10">
          {isIdea ? (
            <span className="flex items-center gap-1 text-xs font-semibold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 px-2.5 py-1 rounded-full border border-amber-100 dark:border-amber-800">
              <Lightbulb className="w-3 h-3" /> Idea
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 px-2.5 py-1 rounded-full border border-blue-100 dark:border-blue-800">
              <Upload className="w-3 h-3" /> Uploaded
            </span>
          )}
        </div>
      )}

      {/* Title + Delete */}
      <div className="flex items-start justify-between mb-2 relative z-10">
        <div className="flex items-start gap-2 flex-1 min-w-0">
          {sourceIcon && (
            <sourceIcon.icon className={`w-4.5 h-4.5 mt-0.5 shrink-0 ${sourceIcon.color}`} />
          )}
          <h3 className="text-base font-semibold text-gray-800 dark:text-gray-100 line-clamp-2 leading-snug">
            {title}
          </h3>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            handleDelete(e)
          }}
          className="ml-3 p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-full transition-colors opacity-0 group-hover:opacity-100 shrink-0"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Preview text */}
      {preview && (
        <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mb-3 relative z-10 leading-relaxed">
          {preview}
        </p>
      )}

      {/* Tags */}
      {note.tags && note.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4 relative z-10">
          {note.tags.filter(t => t !== 'idea' && t !== 'uploaded').slice(0, 5).map((tag) => (
            <span
              key={tag}
              className="px-2.5 py-0.5 text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-full"
            >
              #{tag}
            </span>
          ))}
          {note.tags.length > 7 && (
            <span className="px-2 py-0.5 text-xs text-gray-400">+{note.tags.length - 5} more</span>
          )}
        </div>
      )}

      <div className="flex items-center text-xs text-gray-400 dark:text-gray-500 font-medium relative z-10 mt-auto pt-3 border-t border-gray-100 dark:border-gray-700/50">
        <Calendar className="w-3.5 h-3.5 mr-1.5" />
        {new Date(note.created_at).toLocaleDateString(undefined, {
          month: 'short',
          day: 'numeric',
          year: 'numeric'
        })}
        {note.similarity_score && (
          <span className="ml-auto inline-flex items-center px-2.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800/50 text-xs font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1.5 animate-pulse"></span>
            {(note.similarity_score * 100).toFixed(0)}% match
          </span>
        )}
      </div>
    </div>
  )
}

import DOMPurify from 'dompurify'
import { marked } from 'marked'

// Configure marked once at module scope.
// marked is only the Markdown parser — it does NOT sanitize HTML.
// DOMPurify is the required security gate before any HTML touches the DOM.
marked.use({ gfm: true, breaks: true })

// Belt-and-suspenders on top of DOMPurify defaults.
// ADD_ATTR allows DOMPurify to retain target/rel after the hook sets them;
// without it DOMPurify strips those attributes post-hook.
const PURIFY_CONFIG = {
  FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed'],
  ADD_ATTR:    ['target', 'rel'],
}

// Module-scoped hook — registered once, not inside the React component.
// Enforces target="_blank" and rel="noopener noreferrer" on every <a> tag
// that survives sanitization, preventing opener attacks.
DOMPurify.addHook('afterSanitizeAttributes', node => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

/**
 * Renders assistant Markdown content safely.
 *
 * Security contract:
 *   - marked.parse()  → raw HTML string (NOT sanitized)
 *   - DOMPurify.sanitize() → safeHtml (sanitized, links hardened by hook)
 *   - dangerouslySetInnerHTML receives ONLY safeHtml — never rawHtml directly.
 *
 * Usage: assistant messages only.
 * User messages must be rendered as plain React text, NOT through this component.
 */
export default function SafeMarkdown({ content }) {
  if (
    content === null ||
    content === undefined ||
    typeof content !== 'string' ||
    !content.trim()
  ) {
    return null
  }

  const rawHtml  = marked.parse(content)
  const safeHtml = DOMPurify.sanitize(rawHtml, PURIFY_CONFIG)

  return (
    <div
      className="markdown-body"
      // safeHtml is the output of DOMPurify.sanitize() — the only permitted
      // value for dangerouslySetInnerHTML in this codebase.
      dangerouslySetInnerHTML={{ __html: safeHtml }}
    />
  )
}

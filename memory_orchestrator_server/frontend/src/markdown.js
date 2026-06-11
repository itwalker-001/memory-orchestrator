import MarkdownIt from 'markdown-it'
import { createHighlighterCore } from 'shiki/core'
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript'
import { fromHighlighter } from '@shikijs/markdown-it/core'

import oneLight from 'shiki/themes/one-light.mjs'
import oneDarkPro from 'shiki/themes/one-dark-pro.mjs'

// Languages we actually see in stored memories (code blocks + dir trees/config).
// Imported explicitly via the core API so Shiki bundles ONLY these grammars —
// importing from 'shiki' directly would pull in the entire language registry.
const langs = [
  import('shiki/langs/bash.mjs'),
  import('shiki/langs/javascript.mjs'),
  import('shiki/langs/typescript.mjs'),
  import('shiki/langs/json.mjs'),
  import('shiki/langs/python.mjs'),
  import('shiki/langs/sql.mjs'),
  import('shiki/langs/yaml.mjs'),
  import('shiki/langs/vue.mjs'),
  import('shiki/langs/css.mjs'),
  import('shiki/langs/html.mjs'),
  import('shiki/langs/markdown.mjs'),
  import('shiki/langs/docker.mjs'),
  import('shiki/langs/ini.mjs'),
  import('shiki/langs/diff.mjs'),
]
const THEMES = { light: 'one-light', dark: 'one-dark-pro' }

// html: false → bare tags like "<script setup>" render as literal text, not HTML.
// This both fixes content being swallowed and removes the v-html XSS vector.
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

// Shiki's highlighter is async to create but synchronous to render. We build it
// once at app startup (see initMarkdown) so renderMarkdown can stay synchronous
// for the existing computed() call sites.
let ready = false

export async function initMarkdown() {
  if (ready) return
  const highlighter = await createHighlighterCore({
    themes: [oneLight, oneDarkPro],
    langs,
    // JS regex engine avoids shipping Shiki's ~600 kB Oniguruma wasm; it handles
    // all the grammars listed above.
    engine: createJavaScriptRegexEngine(),
  })
  md.use(fromHighlighter(highlighter, {
    themes: THEMES,
    // Emit CSS variables (--shiki-light / --shiki-dark) instead of baking one
    // color in, so we can switch via [data-theme] rather than the OS setting.
    defaultColor: false,
    fallbackLanguage: 'text',
  }))
  ready = true
}

// Some stored content uses the literal two-char sequence "\n" instead of a real
// newline; normalize before rendering so lists/paragraphs break correctly.
export function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text.replace(/\\n/g, '\n'))
}

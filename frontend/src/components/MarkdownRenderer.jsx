import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

/**
 * Matches citation references like:
 *   [منبع ۱], [منبع 2], [1], [2,3], [منبع ۱ و ۲]
 * and wraps them in a styled, clickable badge.
 */
const CITATION_REGEX = /\[(منبع\s*[\u06F0-\u06F9\d][\u06F0-\u06F9\d\sو،,]*|\d[\d\sو،,]*)\]/g;

function CitationBadge({ children }) {
  return (
    <a
      href="#sources"
      onClick={(e) => e.preventDefault()}
      className="citation-badge"
      title="منبع"
    >
      {children}
    </a>
  );
}

/**
 * Custom text renderer that splits plain text and wraps citation patterns
 * in styled badges while leaving the rest of the text untouched.
 */
function renderTextWithCitations(text) {
  const parts = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  CITATION_REGEX.lastIndex = 0;
  while ((match = CITATION_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(<CitationBadge key={key++}>{match[0]}</CitationBadge>);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length ? parts : text;
}

export default function MarkdownRenderer({ content }) {
  return (
    <div className="markdown-body text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Wrap text nodes so citations become badges
          text: ({ node, children }) => {
            const raw = String(children ?? "");
            return <>{renderTextWithCitations(raw)}</>;
          },
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mb-2 list-disc space-y-1 pr-5 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal space-y-1 pr-5 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => <li>{children}</li>,
          strong: ({ children }) => (
            <strong className="font-bold text-slate-900 dark:text-white">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          code: ({ inline, className, children }) => {
            if (inline) {
              return (
                <code className="rounded bg-slate-200/70 px-1.5 py-0.5 font-mono text-[0.85em] text-rose-600 dark:bg-slate-600/60 dark:text-rose-300">
                  {children}
                </code>
              );
            }
            return (
              <pre className="mb-2 overflow-x-auto rounded-lg bg-slate-900 p-3 text-slate-100 last:mb-0 dark:bg-slate-950">
                <code className={className}>{children}</code>
              </pre>
            );
          },
          pre: ({ children }) => <>{children}</>,
          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-r-4 border-slate-300 pr-3 text-slate-600 last:mb-0 dark:border-slate-600 dark:text-slate-300">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-300 bg-slate-100 px-2 py-1 text-right font-semibold dark:border-slate-600 dark:bg-slate-700">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-300 px-2 py-1 dark:border-slate-600">{children}</td>
          ),
          hr: () => <hr className="my-3 border-slate-300 dark:border-slate-600" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
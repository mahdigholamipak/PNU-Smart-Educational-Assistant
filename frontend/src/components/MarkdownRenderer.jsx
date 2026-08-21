import { Children, cloneElement, isValidElement, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import reactStringReplace from "react-string-replace";
import {
  autoUpdate,
  flip,
  offset,
  shift,
  useDismiss,
  useFloating,
  useHover,
  useInteractions,
} from "@floating-ui/react";
import "katex/dist/katex.min.css";

/**
 * Matches citation references like:
 *   [1], [ 1 ], [2,3], [4, 5], [منبع 1], [ منبع ۱ ], [منبع ۱ و ۲]
 *   (3), ( 3 ), (2,3), (منبع 3), ( منبع ۳ )
 * and extracts the numeric indices (Persian ۰-۹ + ASCII).
 * Tolerates optional whitespace inside the brackets and after "منبع".
 */
const CITATION_REGEX =
  /(?:\[\s*(?:منبع\s*)?([\u06F0-\u06F9\d][\u06F0-\u06F9\d\sو،,]*)\s*\]|\(\s*(?:منبع\s*)?([\u06F0-\u06F9\d][\u06F0-\u06F9\d\sو،,]*)\s*\))/g;

/** Convert Persian/Arabic digits to ASCII. */
function toAsciiDigits(str) {
  return str
    .replace(/[\u06F0-\u06F9]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

/** Extract a list of numeric indices from a citation match like "منبع ۱ و ۲" or "2,3". */
function extractIndices(raw) {
  const cleaned = toAsciiDigits(raw).replace(/منبع/g, "");
  const nums = cleaned.match(/\d+/g) || [];
  return nums.map(Number).filter((n) => n > 0);
}

/**
 * A single citation badge with its own isolated tooltip state.
 *
 * - `isOpen` lives in this component instance, so clicking one badge never
 *   opens another badge that references the same source ID.
 * - Floating UI smartly flips the popover below the badge when there isn't
 *   enough room above (e.g. citation on the first line), and shifts it to
 *   keep it fully inside the viewport.
 */
function CitationBadge({ label, source }) {
  const [isOpen, setIsOpen] = useState(false);

  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    placement: "top",
    middleware: [offset(8), flip(), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  });

  const hover = useHover(context, { move: false });
  const dismiss = useDismiss(context, { outsidePress: true });

  const { getReferenceProps, getFloatingProps } = useInteractions([
    hover,
    dismiss,
  ]);

  const toggle = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsOpen((v) => !v);
  };

  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        ref={refs.setReference}
        {...getReferenceProps()}
        onClick={toggle}
        className={`citation-badge ${isOpen ? "citation-badge-active" : ""}`}
        title={source ? `منبع: ${source.filename}` : "منبع"}
        aria-expanded={isOpen}
      >
        {label}
      </button>
      {isOpen && source && (
        <div
          ref={refs.setFloating}
          style={floatingStyles}
          {...getFloatingProps()}
          className="citation-popover"
          role="tooltip"
        >
          <div className="max-h-64 overflow-y-auto">
            <span className="block text-xs font-bold text-slate-800 dark:text-slate-100">
              📄 {source.filename}
            </span>
            {source.page != null && (
              <span className="mt-1 block text-xs text-slate-600 dark:text-slate-300">
                صفحه {source.page}
              </span>
            )}
            {source.snippet && (
              <span className="mt-1 block text-xs leading-relaxed text-slate-500 dark:text-slate-400">
                {source.snippet}
              </span>
            )}
          </div>
        </div>
      )}
    </span>
  );
}

/**
 * Deeply intercepts text nodes and wraps citation patterns (e.g. "[1]",
 * "[منبع ۱]", "[4, 5]", "(3)") in interactive badges. Recursively processes
 * React element children so citations inside <li>, <td>, <strong>, <em>,
 * <blockquote>, etc. are all converted — not just plain <p> paragraphs.
 *
 * Code blocks (<code>/<pre>) and math (KaTeX) are skipped so citations inside
 * those stay literal and cannot break the layout.
 */
function renderWithCitations(children, sources) {
  return Children.map(children, (child) => {
    // Plain text node → scan for citations.
    if (typeof child === "string") {
      return reactStringReplace(child, CITATION_REGEX, (match, i) => {
        const indices = extractIndices(match);
        if (indices.length === 0) {
          return `[${match}]`;
        }
        if (indices.length === 1) {
          const idx = indices[0];
          return (
            <CitationBadge
              key={i}
              label={String(idx)}
              source={sources?.[idx - 1]}
            />
          );
        }
        // Multi-citation: render one badge per source index side-by-side.
        return (
          <span key={i} className="inline-flex items-center gap-1">
            {indices.map((idx) => (
              <CitationBadge
                key={idx}
                label={String(idx)}
                source={sources?.[idx - 1]}
              />
            ))}
          </span>
        );
      });
    }

    // React element → recurse into its children (skip code/pre/math).
    if (isValidElement(child)) {
      if (
        child.type === CodeComponent ||
        child.type === PreComponent ||
        child.type === MathInline ||
        child.type === MathBlock
      ) {
        return child; // citations in code/math stay literal
      }
      if (child.props?.children) {
        return cloneElement(child, {
          ...child.props,
          children: renderWithCitations(child.props.children, sources),
        });
      }
      return child;
    }

    return child;
  });
}

/** Code block / inline code — citations inside code stay literal. */
function CodeComponent({ inline, className, children }) {
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
}

/** Pre wrapper — pass through (CodeComponent handles the actual <pre>). */
function PreComponent({ children }) {
  return <>{children}</>;
}

/**
 * Inline math (KaTeX) — `$...$`. Citations inside math formulas must stay
 * literal so the KaTeX renderer isn't corrupted by injected badge elements.
 *
 * CRITICAL: The global CSS sets `html { direction: rtl; }` for Persian text.
 * Math like `$w^R$` or `$((w^R)^R)$` must be forced to LTR with full bidi
 * isolation so parentheses and exponents render in the correct logical order.
 * The inline style (direction + unicodeBidi isolate + inline-block) is the
 * authoritative guarantee; the utility classes are a Tailwind fallback.
 */
function MathInline({ children }) {
  return (
    <span
      dir="ltr"
      className="math-inline inline-block text-left"
      style={{ direction: "ltr", unicodeBidi: "isolate", display: "inline-block" }}
    >
      {children}
    </span>
  );
}

/**
 * Block math (KaTeX) — `$$...$$` display equations. Same LTR + bidi isolation
 * as inline math, but rendered at block level so display equations keep their
 * own line and don't break the paragraph flow. overflow-x keeps wide equations
 * scrollable inside the chat bubble on small screens.
 */
function MathBlock({ children }) {
  return (
    <div
      dir="ltr"
      className="math-block text-left"
      style={{ direction: "ltr", unicodeBidi: "isolate", overflowX: "auto" }}
    >
      {children}
    </div>
  );
}

export default function MarkdownRenderer({ content, sources }) {
  return (
    <div className="markdown-body text-sm leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Intercept paragraphs so citations become interactive badges.
          p: ({ children }) => (
            <p className="mb-2 last:mb-0">
              {renderWithCitations(children, sources)}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="mb-2 list-disc space-y-1 pr-5 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal space-y-1 pr-5 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => (
            <li>{renderWithCitations(children, sources)}</li>
          ),
          strong: ({ children }) => (
            <strong className="font-bold text-slate-900 dark:text-white">
              {renderWithCitations(children, sources)}
            </strong>
          ),
          em: ({ children }) => (
            <em className="italic">{renderWithCitations(children, sources)}</em>
          ),
          code: CodeComponent,
          pre: PreComponent,
          math: MathBlock,
          inlineMath: MathInline,
          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-r-4 border-slate-300 pr-3 text-slate-600 last:mb-0 dark:border-slate-600 dark:text-slate-300">
              {renderWithCitations(children, sources)}
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
              {renderWithCitations(children, sources)}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-slate-300 px-2 py-1 dark:border-slate-600">
              {renderWithCitations(children, sources)}
            </td>
          ),
          hr: () => <hr className="my-3 border-slate-300 dark:border-slate-600" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
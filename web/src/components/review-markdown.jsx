import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function buildCitationMap(sources = []) {
  const map = new Map();

  sources.forEach((source, index) => {
    const number = index + 1;
    const key = `${source.id}:${source.page}`;
    map.set(key, {
      number,
      href: `#source-${number}`,
      tooltip: `${source.title} | ${source.journal_code || 'UNKNOWN'} | ${source.pub_year || 'NA'} | page ${source.page ?? 'NA'}`,
    });
  });

  return map;
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function replaceCitationToken(text, token, replacement) {
  const escaped = escapeRegex(token);
  return text
    .replace(new RegExp(`\\[${escaped}\\]`, 'g'), replacement)
    .replace(new RegExp(`\\(${escaped}\\)`, 'g'), replacement)
    .replace(new RegExp(`(^|[^\\w])${escaped}(?=([^\\w]|$))`, 'g'), `$1${replacement}`);
}

function stripReferencesSection(markdown = '') {
  return markdown.replace(/\n## References Used[\s\S]*$/i, '').trim();
}

function rewriteCitations(markdown = '', citationMap, sources = []) {
  let rewritten = stripReferencesSection(markdown);

  const citationEntries = sources
    .map((source, index) => ({
      number: index + 1,
      href: `#source-${index + 1}`,
      variants: [`${source.id}:${source.page}`, source.id].filter(Boolean),
    }))
    .sort((left, right) => {
      const leftMax = Math.max(...left.variants.map((item) => item.length));
      const rightMax = Math.max(...right.variants.map((item) => item.length));
      return rightMax - leftMax;
    });

  citationEntries.forEach((entry) => {
    const replacement = `[${entry.number}](${entry.href})`;
    entry.variants.forEach((variant) => {
      rewritten = replaceCitationToken(rewritten, variant, replacement);
    });
  });

  return rewritten.replace(/\[(\d+)\]\(#source-\1\)(\s*\[(\d+)\]\(#source-\3\))+/g, (match) => {
    const numbers = Array.from(match.matchAll(/\[(\d+)\]\(#source-\d+\)/g)).map((item) => item[1]);
    const unique = [...new Set(numbers)];
    return unique.map((number) => `[${number}](#source-${number})`).join('');
  });
}

export function ReviewMarkdown({ content, sources }) {
  const citationMap = buildCitationMap(sources);
  const citationByHref = new Map(Array.from(citationMap.values()).map((item) => [item.href, item]));
  const markdown = rewriteCitations(content, citationMap, sources);

  return (
    <div className="rounded-[1.7rem] border border-slate-200 bg-slate-50 p-6">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: ({ children }) => (
            <h2 className="mt-8 border-b border-slate-200 pb-3 text-2xl font-semibold text-slate-950 first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-6 text-lg font-semibold text-slate-900">{children}</h3>
          ),
          p: ({ children }) => (
            <p className="mt-4 text-[15px] leading-8 text-slate-700 first:mt-0">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="mt-4 list-disc space-y-2 pl-6 text-[15px] leading-8 text-slate-700">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mt-4 list-decimal space-y-2 pl-6 text-[15px] leading-8 text-slate-700">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-1 marker:text-slate-400">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-slate-950">{children}</strong>,
          code: ({ inline, children }) => (
            inline ? (
              <code className="rounded-md bg-slate-200 px-1.5 py-0.5 text-[0.92em] text-slate-800">{children}</code>
            ) : (
              <code className="block overflow-x-auto rounded-2xl bg-slate-900 p-4 text-sm text-slate-100">{children}</code>
            )
          ),
          a: ({ href, children }) => {
            if (href?.startsWith('#source-')) {
              const citation = citationByHref.get(href);
              return (
                <a
                  href={href}
                  title={citation?.tooltip}
                  className="mx-0.5 inline-flex -translate-y-1/4 align-super rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold leading-none text-indigo-700 no-underline ring-1 ring-inset ring-indigo-200 transition hover:bg-indigo-100"
                >
                  {children}
                </a>
              );
            }

            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-indigo-700 underline decoration-indigo-300 underline-offset-2"
              >
                {children}
              </a>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

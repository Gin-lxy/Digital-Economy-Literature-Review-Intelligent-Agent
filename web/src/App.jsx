import { useRef, useState } from 'react';
import { Badge, Button, Card, Input, Modal } from './components/ui';
import { ReviewMarkdown } from './components/review-markdown';
import { useGenerateReview, useIndexStatus, useSystemConfig } from './api/hooks';
import { APP_CONFIG } from './config/constants';
import {
  copyToClipboard,
  downloadFile,
  generateMarkdownContent,
  generateShareLink,
  printToPDF,
  saveAsJSON,
  showSuccessToast,
} from './utils/export';

const defaultJournalCodeOptions = ['AMJ', 'AMR', 'ASQ', 'JOM', 'SMJ', 'ORGS', 'ORSC', 'JIBS', 'JMIS', 'JBE', 'RFS', 'RP', 'ARXIV', 'UNKNOWN']
  .map((value) => ({ value, label: value }));

const detailLabels = { concise: 'Concise', standard: 'Standard', deep: 'Deep' };
const SELECT_ALL_VALUE = '__all__';

function sanitizeSelectableOptions(options = []) {
  return options.filter((option) => option?.value && option.value !== 'other');
}

function MultiSelect({ label, value, options, onChange, hint }) {
  const normalizedOptions = sanitizeSelectableOptions(options);
  const optionValues = normalizedOptions.map((option) => option.value);
  const allSelected = optionValues.length > 0 && optionValues.every((item) => value.includes(item));
  const displayValue = allSelected ? [SELECT_ALL_VALUE, ...value] : value;

  function handleChange(event) {
    const selectedValues = Array.from(event.target.selectedOptions, (option) => option.value);
    if (selectedValues.includes(SELECT_ALL_VALUE)) {
      onChange(allSelected ? [] : optionValues);
      return;
    }
    onChange(selectedValues.filter((item) => item !== 'other'));
  }

  return (
    <div>
      <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</label>
      <select
        multiple
        value={displayValue}
        onChange={handleChange}
        className="h-[132px] w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900"
      >
        <option value={SELECT_ALL_VALUE}>Select all</option>
        {normalizedOptions.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <p className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  );
}

function App() {
  const [query, setQuery] = useState('');
  const [detailLevel, setDetailLevel] = useState(APP_CONFIG.defaultDetailLevel);
  const [sourceMode, setSourceMode] = useState(APP_CONFIG.defaultSourceMode);
  const [topK, setTopK] = useState(6);
  const [arxivMaxResults, setArxivMaxResults] = useState(3);
  const [subfields, setSubfields] = useState([]);
  const [journalCategories, setJournalCategories] = useState([]);
  const [journalCodes, setJournalCodes] = useState([]);
  const [yearFrom, setYearFrom] = useState('');
  const [yearTo, setYearTo] = useState('');
  const [history, setHistory] = useState([]);
  const [selectedResult, setSelectedResult] = useState(null);
  const [modalType, setModalType] = useState(null);

  const queryRef = useRef(null);
  const { loading, error, generate } = useGenerateReview();
  const { status: indexStatus, loading: indexLoading } = useIndexStatus();
  const { config } = useSystemConfig();

  const yearMin = Number(config?.year_filter_min) || 2018;
  const yearMax = Number(config?.year_filter_max) || 2025;
  const yearOptions = Array.from({ length: yearMax - yearMin + 1 }, (_, idx) => yearMin + idx);
  const subfieldOptions = sanitizeSelectableOptions(config?.subfield_options || []);
  const journalCategoryOptions = sanitizeSelectableOptions(config?.journal_category_options || []);
  const journalCodeOptions = sanitizeSelectableOptions(config?.journal_code_options || defaultJournalCodeOptions);

  const sourceCounts = (selectedResult?.sources || []).reduce(
    (acc, item) => {
      if (item.source_type === 'arxiv') acc.arxiv += 1;
      else acc.local += 1;
      return acc;
    },
    { local: 0, arxiv: 0 }
  );

  async function handleGenerate(event) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2) {
      alert('Please enter at least 2 characters.');
      queryRef.current?.focus();
      return;
    }

    const parsedYearFrom = yearFrom ? Number(yearFrom) : null;
    const parsedYearTo = yearTo ? Number(yearTo) : null;
    if (parsedYearFrom && parsedYearTo && parsedYearFrom > parsedYearTo) {
      alert('year_from cannot be greater than year_to.');
      return;
    }

    try {
      const result = await generate({
        query: normalizedQuery,
        detailLevel,
        sourceMode,
        topK: Number(topK) || null,
        arxivMaxResults: Number(arxivMaxResults) || null,
        subfields,
        journalCategories,
        journalCodes,
        yearFrom: parsedYearFrom,
        yearTo: parsedYearTo,
      });
      setSelectedResult(result);
      setHistory((prev) => [{ id: Date.now(), query: normalizedQuery, result, time: new Date() }, ...prev]);
    } catch (err) {
      console.error(err);
    }
  }

  async function copyResult() {
    if (!selectedResult) return;
    await copyToClipboard(selectedResult.review || '');
    showSuccessToast('Copied to clipboard.');
  }

  function exportMarkdown() {
    if (!selectedResult) return;
    const content = generateMarkdownContent(selectedResult, selectedResult.query || query);
    downloadFile(content, `review_${Date.now()}.md`, 'text/markdown');
    showSuccessToast('Downloaded markdown file.');
  }

  function exportPdf() {
    if (!selectedResult) return;
    printToPDF(selectedResult, selectedResult.query || query);
    showSuccessToast('Opened print preview.');
  }

  function exportJson() {
    if (!selectedResult) return;
    saveAsJSON(selectedResult, selectedResult.query || query);
    showSuccessToast('Downloaded JSON file.');
  }

  function shareResult() {
    if (!selectedResult) return;
    copyToClipboard(generateShareLink(selectedResult, selectedResult.query || query)).then(() => {
      showSuccessToast('Share link copied.');
    });
  }

  const yearSummary =
    selectedResult?.metadata?.year_from == null && selectedResult?.metadata?.year_to == null
      ? 'Any year'
      : `${selectedResult?.metadata?.year_from ?? 'Any'} - ${selectedResult?.metadata?.year_to ?? 'Any'}`;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto grid max-w-[1600px] gap-6 px-4 py-8 sm:px-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="h-fit rounded-[2rem] border border-slate-200 bg-white p-6 shadow-soft xl:sticky xl:top-8">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-indigo-600">Research Copilot</p>
          <h1 className="mt-3 text-2xl font-semibold text-slate-950">{APP_CONFIG.appName}</h1>
          <div className="mt-6 rounded-[1.6rem] border border-slate-200 bg-slate-50 p-5">
            <p className="mb-3 text-xs uppercase tracking-[0.18em] text-slate-500">System Status</p>
            {indexLoading ? <p className="text-sm text-slate-500">Loading...</p> : (
              <div className="space-y-3 text-sm text-slate-600">
                <div className="flex items-center justify-between">
                  <span>Pipeline</span>
                  <Badge variant={indexStatus?.index_exists ? 'success' : 'default'}>
                    {indexStatus?.index_exists ? 'Ready' : 'Missing'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between"><span>Chunks</span><Badge variant="info">{indexStatus?.chunks_count ?? 0}</Badge></div>
                <div className="flex items-center justify-between"><span>FAISS</span><span className="font-semibold">{indexStatus?.index_size_mb ?? 0} MB</span></div>
              </div>
            )}
          </div>
          <div className="mt-6 rounded-[1.6rem] border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
            <p className="mb-3 text-xs uppercase tracking-[0.18em] text-slate-500">Operating Model</p>
            <p>1. Build corpus and index.</p>
            <p>2. Filter evidence by topic, venue, and year.</p>
            <p>3. Export grounded outputs for reports and experiments.</p>
          </div>
          {history.length > 0 && (
            <div className="mt-6 rounded-[1.6rem] border border-slate-200 bg-slate-50 p-5">
              <p className="mb-3 text-xs uppercase tracking-[0.18em] text-slate-500">Recent Runs</p>
              <div className="space-y-2">
                {history.slice(0, 4).map((item) => (
                  <button key={item.id} onClick={() => setSelectedResult(item.result)} className="block w-full rounded-2xl bg-white p-3 text-left text-xs text-slate-600 transition hover:bg-slate-100">
                    <div className="truncate font-medium text-slate-900">{item.query}</div>
                    <div className="mt-1 text-slate-500">{item.time.toLocaleString()}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="mt-6 rounded-[1.6rem] border border-slate-200 bg-slate-50 p-5">
            <p className="mb-3 text-xs uppercase tracking-[0.18em] text-slate-500">Runtime Configuration</p>
            <p className="mb-4 text-sm leading-6 text-slate-500">Current backend settings exposed to the client</p>
            {config ? (
              <div className="space-y-3 text-sm text-slate-600">
                <div className="rounded-3xl bg-white px-4 py-3"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">Provider</p><p className="mt-1 break-words font-semibold text-slate-900">{config.llm_provider}</p></div>
                <div className="rounded-3xl bg-white px-4 py-3"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">LLM Model</p><p className="mt-1 break-words font-semibold text-slate-900">{config.llm_model}</p></div>
                <div className="rounded-3xl bg-white px-4 py-3"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">Embedding Model</p><p className="mt-1 break-words text-xs font-semibold text-slate-900 [overflow-wrap:anywhere]">{config.embedding_model}</p></div>
              </div>
            ) : <p className="text-sm text-slate-500">Loading config...</p>}
          </div>
          <div className="mt-6 rounded-[1.6rem] border border-slate-200 bg-slate-50 p-5">
            <p className="mb-3 text-xs uppercase tracking-[0.18em] text-slate-500">Product Docs</p>
            <p className="mb-4 text-sm leading-6 text-slate-500">Inline guidance for the main product entry</p>
            <div className="space-y-3">
              <button onClick={() => setModalType('guide')} className="block w-full rounded-2xl border border-slate-200 bg-white p-3 text-left text-sm transition hover:bg-slate-100">Operator Guide</button>
              <button onClick={() => setModalType('workflow')} className="block w-full rounded-2xl border border-slate-200 bg-white p-3 text-left text-sm transition hover:bg-slate-100">Workflow Notes</button>
              <button onClick={() => setModalType('faq')} className="block w-full rounded-2xl border border-slate-200 bg-white p-3 text-left text-sm transition hover:bg-slate-100">Troubleshooting</button>
            </div>
          </div>
        </aside>

        <main className="min-w-0 space-y-6">
          <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-soft">
            <div className="mb-6 flex items-start justify-between gap-4">
              <div className="max-w-3xl">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Primary Product Surface</p>
                <h2 className="mt-3 text-3xl font-semibold text-slate-950">
                  {selectedResult ? 'Grounded Review Output' : 'Generate a literature review with full retrieval controls'}
                </h2>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  This web app is the main agent experience. It exposes the same hybrid retrieval, metadata filtering,
                  and export pipeline used by the backend API.
                </p>
              </div>
              {selectedResult && <Button variant="secondary" onClick={() => setSelectedResult(null)}>New Run</Button>}
            </div>

            {!selectedResult && (
              <form onSubmit={handleGenerate} className="space-y-5">
                <div>
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Research Question</label>
                  <Input ref={queryRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Example: How does platform governance affect labor quality and firm performance?" disabled={loading} />
                </div>
                <div className="grid gap-4 md:grid-cols-4">
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Detail</label>
                    <select value={detailLevel} onChange={(event) => setDetailLevel(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm">
                      <option value="concise">Concise</option>
                      <option value="standard">Standard</option>
                      <option value="deep">Deep</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Source Mode</label>
                    <select value={sourceMode} onChange={(event) => setSourceMode(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm">
                      <option value="local_only">Local only</option>
                      <option value="arxiv_only">arXiv only</option>
                      <option value="local_plus_arxiv">Local + arXiv</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Top-K</label>
                    <input type="number" min="1" max="50" value={topK} onChange={(event) => setTopK(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">arXiv Max</label>
                    <input type="number" min="1" max="20" value={arxivMaxResults} onChange={(event) => setArxivMaxResults(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm" />
                  </div>
                </div>
                <div className="grid gap-4 xl:grid-cols-3">
                  <MultiSelect label="Subfields" value={subfields} options={subfieldOptions} onChange={setSubfields} hint="Optional topical narrowing." />
                  <MultiSelect label="Journal Categories" value={journalCategories} options={journalCategoryOptions} onChange={setJournalCategories} hint="Useful for domain-specific reviews." />
                  <MultiSelect label="Journal Codes" value={journalCodes} options={journalCodeOptions} onChange={setJournalCodes} hint="Exact venue-level filtering." />
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Year From</label>
                    <select value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm">
                      <option value="">Any</option>
                      {yearOptions.map((year) => <option key={year} value={year}>{year}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Year To</label>
                    <select value={yearTo} onChange={(event) => setYearTo(event.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm">
                      <option value="">Any</option>
                      {yearOptions.map((year) => <option key={year} value={year}>{year}</option>)}
                    </select>
                  </div>
                  <div className="flex items-end">
                    <Button type="submit" variant="accent" disabled={loading || !query.trim()} className="w-full">{loading ? 'Running agent...' : 'Run Agent'}</Button>
                  </div>
                </div>
                {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">Warning: {error}</div>}
              </form>
            )}
          </section>

          {selectedResult && (
            <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,0.95fr)]">
              <Card title="Generated Review" description="Formatted, evidence-grounded review with linked citations">
                <div className="space-y-4">
                  <ReviewMarkdown content={selectedResult.review} sources={selectedResult.sources || []} />
                  <div className="grid gap-4 md:grid-cols-2">
                    <Button variant="secondary" className="w-full" onClick={copyResult}>Copy Text</Button>
                    <Button variant="accent" className="w-full" onClick={exportPdf}>Download PDF</Button>
                  </div>
                </div>
              </Card>
              <div className="min-w-0 space-y-6">
                <Card title="Run Summary" description="Runtime settings and retrieval outcome">
                  <div className="space-y-3 text-sm text-slate-600">
                    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">Query</p><p className="mt-1 break-words font-semibold text-slate-900">{selectedResult.query}</p></div>
                    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">Profile</p><p className="mt-1 break-words font-semibold text-slate-900">{detailLabels[selectedResult.metadata?.detail_level] || selectedResult.metadata?.detail_level}</p><p className="mt-1 break-words font-semibold text-slate-900">{selectedResult.metadata?.source_mode}</p></div>
                    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">Evidence Mix</p><p className="mt-1 break-words font-semibold text-slate-900">Local {sourceCounts.local} | arXiv {sourceCounts.arxiv}</p></div>
                    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs uppercase tracking-[0.18em] text-slate-500">Filters</p><p className="mt-1 break-words font-semibold text-slate-900 [overflow-wrap:anywhere]">Subfields: {(selectedResult.metadata?.subfields || []).join(', ') || 'All'}</p><p className="mt-1 break-words font-semibold text-slate-900 [overflow-wrap:anywhere]">Categories: {(selectedResult.metadata?.journal_categories || []).join(', ') || 'All'}</p><p className="mt-1 break-words font-semibold text-slate-900 [overflow-wrap:anywhere]">Codes: {(selectedResult.metadata?.journal_codes || []).join(', ') || 'All'}</p><p className="mt-1 break-words font-semibold text-slate-900">Year: {yearSummary}</p></div>
                  </div>
                </Card>
                <Card title="Sources" description={`Total ${selectedResult.sources?.length || 0}`}>
                  <div className="max-h-80 space-y-3 overflow-y-auto">
                    {(selectedResult.sources || []).map((source, idx) => (
                      <div id={`source-${idx + 1}`} key={`${source.id}-${idx}`} className="scroll-mt-24 rounded-3xl border border-slate-200 bg-slate-50 p-3 text-sm">
                        <div className="mb-1 flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="mb-2 flex items-center gap-2">
                              <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-indigo-600 px-2 text-xs font-semibold text-white">
                                {idx + 1}
                              </span>
                              <Badge variant={source.source_type === 'arxiv' ? 'info' : 'default'}>{source.source_type === 'arxiv' ? 'arXiv' : 'Local'}</Badge>
                            </div>
                            <p className="break-words font-semibold text-slate-900">{source.title}</p>
                          </div>
                        </div>
                        <p className="break-words text-xs text-slate-500 [overflow-wrap:anywhere]">{source.id}</p>
                        <p className="break-words text-xs text-slate-500 [overflow-wrap:anywhere]">{source.journal_code || 'UNKNOWN'} | {source.journal_category || 'other'} | {source.pub_year || 'NA'} | page {source.page ?? 'NA'}</p>
                      </div>
                    ))}
                  </div>
                </Card>
                <Card title="Export">
                  <div className="space-y-3">
                    <Button variant="accent" className="w-full" onClick={exportMarkdown}>Export Markdown</Button>
                    <Button variant="secondary" className="w-full" onClick={exportJson}>Save JSON</Button>
                    <Button variant="subtle" className="w-full" onClick={shareResult}>Copy Share Link</Button>
                  </div>
                </Card>
              </div>
            </div>
          )}
        </main>

      </div>

      <Modal isOpen={Boolean(modalType)} title={modalType === 'guide' ? 'Operator Guide' : modalType === 'workflow' ? 'Workflow Notes' : 'Troubleshooting'} onClose={() => setModalType(null)}>
        {modalType === 'guide' && <div className="space-y-3 text-sm"><p>1. Build corpus and index before local retrieval.</p><p>2. Start `backend.py` and the Vite client.</p><p>3. Run the agent with filters that match your review scope.</p><p>4. Export after checking source coverage.</p></div>}
        {modalType === 'workflow' && <div className="space-y-3 text-sm"><p>Use hybrid mode when you need both private PDFs and recent arXiv evidence.</p><p>Use subfields and categories to reduce retrieval drift on broad topics.</p><p>Use journal codes for controlled experiments and ablation comparisons.</p></div>}
        {modalType === 'faq' && <div className="space-y-3 text-sm"><p>No results usually means missing index files or overly strict filters.</p><p>Request failures usually mean the backend is not reachable on port 8000.</p><p>Sparse citations usually mean the retrieval set is too small or too narrow.</p></div>}
      </Modal>
    </div>
  );
}

export default App;

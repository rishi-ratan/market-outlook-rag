"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type Citation = {
  chunk_id: string;
  page: number;
  quote: string;
};

type AskResponse = {
  answer: string;
  key_points: string[];
  citations: Citation[];
  not_found: boolean;
  provider?: string;
};

type ComparisonResponse = {
  question: string;
  responses: AskResponse[];
};

export default function Page() {
  const API_BASE = useMemo(
    () => process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000",
    []
  );

  const TOP_K = 8; // number of passages retrieved from the report
  const PDF_PUBLIC_PATH = "/report.pdf";

  const SUGGESTED_QUESTIONS: string[] = [
    "What does the report say about the secondaries market and liquidity?",
    "What does the report say about the outlook for real estate sectors like data centers and life sciences, and what demand drivers does it cite?",
    "What are the key risks and opportunities discussed for private credit?",
    "What does the report highlight about infrastructure and energy transition?",
  ];

  const HISTORY_KEY = "moa_session_history_v1";
  const MAX_HISTORY = 8;

  const formRef = useRef<HTMLFormElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [warming, setWarming] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AskResponse | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonResponse | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [isFocused, setIsFocused] = useState(false);
  const [provider, setProvider] = useState<"openai" | "together">("openai");
  const [compareMode, setCompareMode] = useState(false);

  const [pdfOpen, setPdfOpen] = useState(false);
  const [pdfPage, setPdfPage] = useState<number>(1);
  const [pdfQuote, setPdfQuote] = useState<string>("");

  function openPdfAt(page: number, quote: string) {
    setPdfPage(page || 1);
    setPdfQuote(quote || "");
    setPdfOpen(true);
  }

  function onQuestionKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      // Trigger form submit
      (e.currentTarget.form as HTMLFormElement | null)?.requestSubmit();
    }
  }

  useEffect(() => {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          // Limit to MAX_HISTORY items when loading from storage
          const validHistory = parsed
            .filter((x) => typeof x === "string")
            .slice(0, MAX_HISTORY);
          setHistory(validHistory);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Warm the backend (helps with cold starts on serverless hosts)
  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .catch(() => {
        // ignore warmup errors
      })
      .finally(() => setWarming(false));
  }, [API_BASE]);

  useEffect(() => {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch {
      // ignore
    }
  }, [history]);

  function pushHistory(q: string) {
    setHistory((prev) => {
      // Remove duplicates, add new question to front
      const withoutDuplicate = prev.filter((x) => x !== q);
      const withNew = [q, ...withoutDuplicate];
      // Keep only the most recent MAX_HISTORY items (remove oldest if we exceed limit)
      return withNew.slice(0, MAX_HISTORY);
    });
  }

  function applyQuestion(q: string) {
    setQuestion(q);
    setTimeout(() => {
      textareaRef.current?.focus();
      formRef.current?.requestSubmit();
    }, 0);
  }

  async function onAsk(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setData(null);
    setComparisonData(null);

    const q = question.trim();
    if (!q) {
      setError("Please enter a question.");
      return;
    }

    pushHistory(q);

    setLoading(true);
    try {
      const endpoint = compareMode ? "/ask/compare" : "/ask";
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          question: q, 
          top_k: TOP_K,
          provider: compareMode ? undefined : provider,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error (${res.status}): ${text}`);
      }

      if (compareMode) {
        const json = (await res.json()) as ComparisonResponse;
        setComparisonData(json);
      } else {
        const json = (await res.json()) as AskResponse;
        setData(json);
      }
    } catch (err: any) {
      setError(err?.message ?? "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900/80 via-zinc-800/30 via-zinc-900/60 to-zinc-950 text-zinc-100 relative">
      <div className="absolute inset-0 bg-gradient-to-tr from-zinc-950/50 via-transparent to-zinc-900/30 pointer-events-none" />
      <div className="relative z-10">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr,360px]">
          <header className="mb-8 relative">
            <div className="absolute top-0 right-0">
              <Link
                href="/about"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900/80 hover:text-zinc-100 transition-colors"
                title="About this project"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="w-5 h-5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
                  />
                </svg>
                <span className="hidden sm:inline">How it works</span>
              </Link>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-1 text-xs text-zinc-300">
              RAG Prototype • Single PDF • Grounded Q&A
            </div>
            <h1 className="mt-5 text-5xl font-semibold tracking-tight">
              Market Outlook Analyst
            </h1>
            <p className="mt-3 text-lg text-zinc-300">
              Ask questions about BlackRock&apos;s 2026 Private Markets Outlook
            </p>
          </header>
          <div>
            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
              <form ref={formRef} onSubmit={onAsk} className="space-y-4">
                <div className="relative">
                  <textarea
                    ref={textareaRef}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={onQuestionKeyDown}
                    onFocus={() => setIsFocused(true)}
                    onBlur={() => setIsFocused(false)}
                    rows={4}
                    placeholder='e.g., "What are the main themes of the report?"'
                    className={`w-full resize-none rounded-2xl border bg-zinc-950/60 px-4 py-3 text-lg text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-zinc-700 transition-all duration-500 ease-in-out ${
                      loading
                        ? "border-white/30 glow-border-bright"
                        : isFocused
                        ? "border-zinc-600 glow-border-subtle"
                        : "border-zinc-800"
                    }`}
                  />
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 text-sm text-zinc-300">
                      <input
                        type="checkbox"
                        checked={compareMode}
                        onChange={(e) => setCompareMode(e.target.checked)}
                        className="rounded border-zinc-700 bg-zinc-900 text-zinc-100 focus:ring-2 focus:ring-zinc-600"
                      />
                      <span>Compare providers</span>
                    </label>
                    {!compareMode && (
                      <select
                        value={provider}
                        onChange={(e) => setProvider(e.target.value as "openai" | "together")}
                        className="rounded-lg border border-zinc-700 bg-zinc-900/60 px-3 py-1.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-600"
                        aria-label="Select LLM provider"
                        title="Select LLM provider"
                      >
                        <option value="openai">OpenAI (GPT-4o-mini)</option>
                        <option value="together">Together AI (Qwen2.5-72B)</option>
                      </select>
                    )}
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="rounded-xl bg-zinc-100 px-6 py-2.5 text-sm font-medium text-zinc-900 hover:bg-white disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
                  >
                    {loading ? (
                      <span className="inline-flex items-center gap-2">
                        Asking
                        <span className="inline-flex w-8 justify-start">
                          <span className="dot" />
                          <span className="dot" />
                          <span className="dot" />
                        </span>
                      </span>
                    ) : (
                      compareMode ? "Compare" : "Ask"
                    )}
                  </button>
                </div>

                {error && (
                  <div className="rounded-xl border border-red-900/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
                    {error}
                  </div>
                )}
              </form>
            </section>

            {loading && (
              <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                <div className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-400">
                  Working
                </div>
                <div className="space-y-3">
                  <div className="h-4 w-5/6 rounded bg-zinc-800/60 animate-pulse" />
                  <div className="h-4 w-4/6 rounded bg-zinc-800/50 animate-pulse" />
                  <div className="h-4 w-3/6 rounded bg-zinc-800/40 animate-pulse" />
                </div>
              </section>
            )}

            {comparisonData && (
              <section className="mt-6 space-y-6 fade-in">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                  <div className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-400">
                    Comparison Results
                  </div>
                  <p className="text-lg text-zinc-300 mb-6">{comparisonData.question}</p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {comparisonData.responses.map((response, idx) => (
                      <div key={idx} className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-5">
                        <div className="mb-3 flex items-center justify-between">
                          <div className="text-sm font-medium text-zinc-200">
                            {response.provider || `Provider ${idx + 1}`}
                          </div>
                        </div>
                        
                        <div className="mb-4">
                          <div className="text-xs font-medium uppercase tracking-wide text-zinc-400 mb-2">
                            Answer
                          </div>
                          <p className="text-sm leading-6 text-zinc-100">
                            {response.not_found ? "I cannot find this in the report." : response.answer}
                          </p>
                        </div>

                        {response.key_points?.length > 0 && (
                          <div className="mb-4">
                            <div className="text-xs font-medium uppercase tracking-wide text-zinc-400 mb-2">
                              Key Points
                            </div>
                            <ul className="list-inside list-disc space-y-1 text-sm text-zinc-200">
                              {response.key_points.map((kp, i) => (
                                <li key={i}>{kp}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <details className="mt-4">
                          <summary className="cursor-pointer text-xs font-medium text-zinc-400 hover:text-zinc-200">
                            Sources ({response.citations?.length ?? 0})
                          </summary>
                          <div className="mt-2 space-y-2">
                            {response.citations?.map((c, i) => (
                              <button
                                key={`${c.chunk_id}-${i}`}
                                type="button"
                                onClick={() => openPdfAt(c.page, c.quote)}
                                className="w-full text-left rounded-lg border border-zinc-800 bg-zinc-900/40 p-2 hover:bg-zinc-900/60 text-xs"
                              >
                                <div className="text-zinc-300">Page {c.page}</div>
                                <div className="text-zinc-400 mt-1">"{c.quote}"</div>
                              </button>
                            ))}
                          </div>
                        </details>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            )}

            {data && !comparisonData && (
              <section className="mt-6 space-y-4 fade-in">
                {data.provider && (
                  <div className="text-xs text-zinc-500 mb-2">Provider: {data.provider}</div>
                )}
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                  <div className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-400">
                    Answer
                  </div>
                  <p className="text-lg leading-8 text-zinc-100">
                    {data.not_found ? "I cannot find this in the report." : data.answer}
                  </p>
                </div>

                {data.key_points?.length > 0 && (
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                    <div className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-400">
                      Key points
                    </div>
                    <ul className="list-inside list-disc space-y-3 text-lg text-zinc-200">
                      {data.key_points.map((kp, i) => (
                        <li key={i}>{kp}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <details className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
                  <summary className="cursor-pointer select-none text-sm font-medium text-zinc-200">
                    Sources ({data.citations?.length ?? 0})
                  </summary>

                  {(!data.citations || data.citations.length === 0) && (
                    <p className="mt-3 text-sm text-zinc-400">No citations returned.</p>
                  )}

                  <div className="mt-4 space-y-3">
                    {data.citations?.map((c, i) => (
                      <button
                        key={`${c.chunk_id}-${i}`}
                        type="button"
                        onClick={() => openPdfAt(c.page, c.quote)}
                        className="w-full text-left rounded-xl border border-zinc-800 bg-zinc-950/40 p-3 hover:bg-zinc-900/40 focus:outline-none focus:ring-2 focus:ring-zinc-700 transition"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-xs text-zinc-400">
                            <span className="font-medium text-zinc-200">Page {c.page}</span>
                          </div>
                          <span className="text-xs text-zinc-500">Open PDF →</span>
                        </div>
                        <div className="mt-2 text-sm text-zinc-200">"{c.quote}"</div>
                      </button>
                    ))}
                  </div>
                </details>

              </section>
            )}
          </div>

          <aside className="space-y-6">
            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-6">
              <div className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-400">
                Suggested questions
              </div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => applyQuestion(q)}
                    className="chip rounded-full border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 focus:outline-none focus:ring-2 focus:ring-zinc-700"
                  >
                    {q}
                  </button>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <p className="text-sm text-zinc-500">Tip: press Enter to submit, Shift+Enter for a new line.</p>
                {warming && (
                  <div className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-950/30 px-3 py-1 text-xs text-zinc-400">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-zinc-500 animate-pulse" />
                    Initializing…
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-6">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-sm font-medium uppercase tracking-wide text-zinc-400">Session history</div>
                <button
                  type="button"
                  onClick={() => setHistory([])}
                  className="text-xs text-zinc-500 hover:text-zinc-300 transition"
                >
                  Clear
                </button>
              </div>

              {history.length === 0 ? (
                <p className="text-sm text-zinc-500">No questions yet.</p>
              ) : (
                <ul className="space-y-2">
                  {history.map((h) => (
                    <li key={h}>
                      <button
                        type="button"
                        onClick={() => applyQuestion(h)}
                        className="history-item w-full text-left rounded-xl border border-zinc-800 bg-zinc-950/30 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 focus:outline-none focus:ring-2 focus:ring-zinc-700"
                      >
                        {h}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </aside>
        </div>
      </div>
      </div>
      {pdfOpen && (
        <div className="fixed inset-0 z-50">
          <div
            className="absolute inset-0 bg-black/70"
            onClick={() => setPdfOpen(false)}
          />
          <div className="absolute inset-0 p-4 sm:p-8">
            <div className="mx-auto flex h-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl">
              <div className="flex items-center justify-between gap-4 border-b border-zinc-800 bg-zinc-900/40 px-4 py-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-zinc-200">Report viewer</div>
                  <div className="truncate text-xs text-zinc-400">Page {pdfPage}{pdfQuote ? ` • “${pdfQuote}”` : ""}</div>
                </div>
                <button
                  type="button"
                  onClick={() => setPdfOpen(false)}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1.5 text-sm text-zinc-200 hover:bg-zinc-900/60 focus:outline-none focus:ring-2 focus:ring-zinc-700"
                >
                  Close
                </button>
              </div>

              <div className="flex-1 bg-zinc-900/10">
                <iframe
                  title="PDF Viewer"
                  src={`${PDF_PUBLIC_PATH}#page=${pdfPage}`}
                  className="h-full w-full"
                />
              </div>
            </div>
            <div className="mx-auto mt-3 max-w-6xl text-xs text-zinc-500">
              Tip: The built-in PDF viewer jumps to the cited page. Highlighting exact quoted text inside the PDF requires a PDF.js-based renderer.
            </div>
          </div>
        </div>
      )}
      <style jsx global>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .fade-in { animation: fadeInUp 220ms ease-out; }

        @keyframes dotPulse {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.35; }
          40% { transform: translateY(-2px); opacity: 0.9; }
        }
        .dot {
          width: 4px;
          height: 4px;
          border-radius: 9999px;
          margin-right: 4px;
          background: currentColor;
          display: inline-block;
          animation: dotPulse 1s infinite;
        }
        .dot:nth-child(2) { animation-delay: 0.15s; }
        .dot:nth-child(3) { animation-delay: 0.3s; }

        @keyframes glowSubtle {
          0%, 100% {
            box-shadow: 0 0 4px rgba(255, 255, 255, 0.1),
                        0 0 6px rgba(255, 255, 255, 0.05);
          }
        }
        .glow-border-subtle {
          animation: glowSubtle 2s ease-in-out infinite;
          transition: box-shadow 0.6s ease-in-out, border-color 0.6s ease-in-out;
        }

        @keyframes glowBrightPulse {
          0%, 100% {
            box-shadow: 0 0 6px rgba(255, 255, 255, 0.3),
                        0 0 10px rgba(255, 255, 255, 0.2),
                        0 0 14px rgba(255, 255, 255, 0.15);
          }
          50% {
            box-shadow: 0 0 10px rgba(255, 255, 255, 0.4),
                        0 0 16px rgba(255, 255, 255, 0.25),
                        0 0 20px rgba(255, 255, 255, 0.2);
          }
        }
        @keyframes glowBrightFadeIn {
          from {
            box-shadow: 0 0 4px rgba(255, 255, 255, 0.1),
                        0 0 6px rgba(255, 255, 255, 0.05);
          }
          to {
            box-shadow: 0 0 6px rgba(255, 255, 255, 0.3),
                        0 0 10px rgba(255, 255, 255, 0.2),
                        0 0 14px rgba(255, 255, 255, 0.15);
          }
        }
        .glow-border-bright {
          animation: glowBrightFadeIn 0.8s ease-out forwards,
                     glowBrightPulse 2s ease-in-out 0.8s infinite;
          transition: border-color 0.6s ease-in-out;
        }

        .chip, .history-item {
          transition: transform 120ms ease, background-color 120ms ease, border-color 120ms ease;
        }
        .chip:hover, .history-item:hover {
          transform: translateY(-1px);
        }
        .chip:active, .history-item:active {
          transform: translateY(0px) scale(0.99);
        }
      `}</style>
    </main>
  );
}

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
  const [conversationHistory, setConversationHistory] = useState<Array<{question: string; answer: string; citations: Citation[]}>>([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>(SUGGESTED_QUESTIONS);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [expandedTurns, setExpandedTurns] = useState<Set<number>>(new Set());
  const [isFocused, setIsFocused] = useState(false);
  const [provider, setProvider] = useState<"openai" | "together">("openai");
  const [compareMode, setCompareMode] = useState(false);
  const [streamMode, setStreamMode] = useState(true);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [streamingProvider, setStreamingProvider] = useState<string | null>(null);
  const [streamingComparison, setStreamingComparison] = useState<{
    openai: { text: string; complete: boolean; response: AskResponse | null; error: string | null };
    together: { text: string; complete: boolean; response: AskResponse | null; error: string | null };
  }>({
    openai: { text: "", complete: false, response: null, error: null },
    together: { text: "", complete: false, response: null, error: null },
  });

  const [pdfOpen, setPdfOpen] = useState(false);
  const [pdfPage, setPdfPage] = useState<number>(1);
  const [pdfQuote, setPdfQuote] = useState<string>("");

  const [pdfSearchText, setPdfSearchText] = useState<string>("");
  const pdfIframeRef = useRef<HTMLIFrameElement | null>(null);

  function openPdfAt(page: number, quote: string, searchText?: string) {
    setPdfPage(page || 1);
    setPdfQuote(quote || "");
    // Extract searchable text from quote (first 50 chars, remove quotes and special chars)
    const searchableText = searchText || quote.replace(/["'`]/g, '').substring(0, 50).trim();
    setPdfSearchText(searchableText);
    setPdfOpen(true);
    
    // Try to search in PDF after a short delay (for PDF.js viewers)
    setTimeout(() => {
      try {
        const iframe = pdfIframeRef.current;
        if (iframe && iframe.contentWindow) {
          // Try to trigger PDF.js search if available
          const pdfWindow = iframe.contentWindow as any;
          if (pdfWindow.PDFViewerApplication) {
            // PDF.js viewer is available
            pdfWindow.PDFViewerApplication.findController.executeCommand('find', {
              query: searchableText,
              highlightAll: true,
              caseSensitive: false,
              entireWord: false,
            });
          } else if (pdfWindow.find) {
            // Native browser find
            pdfWindow.find(searchableText);
          }
        }
      } catch (e) {
        console.log('PDF search not available:', e);
      }
    }, 500);
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

  // Update suggested questions when conversation history changes
  useEffect(() => {
    if (conversationHistory.length === 0) {
      setSuggestedQuestions(SUGGESTED_QUESTIONS);
    }
  }, [conversationHistory.length]);

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

  function addToConversationHistory(question: string, answer: string, citations: Citation[] = []) {
    setConversationHistory((prev) => {
      const newHistory = [...prev, { question, answer, citations }];
      // Keep only last 10 turns (5 Q&A pairs) to avoid token limits
      const updated = newHistory.slice(-10);
      // Update suggested questions after adding to history
      setTimeout(() => updateSuggestedQuestions(question, answer), 100);
      return updated;
    });
  }

  async function updateSuggestedQuestions(lastQuestion?: string, lastAnswer?: string) {
    // If no history, use default questions
    if (conversationHistory.length === 0 && !lastQuestion) {
      setSuggestedQuestions(SUGGESTED_QUESTIONS);
      return;
    }

    setLoadingSuggestions(true);
    try {
      const historyToSend = lastQuestion && lastAnswer 
        ? [...conversationHistory, { question: lastQuestion, answer: lastAnswer }]
        : conversationHistory;

      const res = await fetch(`${API_BASE}/suggest-questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_history: historyToSend.map(t => ({ question: t.question, answer: t.answer })),
          last_answer: lastAnswer || (conversationHistory.length > 0 ? conversationHistory[conversationHistory.length - 1].answer : null),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.questions && Array.isArray(data.questions)) {
          setSuggestedQuestions(data.questions);
        }
      }
    } catch (err) {
      console.error("Failed to fetch suggested questions:", err);
      // Keep current suggestions on error
    } finally {
      setLoadingSuggestions(false);
    }
  }

  function clearConversation() {
    setConversationHistory([]);
    setSuggestedQuestions(SUGGESTED_QUESTIONS); // Reset to default questions
    setExpandedTurns(new Set());
    setData(null);
    setComparisonData(null);
    setStreamingAnswer("");
    setStreamingProvider(null);
    setStreamingComparison({
      openai: { text: "", complete: false, response: null, error: null },
      together: { text: "", complete: false, response: null, error: null },
    });
  }

  function toggleTurnExpansion(idx: number) {
    setExpandedTurns((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(idx)) {
        newSet.delete(idx);
      } else {
        newSet.add(idx);
      }
      return newSet;
    });
  }

  function copyConversation() {
    const conversationText = conversationHistory
      .map((turn, idx) => {
        let text = `Turn ${idx + 1}:\nQ: ${turn.question}\nA: ${turn.answer}\n`;
        if (turn.citations && turn.citations.length > 0) {
          text += `\nSources (${turn.citations.length}):\n`;
          turn.citations.forEach((cit, citIdx) => {
            text += `  ${citIdx + 1}. Page ${cit.page}: "${cit.quote}"\n`;
          });
        }
        return text;
      })
      .join('\n---\n\n');
    
    navigator.clipboard.writeText(conversationText).then(() => {
      // Show a brief success message (you could add a toast notification here)
      alert('Conversation copied to clipboard!');
    }).catch((err) => {
      console.error('Failed to copy:', err);
      alert('Failed to copy conversation');
    });
  }

  async function exportConversationAsPDF() {
    try {
      // Dynamic import of jsPDF to avoid SSR issues
      const { jsPDF } = await import('jspdf');
      
      const doc = new jsPDF();
      let yPos = 20;
      const pageHeight = doc.internal.pageSize.height;
      const margin = 20;
      const lineHeight = 7;
      const maxWidth = doc.internal.pageSize.width - 2 * margin;

      // Title
      doc.setFontSize(16);
      doc.setFont('helvetica', 'bold');
      doc.text('Conversation History', margin, yPos);
      yPos += 10;

      // Date
      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.text(`Generated: ${new Date().toLocaleString()}`, margin, yPos);
      yPos += 10;

      // Conversation turns
      doc.setFontSize(12);
      conversationHistory.forEach((turn, idx) => {
        // Check if we need a new page
        if (yPos > pageHeight - 40) {
          doc.addPage();
          yPos = 20;
        }

        // Turn number
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(11);
        doc.text(`Turn ${idx + 1}`, margin, yPos);
        yPos += lineHeight;

        // Question
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        const questionLines = doc.splitTextToSize(`Q: ${turn.question}`, maxWidth);
        doc.text(questionLines, margin, yPos);
        yPos += questionLines.length * lineHeight + 3;

        // Answer
        doc.setFont('helvetica', 'normal');
        const answerLines = doc.splitTextToSize(`A: ${turn.answer}`, maxWidth);
        doc.text(answerLines, margin, yPos);
        yPos += answerLines.length * lineHeight + 3;

        // Citations if available
        if (turn.citations && turn.citations.length > 0) {
          if (yPos > pageHeight - 30) {
            doc.addPage();
            yPos = 20;
          }
          doc.setFont('helvetica', 'bold');
          doc.setFontSize(9);
          doc.text(`Sources (${turn.citations.length}):`, margin, yPos);
          yPos += lineHeight;
          doc.setFont('helvetica', 'normal');
          turn.citations.forEach((cit, citIdx) => {
            if (yPos > pageHeight - 20) {
              doc.addPage();
              yPos = 20;
            }
            const citText = `  ${citIdx + 1}. Page ${cit.page}: "${cit.quote.substring(0, 60)}${cit.quote.length > 60 ? '...' : ''}"`;
            const citLines = doc.splitTextToSize(citText, maxWidth - 10);
            doc.text(citLines, margin + 5, yPos);
            yPos += citLines.length * lineHeight;
          });
          yPos += 5;
        }

        // Separator (if not last)
        if (idx < conversationHistory.length - 1) {
          if (yPos > pageHeight - 20) {
            doc.addPage();
            yPos = 20;
          }
          doc.setDrawColor(200, 200, 200);
          doc.line(margin, yPos, doc.internal.pageSize.width - margin, yPos);
          yPos += 5;
        }
      });

      // Save the PDF
      doc.save(`conversation-${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (error) {
      console.error('Failed to export PDF:', error);
      alert('Failed to export PDF. Make sure jsPDF is installed: npm install jspdf');
    }
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
    setStreamingAnswer("");
    setStreamingProvider(null);
    setStreamingComparison({
      openai: { text: "", complete: false, response: null, error: null },
      together: { text: "", complete: false, response: null, error: null },
    });

    const q = question.trim();
    if (!q) {
      setError("Please enter a question.");
      return;
    }

    pushHistory(q);

    // Handle streaming mode for single provider
    if (streamMode && !compareMode) {
      setLoading(true);
      try {
        // Use fetch with ReadableStream for POST (EventSource only supports GET)
        const res = await fetch(`${API_BASE}/ask/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            question: q, 
            top_k: TOP_K,
            provider: provider,
            conversation_history: conversationHistory.length > 0 ? conversationHistory.map(t => ({ question: t.question, answer: t.answer })) : [],
          }),
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`API error (${res.status}): ${text}`);
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let accumulatedText = "";

        if (!reader) {
          throw new Error("No response body");
        }

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.type === "chunk") {
                  accumulatedText += data.content;
                  console.log("Streaming chunk:", data.content);
                  
                  // Try to extract answer from partial JSON
                  try {
                    // Look for "answer":"... in the accumulated text (handle escaped quotes)
                    // More robust regex that handles partial JSON
                    const answerMatch = accumulatedText.match(/"answer"\s*:\s*"((?:[^"\\]|\\.|")*?)(?:"|$)/);
                    if (answerMatch && answerMatch[1]) {
                      // Unescape JSON string
                      let answerText = answerMatch[1]
                        .replace(/\\n/g, '\n')
                        .replace(/\\"/g, '"')
                        .replace(/\\\\/g, '\\')
                        .replace(/\\t/g, '\t')
                        .replace(/\\r/g, '\r');
                      
                      // If we're still building the answer (no closing quote yet), show what we have
                      if (!accumulatedText.includes('"answer"') || accumulatedText.indexOf('"answer"') < accumulatedText.lastIndexOf('"')) {
                        setStreamingAnswer(answerText);
                        console.log("Extracted answer so far:", answerText.substring(0, 50) + "...");
                      } else {
                        setStreamingAnswer(answerText);
                      }
                    } else {
                      // Show raw JSON being built (so user sees something happening)
                      // But only show a preview to avoid overwhelming
                      const preview = accumulatedText.length > 200 
                        ? accumulatedText.substring(0, 200) + "..." 
                        : accumulatedText;
                      setStreamingAnswer("Building response...\n\n" + preview);
                    }
                  } catch (e) {
                    // If parsing fails, show accumulated text preview
                    const preview = accumulatedText.length > 200 
                      ? accumulatedText.substring(0, 200) + "..." 
                      : accumulatedText;
                    setStreamingAnswer("Building response...\n\n" + preview);
                    console.error("Error extracting answer:", e);
                  }
                } else if (data.type === "complete") {
                  console.log("Streaming complete, received full response");
                  const response = data.response as AskResponse;
                  setData(response);
                  setStreamingAnswer("");
                  setStreamingProvider(response.provider || null);
                  addToConversationHistory(q, response.answer, response.citations || []);
                } else if (data.type === "error") {
                  console.error("Streaming error:", data.message);
                  throw new Error(data.message || "Streaming error");
                }
              } catch (e) {
                console.error("Error parsing SSE data:", e, "Line:", line);
              }
            } else if (line.trim()) {
              // Log non-data lines for debugging
              console.log("Non-data line:", line);
            }
          }
        }
        console.log("Streaming finished, total accumulated:", accumulatedText.length, "chars");
      } catch (err: any) {
        console.error("Streaming error:", err);
        setError(err?.message ?? "Something went wrong.");
      } finally {
        setLoading(false);
      }
      return;
    }

    // Handle streaming mode for comparison
    if (streamMode && compareMode) {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/ask/compare/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            question: q, 
            top_k: TOP_K,
            conversation_history: conversationHistory.length > 0 ? conversationHistory.map(t => ({ question: t.question, answer: t.answer })) : [],
          }),
        });

        if (!res.ok) {
          const text = await res.text();
          throw new Error(`API error (${res.status}): ${text}`);
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        if (!reader) {
          throw new Error("No response body");
        }

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.type === "chunk") {
                  const provider = data.provider as "openai" | "together";
                  setStreamingComparison(prev => {
                    const updated = { ...prev };
                    updated[provider].text += data.content;
                    // Try to extract answer
                    try {
                      const answerMatch = updated[provider].text.match(/"answer"\s*:\s*"((?:[^"\\]|\\.|")*?)(?:"|$)/);
                      if (answerMatch && answerMatch[1]) {
                        const answerText = answerMatch[1]
                          .replace(/\\n/g, '\n')
                          .replace(/\\"/g, '"')
                          .replace(/\\\\/g, '\\')
                          .replace(/\\t/g, '\t')
                          .replace(/\\r/g, '\r');
                        updated[provider].text = answerText;
                      }
                    } catch {}
                    return updated;
                  });
                } else if (data.type === "provider_complete") {
                  const provider = data.provider as "openai" | "together";
                  const response = data.response as AskResponse;
                  setStreamingComparison(prev => ({
                    ...prev,
                    [provider]: { ...prev[provider], complete: true, response },
                  }));
                } else if (data.type === "complete") {
                  const responses = data.responses as AskResponse[];
                  setComparisonData({
                    question: data.question,
                    responses,
                  });
                  setStreamingComparison({
                    openai: { text: "", complete: false, response: null, error: null },
                    together: { text: "", complete: false, response: null, error: null },
                  });
                  // For comparison, use the first response's answer for conversation history
                  if (responses && responses.length > 0) {
                    addToConversationHistory(q, responses[0].answer, responses[0].citations || []);
                  }
                } else if (data.type === "error") {
                  throw new Error(data.message || "Streaming error");
                }
              } catch (e) {
                console.error("Error parsing SSE data:", e);
              }
            }
          }
        }
      } catch (err: any) {
        console.error("Streaming comparison error:", err);
        setError(err?.message ?? "Network error. Check console for details.");
        // Try to show partial results if any
        const partialResponses = [
          streamingComparison.openai.response,
          streamingComparison.together.response,
        ].filter(r => r !== null) as AskResponse[];
        if (partialResponses.length > 0) {
          setComparisonData({
            question: q,
            responses: partialResponses,
          });
        }
      } finally {
        setLoading(false);
      }
      return;
    }

    // Non-streaming mode (existing logic)
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
          conversation_history: conversationHistory.length > 0 ? conversationHistory.map(t => ({ question: t.question, answer: t.answer })) : [],
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error (${res.status}): ${text}`);
      }

      if (compareMode) {
        const json = (await res.json()) as ComparisonResponse;
        setComparisonData(json);
        // For comparison, use the first response's answer for conversation history
        if (json.responses && json.responses.length > 0) {
          addToConversationHistory(q, json.responses[0].answer, json.responses[0].citations || []);
        }
      } else {
        const json = (await res.json()) as AskResponse;
        setData(json);
        addToConversationHistory(q, json.answer, json.citations || []);
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
            <div className="absolute top-0 right-0 flex items-center gap-3">
              {conversationHistory.length > 0 && (
                <button
                  onClick={clearConversation}
                  className="inline-flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-900/80 hover:text-zinc-100 transition-colors"
                  title="Start a new conversation"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  New Conversation
                </button>
              )}
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
            {/* Conversation History */}
            {conversationHistory.length > 0 && (
              <section className="mb-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                <div className="mb-4 flex items-center justify-between">
                  <div className="text-sm font-medium uppercase tracking-wide text-zinc-400">
                    Conversation History ({conversationHistory.length} {conversationHistory.length === 1 ? 'turn' : 'turns'})
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={copyConversation}
                      className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors flex items-center gap-1"
                      title="Copy conversation"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      Copy
                    </button>
                    <button
                      onClick={exportConversationAsPDF}
                      className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors flex items-center gap-1"
                      title="Export as PDF"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                      PDF
                    </button>
                    <button
                      onClick={clearConversation}
                      className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                      title="Clear conversation"
                    >
                      Clear
                    </button>
                  </div>
                </div>
                <div className="space-y-3 max-h-[600px] overflow-y-auto">
                  {conversationHistory.map((turn, idx) => {
                    const isExpanded = expandedTurns.has(idx);
                    const answerPreview = turn.answer.length > 200 ? turn.answer.substring(0, 200) + '...' : turn.answer;
                    const showExpandButton = turn.answer.length > 200;

                    return (
                      <div key={idx} className="space-y-2 border-l-2 border-zinc-700 pl-4 py-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="text-sm font-medium text-zinc-300 mb-1">
                              <span className="text-zinc-500">Q{idx + 1}:</span> {turn.question}
                            </div>
                            <div className="text-sm text-zinc-400">
                              <span className="text-zinc-500">A:</span>{' '}
                              {isExpanded ? (
                                <span className="whitespace-pre-wrap">{turn.answer}</span>
                              ) : (
                                <span>{answerPreview}</span>
                              )}
                            </div>
                            {turn.citations && turn.citations.length > 0 && (
                              <div className="mt-2">
                                <div className="text-xs text-zinc-500 mb-1">Sources ({turn.citations.length}):</div>
                                <div className="flex flex-wrap gap-1">
                                  {turn.citations.map((citation, citIdx) => (
                                    <button
                                      key={citIdx}
                                      onClick={() => openPdfAt(citation.page, citation.quote, citation.quote)}
                                      className="text-xs px-2 py-1 rounded border border-zinc-700 bg-zinc-900/40 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
                                      title={`Page ${citation.page}: ${citation.quote}`}
                                    >
                                      Pg {citation.page}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                        {showExpandButton && (
                          <button
                            onClick={() => toggleTurnExpansion(idx)}
                            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1"
                          >
                            {isExpanded ? (
                              <>
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                </svg>
                                Show less
                              </>
                            ) : (
                              <>
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                                Show full answer
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

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
                    <label className="flex items-center gap-2 text-sm text-zinc-300">
                      <input
                        type="checkbox"
                        checked={streamMode}
                        onChange={(e) => setStreamMode(e.target.checked)}
                        className="rounded border-zinc-700 bg-zinc-900 text-zinc-100 focus:ring-2 focus:ring-zinc-600"
                      />
                      <span>Stream response</span>
                    </label>
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

            {/* Show streaming comparison */}
            {loading && streamMode && compareMode && (
              <section className="mt-6 space-y-6 fade-in">
                <div className="rounded-2xl border-2 border-green-500/50 bg-zinc-900/40 p-7 shadow-lg shadow-green-500/10">
                  <div className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-400">
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block h-2 w-2 rounded-full bg-green-400 animate-pulse"></span>
                      Streaming Comparison
                    </span>
                  </div>
                  <p className="text-lg text-zinc-300 mb-6">{question}</p>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {(["openai", "together"] as const).map((provider) => (
                      <div key={provider} className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-5">
                        <div className="mb-3 flex items-center justify-between">
                          <div className="text-sm font-medium text-zinc-200">
                            {provider === "openai" ? "OpenAI (GPT-4o-mini)" : "Together AI (Qwen2.5-72B)"}
                          </div>
                          {streamingComparison[provider].complete ? (
                            <span className="text-xs text-green-400">✓ Complete</span>
                          ) : (
                            <span className="text-xs text-yellow-400 animate-pulse">Streaming...</span>
                          )}
                        </div>
                        
                        <div className="mb-4">
                          <div className="text-xs font-medium uppercase tracking-wide text-zinc-400 mb-2">
                            Answer
                          </div>
                          <div className="text-sm leading-6 text-zinc-100 whitespace-pre-wrap min-h-[80px]">
                            {streamingComparison[provider].text || (
                              <span className="text-zinc-500 italic">Waiting for response...</span>
                            )}
                            {!streamingComparison[provider].complete && (
                              <span className="inline-block w-2 h-4 bg-green-400 ml-1 animate-pulse">|</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
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
                                onClick={() => openPdfAt(c.page, c.quote, c.quote)}
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

            {/* Show streaming answer while streaming */}
            {loading && streamMode && !compareMode && (
              <section className="mt-6 space-y-4 fade-in">
                <div className="text-xs text-zinc-500 mb-2">
                  {streamingProvider ? `Provider: ${streamingProvider} ` : ""}
                  <span className="inline-flex items-center gap-1">
                    <span className="inline-block h-2 w-2 rounded-full bg-green-400 animate-pulse"></span>
                    <span className="font-medium text-green-400">Streaming response...</span>
                  </span>
                </div>
                <div className="rounded-2xl border-2 border-green-500/50 bg-zinc-900/40 p-7 shadow-lg shadow-green-500/10">
                  <div className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-400">
                    Answer {streamingAnswer ? `(${streamingAnswer.length} characters)` : "(waiting for response...)"}
                  </div>
                  <div className="text-lg leading-8 text-zinc-100 whitespace-pre-wrap min-h-[100px]">
                    {streamingAnswer ? (
                      <>
                        {streamingAnswer}
                        <span className="inline-block w-2 h-5 bg-green-400 ml-1 animate-pulse">|</span>
                      </>
                    ) : (
                      <span className="text-zinc-500 italic">Waiting for response to start streaming...</span>
                    )}
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
                {loadingSuggestions ? (
                  <div className="flex items-center gap-2 text-sm text-zinc-400">
                    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-zinc-400 border-t-transparent"></span>
                    Generating suggestions...
                  </div>
                ) : (
                  suggestedQuestions.map((q, idx) => (
                    <button
                      key={`${q}-${idx}`}
                      type="button"
                      onClick={() => applyQuestion(q)}
                      className="chip rounded-full border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 focus:outline-none focus:ring-2 focus:ring-zinc-700 transition-colors"
                    >
                      {q}
                    </button>
                  ))
                )}
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
                  ref={pdfIframeRef}
                  title="PDF Viewer"
                  src={`${PDF_PUBLIC_PATH}#page=${pdfPage}${pdfSearchText ? `&search=${encodeURIComponent(pdfSearchText)}` : ''}`}
                  className="h-full w-full"
                />
              </div>
            </div>
            <div className="mx-auto mt-3 max-w-6xl">
              <div className="flex items-center justify-between gap-4 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2">
                <div className="text-xs text-zinc-400">
                  <span className="text-zinc-300">Tip:</span> {pdfSearchText ? (
                    <>Use Ctrl+F (Cmd+F on Mac) to search for: <span className="font-mono text-zinc-200">"{pdfSearchText.substring(0, 40)}{pdfSearchText.length > 40 ? '...' : ''}"</span></>
                  ) : (
                    <>The PDF viewer jumps to the cited page. Use Ctrl+F to search for specific text.</>
                  )}
                </div>
                {pdfSearchText && (
                  <button
                    onClick={() => {
                      try {
                        const iframe = pdfIframeRef.current;
                        if (iframe && iframe.contentWindow) {
                          const pdfWindow = iframe.contentWindow as any;
                          if (pdfWindow.find) {
                            pdfWindow.find(pdfSearchText);
                          }
                        }
                      } catch (e) {
                        console.log('Search failed:', e);
                      }
                    }}
                    className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors px-2 py-1 rounded border border-zinc-700 hover:border-zinc-600"
                  >
                    Search in PDF
                  </button>
                )}
              </div>
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

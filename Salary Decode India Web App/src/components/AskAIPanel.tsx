import { useState, useRef, useEffect } from "react";
import { askAgent, describeAiError } from "../lib/api";
import type { CtcBreakup, ChatTurn, ToolCallLog } from "../lib/types";

interface Props {
  ctcBreakup: CtcBreakup;
}

interface DisplayMessage extends ChatTurn {
  toolCalls?: ToolCallLog[];
}

const SUGGESTIONS = [
  "Why is my in-hand lower than my CTC?",
  "Is this offer's variable pay too high?",
  "What should I negotiate?",
];

export default function AskAIPanel({ ctcBreakup }: Props) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = async (question: string) => {
    if (!question.trim() || loading) return;
    const history: ChatTurn[] = messages.map(({ role, content }) => ({ role, content }));
    setMessages(prev => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const result = await askAgent(ctcBreakup, question, history);
      setMessages(prev => [...prev, { role: "assistant", content: result.answer, toolCalls: result.tool_calls }]);
    } catch (err) {
      setError(describeAiError(err, "Couldn't get a response right now. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-40">
      {open && (
        <div className="mb-3 w-[22rem] max-w-[calc(100vw-2.5rem)] h-[28rem] bg-white border border-[#E2E5F0] rounded-2xl shadow-2xl flex flex-col overflow-hidden">
          <div className="px-4 py-3 bg-[#3730A3] text-white flex items-center justify-between shrink-0">
            <div className="text-sm font-semibold" style={{ fontFamily: "Manrope, sans-serif" }}>Ask your offer anything</div>
            <button onClick={() => setOpen(false)} className="text-white/80 hover:text-white text-lg leading-none">×</button>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && (
              <div className="space-y-2">
                <p className="text-xs text-[#94A3B8]">Ask a question, or try one of these:</p>
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="block w-full text-left text-xs bg-[#F5F6FA] hover:bg-[#EEF2FF] text-[#3730A3] rounded-lg px-3 py-2 transition-colors"
                  >
                    💬 {s}
                  </button>
                ))}
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed ${
                  m.role === "user" ? "bg-[#3730A3] text-white" : "bg-[#F5F6FA] text-[#1A1D2E]"
                }`}>
                  <div className="whitespace-pre-line">{m.content}</div>
                  {m.toolCalls && m.toolCalls.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {m.toolCalls.map((t, ti) => (
                        <span key={ti} className="text-[9px] bg-white/60 text-[#3730A3] px-1.5 py-0.5 rounded-full">
                          ⚙ {t.tool}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-[#F5F6FA] rounded-2xl px-3 py-2 text-xs text-[#94A3B8]">Thinking…</div>
              </div>
            )}
            {error && <p className="text-xs text-[#DC2626]">{error}</p>}
          </div>

          <div className="p-3 border-t border-[#E2E5F0] flex gap-2 shrink-0">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") send(input); }}
              placeholder="Ask about your offer…"
              className="flex-1 px-3 py-2 bg-[#F5F6FA] border border-[#E2E5F0] rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-[#818CF8]"
            />
            <button
              onClick={() => send(input)}
              disabled={loading || !input.trim()}
              className="px-3 py-2 bg-[#3730A3] text-white rounded-xl text-xs font-semibold disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen(v => !v)}
        className="w-14 h-14 rounded-full bg-[#3730A3] text-white shadow-xl shadow-indigo-300 flex items-center justify-center text-2xl hover:bg-[#312E81] transition-all"
        aria-label="Ask AI"
      >
        {open ? "×" : "💬"}
      </button>
    </div>
  );
}

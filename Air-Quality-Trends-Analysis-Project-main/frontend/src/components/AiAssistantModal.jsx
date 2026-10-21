import React, { useState, useRef, useEffect } from "react";
import axios from "axios";

const API = import.meta.env.VITE_API_BASE ?? "";

const QUICK_PROMPTS = [
  "Why is air quality in Delhi high during winter?",
  "What precautions should I take during Diwali?",
  "Is it safe to jog outdoors if AQI is above 150?",
  "Explain the difference between PM2.5 and PM10",
];

export default function AiAssistantModal({ placeId = null, placeName = null }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      sender: "ai",
      text:
        "Hello! I am AirSense AI — your intelligent air quality assistant for India.\n\n" +
        "I can help you with:\n" +
        "• Live City AQI — \"What is the AQI in Chandigarh?\", \"Delhi air quality\", \"Mumbai pollution\"\n" +
        "• State-level AQI — \"AQI in UP?\", \"Punjab air quality\", \"Maharashtra\"\n" +
        "• AI Forecast — \"How are you predicting the 5-day forecast?\"\n" +
        "• Delhi Smog & Winter — \"Why is air quality in Delhi worse in winter?\"\n" +
        "• Festivals & Stubble — \"Diwali smog\", \"stubble burning Punjab\"\n" +
        "• Health Advice — \"N95 mask advice\", \"Is it safe to jog with AQI 150?\"\n\n" +
        "Or just ask me anything about India's air quality!",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  const MAX_QUESTIONS = 10;
  const WINDOW_DAYS = 10;
  const WINDOW_MS = WINDOW_DAYS * 24 * 60 * 60 * 1000;

  const getStoredQuota = () => {
    try {
      const storedStartTime = localStorage.getItem("airsense_query_start_time");
      const storedCount = localStorage.getItem("airsense_query_count");
      const now = Date.now();

      if (storedStartTime) {
        const startTime = parseInt(storedStartTime, 10);
        // If 10 days have elapsed since the quota window started, automatically reset
        if (now - startTime >= WINDOW_MS) {
          localStorage.setItem("airsense_query_start_time", now.toString());
          localStorage.setItem("airsense_query_count", "0");
          return { count: 0, daysLeft: WINDOW_DAYS };
        }
        const count = parseInt(storedCount, 10) || 0;
        const msRemaining = startTime + WINDOW_MS - now;
        const daysLeft = Math.max(1, Math.ceil(msRemaining / (24 * 60 * 60 * 1000)));
        return { count, daysLeft };
      }
    } catch {}
    return { count: 0, daysLeft: WINDOW_DAYS };
  };

  const [quota, setQuota] = useState(getStoredQuota);

  const handleSend = async (textToSend = null) => {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    const currentQuota = getStoredQuota();
    if (currentQuota.count >= MAX_QUESTIONS) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: `Question limit reached (10 queries per 10 days on this device). Your quota will automatically refresh in ${currentQuota.daysLeft} day${currentQuota.daysLeft > 1 ? "s" : ""}.`,
        },
      ]);
      return;
    }

    const userMsg = { sender: "user", text };
    setMessages((prev) => [...prev, userMsg]);

    const newCount = currentQuota.count + 1;
    const now = Date.now();
    try {
      if (!localStorage.getItem("airsense_query_start_time")) {
        localStorage.setItem("airsense_query_start_time", now.toString());
      }
      localStorage.setItem("airsense_query_count", newCount.toString());
    } catch {}
    setQuota(getStoredQuota());

    if (!textToSend) setInput("");
    setLoading(true);

    try {
      const res = await axios.post(`${API}/agent/chat`, {
        message: text,
        place_id: placeId,
      });

      const aiMsg = {
        sender: "ai",
        text: res.data.reply || "No response received.",
        provider: res.data.provider,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      console.error("AI assistant error:", err);
      const errorMsg =
        err?.response?.status === 429
          ? err?.response?.data?.detail || "Question limit reached (10 queries per 10 days). Quota will automatically refresh soon."
          : "Sorry, I could not connect to the AirSense AI service right now. Please try again in a moment.";
      if (err?.response?.status === 429) {
        setQuota((prev) => ({ ...prev, count: MAX_QUESTIONS }));
      }
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: errorMsg,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Trigger Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-4 sm:right-6 z-50 bg-emerald-700 hover:bg-emerald-800 text-white px-3 sm:px-4 py-3 rounded-full shadow-lg flex items-center gap-2 text-sm font-semibold transition-all transform hover:scale-105"
        >
          <span className="text-lg">&#127807;</span>
          <span className="hidden sm:inline">Ask AirSense AI</span>
          {placeName && (
            <span className="hidden sm:inline bg-emerald-800 text-[10px] px-2 py-0.5 rounded-full border border-emerald-600">
              {placeName}
            </span>
          )}
        </button>
      )}

      {/* Slide-over / Modal Chat Panel */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-xs transition-opacity">
          <div className="w-full sm:max-w-md bg-white h-full shadow-2xl flex flex-col justify-between border-l border-gray-200">
            {/* Header */}
            <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-emerald-50/60">
              <div className="flex items-center gap-2">
                <span className="text-xl">&#127807;</span>
                <div>
                  <h3 className="font-bold text-gray-900 text-sm">AirSense AI Assistant</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
                      <span>AI Online</span>
                      <span className="text-emerald-600">•</span>
                      <span>{Math.max(0, MAX_QUESTIONS - quota.count)}/{MAX_QUESTIONS} left</span>
                      {quota.count >= MAX_QUESTIONS && (
                        <span className="text-amber-800 font-semibold ml-0.5">
                          (Refreshes in {quota.daysLeft}d)
                        </span>
                      )}
                    </span>
                    {placeName && (
                      <span className="text-[10px] text-gray-500 font-medium truncate max-w-[120px]">
                        • {placeName}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-gray-400 hover:text-gray-700 text-xl font-bold w-8 h-8 rounded-full flex items-center justify-center hover:bg-gray-100"
              >
                &#x2715;
              </button>
            </div>

            {/* Messages Thread */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 text-xs sm:text-sm">
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col ${m.sender === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl p-3.5 leading-relaxed whitespace-pre-wrap ${
                      m.sender === "user"
                        ? "bg-emerald-700 text-white rounded-br-none"
                        : "bg-gray-100 text-gray-800 rounded-bl-none border border-gray-200"
                    }`}
                  >
                    {m.text}
                  </div>
                  {m.provider && (
                    <span className="text-[10px] text-gray-400 mt-1 px-1">
                      via AirSense Intelligence
                    </span>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-50 p-3 rounded-xl border border-gray-200 w-fit">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span>AirSense AI is thinking...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Quick Suggestions */}
            <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 flex gap-1.5 overflow-x-auto text-[11px]">
              {QUICK_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  disabled={loading}
                  onClick={() => handleSend(prompt)}
                  className="whitespace-nowrap px-2.5 py-1 bg-white border border-gray-200 rounded-full text-gray-700 hover:border-emerald-500 hover:text-emerald-700 transition"
                >
                  {prompt}
                </button>
              ))}
            </div>

            {/* Input Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="p-3 border-t border-gray-200 bg-white flex items-center gap-2"
            >
              <input
                type="text"
                placeholder="Ask about air quality, health, Diwali spikes..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading}
                className="flex-1 px-3 py-2.5 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-xs sm:text-sm bg-white text-gray-900"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="px-4 py-2.5 bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 text-white rounded-xl text-xs sm:text-sm font-semibold transition"
              >
                Send
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

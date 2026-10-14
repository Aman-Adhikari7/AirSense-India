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
        "Hello! I am **AirSense AI**, your environmental assistant (currently in **Offline Database Mode**).\n\n" +
        "📚 **What I can answer from our local system:**\n" +
        "• **City AQI Lookups:** *\"What is the AQI in Chandigarh?\"*, *\"Delhi air quality\"*, *\"Mohali\"*, *\"Mumbai\"*\n" +
        "• **State AQI Lookups:** *\"What is the AQI in UP?\"*, *\"Punjab\"*, *\"Haryana\"*, *\"Maharashtra\"*\n" +
        "• **AI Forecast Models:** *\"How are you predicting the 5-day forecast?\"*\n" +
        "• **Winter Smog & Stubble:** *\"Why is air quality in Delhi high during winter?\"*\n" +
        "• **Health Precautions:** *\"N95 mask advice\"*, *\"Safe jogging AQI\"*, *\"Diwali precautions\"*\n\n" +
        "💡 *Tip: For open-ended conversation like ChatGPT or Grok, add a free Groq key (`LLM_API_KEY`) to `backend/.env`!*",
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
  const todayKey = new Date().toISOString().slice(0, 10);

  const [questionCount, setQuestionCount] = useState(0);

  const resetQuestionLimit = () => {
    setQuestionCount(0);
    try {
      localStorage.setItem("airsense_query_count", "0");
      localStorage.setItem("airsense_query_date", todayKey);
    } catch {}
  };

  const handleSend = async (textToSend = null) => {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    if (questionCount >= MAX_QUESTIONS) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: "⚠️ **Daily Device Limit Reached:** You have reached your limit of 10 free AI questions on this device for today. The limit resets at midnight, or you can log in for unlimited access.",
        },
      ]);
      return;
    }

    const userMsg = { sender: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    
    const newCount = questionCount + 1;
    setQuestionCount(newCount);
    try {
      localStorage.setItem("airsense_query_date", todayKey);
      localStorage.setItem("airsense_query_count", newCount.toString());
    } catch {}

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
      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: "⚠️ Sorry, I could not connect to the AirSense AI service right now. Please check if the backend is running.",
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
          className="fixed bottom-6 right-6 z-50 bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-3 rounded-full shadow-lg flex items-center gap-2 text-sm font-semibold transition-all transform hover:scale-105"
        >
          <span className="text-lg">🌿</span>
          <span>Ask AirSense AI</span>
          {placeName && (
            <span className="bg-emerald-800 text-[10px] px-2 py-0.5 rounded-full border border-emerald-600">
              {placeName}
            </span>
          )}
        </button>
      )}

      {/* Slide-over / Modal Chat Panel */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-xs transition-opacity">
          <div className="w-full max-w-md bg-white h-full shadow-2xl flex flex-col justify-between border-l border-gray-200">
            {/* Header */}
            <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-emerald-50/60">
              <div className="flex items-center gap-2">
                <span className="text-xl">🌿</span>
                <div>
                  <h3 className="font-bold text-gray-900 text-sm">AirSense AI Assistant</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                      <span>{MAX_QUESTIONS - questionCount} / {MAX_QUESTIONS} left</span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          resetQuestionLimit();
                        }}
                        className="ml-0.5 text-[9px] bg-emerald-200 hover:bg-emerald-300 text-emerald-900 px-1 py-0.2 rounded font-semibold transition"
                        title="Reset daily question limit"
                      >
                        Reset
                      </button>
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
                ✕
              </button>
            </div>

            {/* Offline Mode Banner */}
            <div className="bg-amber-50 border-b border-amber-200 px-3.5 py-2 text-[11px] text-amber-900 flex items-start gap-2">
              <span className="text-amber-600 text-sm leading-none mt-0.5">⚠️</span>
              <div className="leading-tight">
                <span className="font-bold text-amber-950">Offline Database Mode:</span> Answering from local 111-city AQI database & environmental models. For full conversational AI (like ChatGPT / Grok), connect a free Groq key in <code className="bg-amber-100 text-amber-950 px-1 py-0.5 rounded font-mono text-[10px]">backend/.env</code>.
              </div>
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
                      via {m.provider}
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

import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../api/axios.client";
import Spinner from "../components/Spinner";

export default function Chat() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialCourseId = searchParams.get("course");
  const initialSessionId = searchParams.get("session");

  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState(false);
  const [courses, setCourses] = useState([]);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    api.get("/courses").then((res) => setCourses(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (initialSessionId) {
      loadExistingSession(initialSessionId);
    } else if (initialCourseId) {
      createNewSession(initialCourseId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCourseId, initialSessionId]);

  const loadExistingSession = async (sessionId) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get(`/chat/sessions/${sessionId}`);
      setSession({ id: res.data.id, course_id: res.data.course_id, course_title: res.data.course_title, title: res.data.title });
      setMessages(res.data.messages || []);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در بارگذاری گفتگو");
    } finally {
      setLoading(false);
    }
  };

  const createNewSession = async (courseId) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/chat/sessions", { course_id: Number(courseId) });
      setSession(res.data);
      setMessages([]);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ایجاد گفتگو");
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading || !session) return;

    const userMsg = { id: `temp-${Date.now()}`, role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const res = await api.post(`/chat/sessions/${session.id}/messages`, {
        content: userMsg.content,
      });
      setMessages((prev) => [...prev, res.data]);
      setConnectionError(false); // reset on success
    } catch (err) {
      const status = err.response?.status;
      if (status === 502) {
        setConnectionError(true);
        setError(err.response?.data?.detail || "ارتباط با مدل هوش مصنوعی برقرار نشد.");
      } else {
        setError(err.response?.data?.detail || "خطا در دریافت پاسخ");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  if (!initialCourseId && !initialSessionId) {
    return (
      <div className="flex h-64 flex-col items-center justify-center space-y-4">
        <p className="text-slate-500 dark:text-slate-400">برای شروع گفتگو، ابتدا یک درس را انتخاب کنید.</p>
        <button onClick={() => navigate("/dashboard")} className="btn-primary">
          انتخاب درس
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col">
      {/* Header */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">
            {session ? `گفتگو: ${session.course_title}` : "گفتگو با دستیار هوشمند"}
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            پاسخ‌ها فقط بر اساس منابع درسی بارگذاری‌شده تولید می‌شوند.
          </p>
        </div>
        <select
          value={session?.course_id || ""}
          onChange={(e) => {
            if (e.target.value) createNewSession(e.target.value);
          }}
          className="input-field w-full sm:w-56"
        >
          <option value="" disabled>
            تغییر درس
          </option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title} ({c.code})
            </option>
          ))}
        </select>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
        {messages.length === 0 && !loading && (
          <div className="mt-20 text-center">
            <span className="text-5xl">🤖</span>
            <h2 className="mt-4 text-lg font-semibold text-slate-700 dark:text-slate-200">چه سؤالی از منابع درسی دارید؟</h2>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              می‌توانید درباره مفاهیم، تمرین‌ها و نمونه سؤالات درس بپرسید.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-start" : "justify-end"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "border border-slate-200 bg-slate-50 text-slate-800 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              }`}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>

              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 border-t border-slate-200 pt-2 dark:border-slate-600">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">منابع:</p>
                  <ul className="mt-1 space-y-1">
                    {msg.sources.map((src, i) => (
                      <li key={i} className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                        <span>📄</span>
                        <span className="truncate">{src.filename}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-end">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-600 dark:bg-slate-700">
              <Spinner size="sm" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {connectionError && (
        <div className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
          ⚠️ اتصال به مدل هوش مصنوعی برقرار نشد. لطفاً اتصال اینترنت، سهمیه API یا کلید را بررسی کنید و دوباره تلاش کنید.
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{error}</div>
      )}

      {/* Input */}
      <form onSubmit={handleSend} className="mt-4 flex gap-3">
        <input
          type="text"
          className="input-field"
          placeholder="سؤال خود را بنویسید..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading || !session}
        />
        <button type="submit" className="btn-primary" disabled={loading || !session || !input.trim()}>
          ارسال
        </button>
      </form>
    </div>
  );
}
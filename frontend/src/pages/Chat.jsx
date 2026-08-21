import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../api/axios.client";
import Spinner from "../components/Spinner";
import MarkdownRenderer from "../components/MarkdownRenderer";
import { MAX_IMAGE_BYTES, dedupeSources, readFileAsDataURL } from "../utils/chat";

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
  const [attachments, setAttachments] = useState([]);

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  // Guards the mount effect so it runs once per distinct course/session key,
  // preventing the infinite loop caused by our own URL navigation.
  const handledRef = useRef(null);

  useEffect(() => {
    api.get("/courses").then((res) => setCourses(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const key = initialSessionId
      ? `session:${initialSessionId}`
      : initialCourseId
      ? `course:${initialCourseId}`
      : null;
    if (!key || handledRef.current === key) return;
    handledRef.current = key;

    if (initialSessionId) {
      loadExistingSession(initialSessionId);
    } else if (initialCourseId) {
      // Draft state — do NOT create a DB session yet. It is created lazily on
      // the user's first message.
      const course = courses.find((c) => String(c.id) === String(initialCourseId));
      setSession({
        id: null,
        course_id: Number(initialCourseId),
        course_title: course?.title || "گفتگو با دستیار هوشمند",
        title: "",
      });
      setMessages([]);
      setError("");
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

  const addFiles = async (files) => {
    const imageFiles = Array.from(files || []).filter((f) => f.type.startsWith("image/"));
    if (imageFiles.length === 0) return;

    const newAttachments = [];
    for (const file of imageFiles) {
      if (file.size > MAX_IMAGE_BYTES) {
        setError("حجم تصویر نباید بیشتر از ۱۰ مگابایت باشد.");
        continue;
      }
      try {
        const dataUrl = await readFileAsDataURL(file);
        newAttachments.push({
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          name: file.name || "paste-image.png",
          mimeType: file.type || "image/png",
          dataUrl,
        });
      } catch {
        setError("خطا در خواندن تصویر. لطفاً دوباره تلاش کنید.");
      }
    }

    if (newAttachments.length > 0) {
      setAttachments((prev) => [...prev, ...newAttachments]);
      setError("");
    }
  };

  const handleFileSelect = (e) => {
    addFiles(e.target.files);
    e.target.value = ""; // allow re-selecting the same file
  };

  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles = [];
    for (const item of items) {
      if (item.kind === "file" && item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) imageFiles.push(file);
      }
    }
    if (imageFiles.length > 0) {
      e.preventDefault(); // don't paste raw image bytes into the text input
      addFiles(imageFiles);
    }
  };

  const removeAttachment = (id) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if ((!text && attachments.length === 0) || loading || !session) return;

    const userMsg = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: text,
      image: attachments[0]?.dataUrl || null,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setAttachments([]);
    setLoading(true);
    setError("");

    try {
      let targetSession = session;

      // Lazily create the session on the first message (draft -> real session).
      if (!session.id) {
        const created = await api.post("/chat/sessions", { course_id: session.course_id });
        targetSession = created.data;
        setSession(targetSession);
        // Mark this session as handled so the mount effect won't re-fetch it.
        handledRef.current = `session:${targetSession.id}`;
        navigate(`/chat?session=${targetSession.id}`, { replace: true });
      }

      const res = await api.post(`/chat/sessions/${targetSession.id}/messages`, {
        content: userMsg.content,
        session_id: targetSession.id,
        image_data: userMsg.image || undefined,
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
            if (e.target.value) navigate(`/chat?course=${e.target.value}`, { replace: true });
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
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
              💡 می‌توانید اسکرین‌شات سؤال را با Ctrl+V / Cmd+V جای‌گذاری کنید.
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
              {msg.role === "user" ? (
                <>
                  {msg.image && (
                    <img
                      src={msg.image}
                      alt="Uploaded attachment"
                      className="max-w-xs max-h-48 rounded-lg border my-2 object-cover"
                    />
                  )}
                  {(!msg.image || !["📷 تصویر", "🖼️ تصویر"].includes(msg.content)) && (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
                  )}
                </>
              ) : (
                <MarkdownRenderer content={msg.content} sources={msg.sources} />
              )}

              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 border-t border-slate-200 pt-2 dark:border-slate-600">
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">منابع:</p>
                  <ul className="mt-1 space-y-1">
                    {dedupeSources(msg.sources).map((src, i) => (
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

      {/* Attachment previews */}
      {attachments.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-3">
          {attachments.map((att) => (
            <div key={att.id} className="relative">
              <img
                src={att.dataUrl}
                alt={att.name}
                className="h-16 w-16 rounded-lg border border-slate-300 object-cover shadow-sm dark:border-slate-600"
              />
              <button
                type="button"
                onClick={() => removeAttachment(att.id)}
                aria-label="حذف تصویر"
                className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white shadow transition hover:bg-red-600"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSend} onPaste={handlePaste} className="mt-4 flex gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={handleFileSelect}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading || !session}
          aria-label="پیوست تصویر"
          title="پیوست تصویر"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-slate-300 bg-white text-slate-500 transition hover:border-blue-400 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-300 dark:hover:border-blue-500 dark:hover:text-blue-400"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
            />
          </svg>
        </button>
        <input
          type="text"
          className="input-field"
          placeholder="سؤال خود را بنویسید... (Ctrl+V برای چسباندن تصویر)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading || !session}
        />
        <button
          type="submit"
          className="btn-primary"
          disabled={loading || !session || (!input.trim() && attachments.length === 0)}
        >
          ارسال
        </button>
      </form>
    </div>
  );
}
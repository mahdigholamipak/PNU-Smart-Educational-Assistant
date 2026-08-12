import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios.client";
import Spinner from "../components/Spinner";

export default function History() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  const loadSessions = () => {
    setLoading(true);
    api
      .get("/chat/sessions")
      .then((res) => setSessions(res.data))
      .catch(() => setError("خطا در دریافت تاریخچه گفتگوها"))
      .finally(() => setLoading(false));
  };

  useEffect(loadSessions, []);

  const openSession = async (id) => {
    setDetailLoading(true);
    setDetail(null);
    try {
      const res = await api.get(`/chat/sessions/${id}`);
      setDetail(res.data);
      setError("");
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در دریافت گفتگو");
    } finally {
      setDetailLoading(false);
    }
  };

  const deleteSession = async (id) => {
    if (!window.confirm("آیا از حذف این گفتگو مطمئن هستید؟")) return;
    try {
      await api.delete(`/chat/sessions/${id}`);
      if (detail?.id === id) setDetail(null);
      loadSessions();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در حذف گفتگو");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">تاریخچه گفتگوها</h1>
        <p className="mt-1 text-sm text-slate-500">گفتگوهای قبلی خود را مرور کنید.</p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Sessions list */}
        <div className="lg:col-span-2">
          <div className="card">
            <h2 className="mb-4 text-lg font-semibold text-slate-700">لیست گفتگوها</h2>

            {loading ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : sessions.length === 0 ? (
              <p className="text-sm text-slate-500">هنوز گفتگویی ندارید.</p>
            ) : (
              <ul className="space-y-2">
                {sessions.map((s) => (
                  <li key={s.id}>
                    <div
                      className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition hover:border-blue-300 ${
                        detail?.id === s.id ? "border-blue-400 bg-blue-50" : "border-slate-200"
                      }`}
                      onClick={() => openSession(s.id)}
                    >
                      <span>💬</span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-slate-800">{s.title}</p>
                        <p className="text-xs text-slate-500">
                          {s.course_title} • {new Date(s.created_at).toLocaleDateString("fa-IR")}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteSession(s.id);
                        }}
                        className="text-sm text-red-500 hover:text-red-700"
                        title="حذف"
                      >
                        🗑️
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Detail */}
        <div className="lg:col-span-3">
          <div className="card">
            <h2 className="mb-4 text-lg font-semibold text-slate-700">مشاهده گفتگو</h2>

            {detailLoading ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : !detail ? (
              <div className="py-12 text-center">
                <span className="text-4xl">📜</span>
                <p className="mt-3 text-sm text-slate-500">
                  برای مشاهده پیام‌ها، یک گفتگو را از لیست انتخاب کنید.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-200 pb-3">
                  <div>
                    <h3 className="font-semibold text-slate-800">{detail.title}</h3>
                    <p className="text-xs text-slate-500">
                      {detail.course_title} • {new Date(detail.created_at).toLocaleDateString("fa-IR")}
                    </p>
                  </div>
                  <button
                    onClick={() => navigate(`/chat?session=${detail.id}`)}
                    className="btn-secondary"
                  >
                    ادامه گفتگو
                  </button>
                </div>

                <div className="max-h-[60vh] space-y-4 overflow-y-auto">
                  {detail.messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex ${msg.role === "user" ? "justify-start" : "justify-end"}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                          msg.role === "user"
                            ? "bg-blue-600 text-white"
                            : "border border-slate-200 bg-slate-50 text-slate-800"
                        }`}
                      >
                        <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="mt-2 border-t border-slate-200 pt-2">
                            <p className="text-xs font-semibold text-slate-500">منابع:</p>
                            <ul className="mt-1 space-y-1">
                              {msg.sources.map((src, i) => (
                                <li key={i} className="flex items-center gap-1 text-xs text-slate-500">
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
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
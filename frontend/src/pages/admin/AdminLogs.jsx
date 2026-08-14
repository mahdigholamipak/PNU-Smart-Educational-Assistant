import { useEffect, useState } from "react";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

const levelStyles = {
  info: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  warning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

const levelLabels = {
  info: "اطلاعات",
  warning: "هشدار",
  error: "خطا",
};

export default function AdminLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [level, setLevel] = useState("");
  const [expanded, setExpanded] = useState({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState(null);

  const loadLogs = async (filterLevel = level) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get("/admin/logs", {
        params: { limit: 100, level: filterLevel || undefined },
      });
      setLogs(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در دریافت لاگ‌ها");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs("");
  }, []);

  const handleLevelChange = (e) => {
    const val = e.target.value;
    setLevel(val);
    loadLogs(val);
  };

  const handleClear = async () => {
    if (!window.confirm("همه لاگ‌های سیستم حذف شوند؟")) return;
    try {
      await api.delete("/admin/logs");
      setMessage("لاگ‌های سیستم پاک شدند");
      setLogs([]);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در پاک کردن لاگ‌ها");
    }
  };

  const toggleExpand = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyDetails = async (id, text) => {
    try {
      await navigator.clipboard.writeText(text || "");
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch (err) {
      setError("خطا در کپی متن");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">لاگ سیستم</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            خطاهای پردازش فایل، اتصال API و مشکلات وکتور/ChromaDB
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={level} onChange={handleLevelChange} className="input-field w-auto">
            <option value="">همه</option>
            <option value="info">اطلاعات</option>
            <option value="warning">هشدار</option>
            <option value="error">خطا</option>
          </select>
          <button onClick={() => loadLogs()} className="btn-secondary">تازه‌سازی</button>
          <button onClick={handleClear} className="btn-secondary !text-red-600 dark:!text-red-400">پاک‌کردن همه</button>
        </div>
      </div>

      {message && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/40 dark:text-green-300">{message}</div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{error}</div>
      )}

      <div className="card">
        {loading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : logs.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">لاگی ثبت نشده است.</p>
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {logs.map((log) => (
              <div key={log.id} className="py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${levelStyles[log.level] || levelStyles.info}`}>
                    {levelLabels[log.level] || log.level}
                  </span>
                  <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300">{log.source}</span>
                  <span className="text-sm text-slate-800 dark:text-slate-100">{log.message}</span>
                  <span className="mr-auto text-xs text-slate-400 dark:text-slate-500">
                    {log.created_at ? new Date(log.created_at).toLocaleString("fa-IR") : "-"}
                  </span>
                  {log.details && (
                    <button onClick={() => toggleExpand(log.id)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                      {expanded[log.id] ? "بستن جزئیات" : "جزئیات"}
                    </button>
                  )}
                </div>
                {expanded[log.id] && log.details && (
                  <div className="mt-2">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => copyDetails(log.id, log.details)}
                        className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {copiedId === log.id ? "کپی شد ✓" : "کپی"}
                      </button>
                    </div>
                    <pre
                      className="mt-1 overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-700 dark:bg-slate-900 dark:text-slate-300"
                      style={{ direction: "ltr", textAlign: "left", wordBreak: "break-all", whiteSpace: "pre-wrap" }}
                    >
                      {log.details}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
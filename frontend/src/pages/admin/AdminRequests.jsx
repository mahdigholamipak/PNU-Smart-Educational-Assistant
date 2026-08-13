import { useEffect, useState } from "react";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

const statusLabels = {
  pending: "در انتظار بررسی",
  approved: "تأیید شده",
  rejected: "رد شده",
};

const statusColors = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  approved: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export default function AdminRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [notes, setNotes] = useState({});

  const loadRequests = () => {
    setLoading(true);
    api
      .get("/admin/requests")
      .then((res) => setRequests(res.data))
      .catch(() => setError("خطا در دریافت درخواست‌ها"))
      .finally(() => setLoading(false));
  };

  useEffect(loadRequests, []);

  const updateStatus = async (id, status) => {
    try {
      await api.patch(`/admin/requests/${id}`, {
        status,
        admin_note: notes[id] || null,
      });
      setMessage("وضعیت درخواست به‌روزرسانی شد");
      loadRequests();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در به‌روزرسانی درخواست");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">درخواست‌های درس</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">بررسی و مدیریت درخواست‌های دانشجویان</p>
      </div>

      {message && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/40 dark:text-green-300">{message}</div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{error}</div>
      )}

      <div className="card">
        {loading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : requests.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">درخواستی ثبت نشده است.</p>
        ) : (
          <div className="space-y-4">
            {requests.map((req) => (
              <div key={req.id} className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-slate-800 dark:text-slate-100">{req.course_name}</h3>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[req.status]}`}
                      >
                        {statusLabels[req.status]}
                      </span>
                    </div>
                    {req.course_code && (
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">کد درس: {req.course_code}</p>
                    )}
                    {req.description && (
                      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{req.description}</p>
                    )}
                    <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
                      {new Date(req.created_at).toLocaleDateString("fa-IR")}
                    </p>
                  </div>
                </div>

                <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                  <input
                    type="text"
                    className="input-field flex-1"
                    placeholder="یادداشت مدیر (اختیاری)"
                    value={notes[req.id] || ""}
                    onChange={(e) => setNotes({ ...notes, [req.id]: e.target.value })}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => updateStatus(req.id, "approved")}
                      disabled={req.status === "approved"}
                      className="btn-primary !px-3 !py-1.5 text-xs"
                    >
                      تأیید
                    </button>
                    <button
                      onClick={() => updateStatus(req.id, "rejected")}
                      disabled={req.status === "rejected"}
                      className="btn-secondary !px-3 !py-1.5 text-xs text-red-600 dark:text-red-400"
                    >
                      رد
                    </button>
                  </div>
                </div>

                {req.admin_note && (
                  <p className="mt-2 rounded bg-slate-50 p-2 text-xs text-slate-500 dark:bg-slate-700 dark:text-slate-300">
                    یادداشت مدیر: {req.admin_note}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
import { useEffect, useState } from "react";
import api from "../api/axios.client";
import Spinner from "../components/Spinner";

export default function CourseRequest() {
  const [form, setForm] = useState({
    course_name: "",
    course_code: "",
    description: "",
  });
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadRequests = () => {
    setLoading(true);
    setError("");
    api
      .get("/requests/me")
      .then((res) => setRequests(res.data))
      .catch(() => setError("خطا در دریافت درخواست‌های شما"))
      .finally(() => setLoading(false));
  };

  useEffect(loadRequests, []);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setMessage("");
    setError("");
    try {
      await api.post("/requests", form);
      setMessage("درخواست شما با موفقیت ثبت شد");
      setForm({ course_name: "", course_code: "", description: "" });
      loadRequests();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ثبت درخواست");
    } finally {
      setSubmitting(false);
    }
  };

  const statusLabels = {
    pending: "در انتظار بررسی",
    approved: "تأیید شده",
    rejected: "رد شده",
  };

  const statusColors = {
    pending: "bg-yellow-100 text-yellow-800",
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">درخواست درس جدید</h1>
        <p className="mt-1 text-sm text-slate-500">
          اگر درس مورد نظر شما در سیستم موجود نیست، آن را درخواست دهید.
        </p>
      </div>

      {message && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">{message}</div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Form */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-slate-700">فرم درخواست</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label-field" htmlFor="course_name">نام درس *</label>
              <input
                id="course_name"
                name="course_name"
                type="text"
                required
                className="input-field"
                placeholder="مثال: مبانی کامپیوتر"
                value={form.course_name}
                onChange={handleChange}
              />
            </div>

            <div>
              <label className="label-field" htmlFor="course_code">کد درس</label>
              <input
                id="course_code"
                name="course_code"
                type="text"
                className="input-field"
                placeholder="مثال: 1111001"
                value={form.course_code}
                onChange={handleChange}
              />
            </div>

            <div>
              <label className="label-field" htmlFor="description">توضیحات</label>
              <textarea
                id="description"
                name="description"
                rows={4}
                className="input-field resize-none"
                placeholder="توضیحات تکمیلی درباره درس..."
                value={form.description}
                onChange={handleChange}
              />
            </div>

            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? <Spinner size="sm" /> : "ثبت درخواست"}
            </button>
          </form>
        </div>

        {/* My requests */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-slate-700">درخواست‌های من</h2>

          {loading ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : requests.length === 0 ? (
            <p className="text-sm text-slate-500">هنوز درخواستی ثبت نکرده‌اید.</p>
          ) : (
            <ul className="space-y-3">
              {requests.map((req) => (
                <li key={req.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-slate-800">{req.course_name}</p>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[req.status]}`}
                    >
                      {statusLabels[req.status]}
                    </span>
                  </div>
                  {req.course_code && (
                    <p className="mt-1 text-xs text-slate-500">کد درس: {req.course_code}</p>
                  )}
                  {req.description && (
                    <p className="mt-1 text-sm text-slate-600">{req.description}</p>
                  )}
                  {req.admin_note && (
                    <p className="mt-2 rounded bg-slate-50 p-2 text-xs text-slate-500">
                      پاسخ مدیر: {req.admin_note}
                    </p>
                  )}
                  <p className="mt-2 text-xs text-slate-400">
                    {new Date(req.created_at).toLocaleDateString("fa-IR")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
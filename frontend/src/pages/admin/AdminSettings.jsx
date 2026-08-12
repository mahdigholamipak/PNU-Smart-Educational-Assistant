import { useEffect, useState } from "react";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

export default function AdminSettings() {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadSettings = () => {
    setLoading(true);
    api
      .get("/admin/settings")
      .then((res) => setSettings(res.data))
      .catch(() => setError("خطا در دریافت تنظیمات"))
      .finally(() => setLoading(false));
  };

  useEffect(loadSettings, []);

  const getValue = (key) => {
    const setting = settings.find((s) => s.key === key);
    return setting?.value || "";
  };

  const saveSetting = async (key, value) => {
    setSaving(true);
    setMessage("");
    setError("");
    try {
      await api.put(`/admin/settings/${key}`, { value });
      setMessage("تنظیمات با موفقیت ذخیره شد");
      loadSettings();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ذخیره تنظیمات");
    } finally {
      setSaving(false);
    }
  };

  const handleGeminiSave = (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    saveSetting("gemini_api_key", formData.get("gemini_api_key") || "");
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">تنظیمات API</h1>
        <p className="mt-1 text-sm text-slate-500">مدیریت کلیدهای API مدل هوش مصنوعی</p>
      </div>

      {message && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">{message}</div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-700">Google Gemini</h2>

        <form onSubmit={handleGeminiSave} className="space-y-4">
          <div>
            <label className="label-field" htmlFor="gemini_api_key">کلید API (Gemini Token)</label>
            <input
              id="gemini_api_key"
              name="gemini_api_key"
              type="password"
              className="input-field"
              placeholder="AIza..."
              defaultValue={getValue("gemini_api_key")}
              autoComplete="off"
            />
            <p className="mt-1 text-xs text-slate-500">
              این کلید برای تولید پاسخ و ساخت بردارهای جستجو استفاده می‌شود.
            </p>
          </div>

          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? <Spinner size="sm" /> : "ذخیره کلید"}
          </button>
        </form>
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-700">سایر تنظیمات</h2>
        <div className="space-y-4">
          <div>
            <label className="label-field" htmlFor="gemini_chat_model">مدل گفتگو</label>
            <input
              id="gemini_chat_model"
              type="text"
              className="input-field"
              defaultValue={getValue("gemini_chat_model") || "gemini-1.5-flash"}
              onBlur={(e) => {
                if (e.target.value !== getValue("gemini_chat_model")) {
                  saveSetting("gemini_chat_model", e.target.value);
                }
              }}
            />
          </div>
          <div>
            <label className="label-field" htmlFor="gemini_embedding_model">مدل بردارساز</label>
            <input
              id="gemini_embedding_model"
              type="text"
              className="input-field"
              defaultValue={getValue("gemini_embedding_model") || "models/text-embedding-004"}
              onBlur={(e) => {
                if (e.target.value !== getValue("gemini_embedding_model")) {
                  saveSetting("gemini_embedding_model", e.target.value);
                }
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
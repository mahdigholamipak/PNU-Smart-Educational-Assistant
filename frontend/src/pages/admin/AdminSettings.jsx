import { useEffect, useState } from "react";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

export default function AdminSettings() {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [chatModels, setChatModels] = useState([]);
  const [embeddingModels, setEmbeddingModels] = useState([]);
  const [chatModel, setChatModel] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  const loadSettings = () => {
    setLoading(true);
    api
      .get("/admin/settings")
      .then((res) => {
        setSettings(res.data);
        const key = res.data.find((s) => s.key === "gemini_api_key")?.value || "";
        setApiKey(key);
        setChatModel(res.data.find((s) => s.key === "gemini_chat_model")?.value || "gemini-1.5-flash");
        setEmbeddingModel(res.data.find((s) => s.key === "gemini_embedding_model")?.value || "models/text-embedding-004");
      })
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

  const handleGeminiSave = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const key = formData.get("gemini_api_key") || "";
    setMessage("");
    setError("");
    try {
      await api.put("/admin/settings/gemini_api_key", { value: key });
      setApiKey(key);
      setMessage("کلید API با موفقیت ذخیره شد");
      loadSettings();
      // After saving key, try loading models
      await fetchModels(key);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ذخیره کلید");
    }
  };

  const fetchModels = async (keyOverride) => {
    setModelsLoading(true);
    setError("");
    try {
      // Temporarily save the key if provided so backend can use it
      if (keyOverride !== undefined && keyOverride !== apiKey) {
        // Do a lightweight request using the saved key; if user passes a new untested key,
        // we rely on it being saved first. For a fresh typed key, call with the saved key.
        keyOverride = null; // use saved key in DB
      }
      const res = await api.get("/admin/gemini/models");
      setChatModels(res.data.chat_models || []);
      setEmbeddingModels(res.data.embedding_models || []);
      setMessage("لیست مدل‌ها با موفقیت دریافت شد");
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در دریافت مدل‌ها");
    } finally {
      setModelsLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setMessage("");
    setError("");
    try {
      const payload = { api_key: apiKey, chat_model: chatModel, embedding_model: embeddingModel };
      const res = await api.post("/admin/gemini/test-connection", payload);
      setMessage(`ارتباط با موفقیت برقرار شد ✓ (گفتگو: ${res.data.chat_model}، بردارساز: ${res.data.embedding_model})`);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در تست ارتباط");
    } finally {
      setTesting(false);
    }
  };

  const handleModelSelect = async (type, value) => {
    if (type === "chat") {
      setChatModel(value);
      await saveSetting("gemini_chat_model", value);
    } else {
      setEmbeddingModel(value);
      await saveSetting("gemini_embedding_model", value);
    }
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
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">تنظیمات API</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">مدیریت کلیدهای API و مدل‌های هوش مصنوعی</p>
      </div>

      {message && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/40 dark:text-green-300">{message}</div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{error}</div>
      )}

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">Google Gemini</h2>

        <form onSubmit={handleGeminiSave} className="space-y-4">
          <div>
            <label className="label-field" htmlFor="gemini_api_key">کلید API (Gemini Token)</label>
            <div className="relative">
              <input
                id="gemini_api_key"
                name="gemini_api_key"
                type={showApiKey ? "text" : "password"}
                className="input-field pl-10"
                placeholder="AIza..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoComplete="off"
              />
              <button
                type="button"
                onClick={() => setShowApiKey((v) => !v)}
                className="absolute top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                style={{ left: "0.75rem" }}
                aria-label={showApiKey ? "پنهان‌کردن کلید API" : "نمایش کلید API"}
                tabIndex={-1}
              >
                {showApiKey ? (
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                  </svg>
                ) : (
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              این کلید برای تولید پاسخ و ساخت بردارهای جستجو استفاده می‌شود.
            </p>
          </div>

          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? <Spinner size="sm" /> : "ذخیره کلید"}
            </button>
            <button
              type="button"
              onClick={() => fetchModels()}
              disabled={modelsLoading || saving}
              className="btn-secondary"
            >
              {modelsLoading ? <Spinner size="sm" /> : "بارگذاری مدل‌ها"}
            </button>
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing || saving || modelsLoading}
              className="btn-secondary !border-green-500 !text-green-600 dark:!border-green-400 dark:!text-green-400"
            >
              {testing ? (
                <span className="flex items-center gap-2">
                  <Spinner size="sm" /> در حال تست...
                </span>
              ) : (
                "تست ارتباط"
              )}
            </button>
          </div>
        </form>
      </div>

      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">سایر تنظیمات — انتخاب مدل‌ها</h2>

        <div className="space-y-4">
          <div>
            <label className="label-field" htmlFor="gemini_chat_model">مدل گفتگو</label>
            {chatModels.length > 0 ? (
              <select
                id="gemini_chat_model"
                className="input-field"
                value={chatModel}
                onChange={(e) => handleModelSelect("chat", e.target.value)}
              >
                {chatModels.map((m) => (
                  <option key={m.id} value={m.id}>{m.display}</option>
                ))}
              </select>
            ) : (
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
            )}
            {chatModels.length === 0 && (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                برای لیست مدل‌ها، ابتدا کلید API را ذخیره و «بارگذاری مدل‌ها» را بزنید.
              </p>
            )}
          </div>
          <div>
            <label className="label-field" htmlFor="gemini_embedding_model">مدل بردارساز</label>
            {embeddingModels.length > 0 ? (
              <select
                id="gemini_embedding_model"
                className="input-field"
                value={embeddingModel}
                onChange={(e) => handleModelSelect("embedding", e.target.value)}
              >
                {embeddingModels.map((m) => (
                  <option key={m.id} value={m.id}>{m.display}</option>
                ))}
              </select>
            ) : (
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
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
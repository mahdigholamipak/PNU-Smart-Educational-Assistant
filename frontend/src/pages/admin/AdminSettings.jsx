import { useEffect, useState } from "react";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

/**
 * Renders one API key's usage as a parent row (masked key + combined totals)
 * followed by nested per-model sub-rows, similar to Google AI Studio's
 * per-key/per-model monitoring breakdown.
 */
function UsageGroup({ group }) {
  const [expanded, setExpanded] = useState(true);
  const models = group.models || [];

  return (
    <>
      <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-600 dark:bg-slate-700/40">
        <td className="px-3 py-2">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
            aria-expanded={expanded}
          >
            <svg
              className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-0" : "-rotate-90"}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
            <span className="font-mono text-xs text-slate-600 dark:text-slate-300" dir="ltr">
              {group.api_key_masked}
            </span>
          </button>
        </td>
        <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
          {models.length} مدل
        </td>
        <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-100">
          {Number(group.total_requests || 0).toLocaleString("fa-IR")}
        </td>
        <td className="px-3 py-2 font-semibold text-slate-800 dark:text-slate-100">
          {Number(group.total_tokens_used || 0).toLocaleString("fa-IR")}
        </td>
        <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
          {group.updated_at ? new Date(group.updated_at).toLocaleString("fa-IR") : "—"}
        </td>
      </tr>
      {expanded &&
        (models.length === 0 ? (
          <tr className="border-b border-slate-100 dark:border-slate-700">
            <td className="px-3 py-2" />
            <td className="px-3 py-2 pr-10 text-xs italic text-slate-400 dark:text-slate-500">
              هنوز مصرفی برای این کلید ثبت نشده است.
            </td>
            <td className="px-3 py-2 text-xs text-slate-400 dark:text-slate-500">۰</td>
            <td className="px-3 py-2 text-xs text-slate-400 dark:text-slate-500">۰</td>
            <td />
          </tr>
        ) : (
          models.map((m, j) => (
            <tr key={j} className="border-b border-slate-100 dark:border-slate-700">
              <td className="px-3 py-2" />
              <td className="px-3 py-2 pr-10 text-slate-700 dark:text-slate-200">{m.model}</td>
              <td className="px-3 py-2 text-slate-700 dark:text-slate-200">
                {Number(m.total_requests || 0).toLocaleString("fa-IR")}
              </td>
              <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-100">
                {Number(m.total_tokens_used || 0).toLocaleString("fa-IR")}
              </td>
              <td className="px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                {m.updated_at ? new Date(m.updated_at).toLocaleString("fa-IR") : "—"}
              </td>
            </tr>
          ))
        ))}
    </>
  );
}

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
  const [apiKeys, setApiKeys] = useState([""]);
  const [showKeys, setShowKeys] = useState([]);
  const [usage, setUsage] = useState([]);
  const [usageLoading, setUsageLoading] = useState(false);

  const loadSettings = () => {
    setLoading(true);
    api
      .get("/admin/settings")
      .then((res) => {
        setSettings(res.data);
        const raw = res.data.find((s) => s.key === "gemini_api_key")?.value || "";
        const keys = raw
          .split("\n")
          .map((k) => k.trim())
          .filter(Boolean);
        setApiKeys(keys.length ? keys : [""]);
        setShowKeys(keys.map(() => false));
        setChatModel(res.data.find((s) => s.key === "gemini_chat_model")?.value || "gemini-1.5-flash");
        setEmbeddingModel(res.data.find((s) => s.key === "gemini_embedding_model")?.value || "models/text-embedding-004");
      })
      .catch(() => setError("خطا در دریافت تنظیمات"))
      .finally(() => setLoading(false));
  };

  useEffect(loadSettings, []);

  const loadUsage = () => {
    setUsageLoading(true);
    api
      .get("/admin/api-usage")
      .then((res) => setUsage(Array.isArray(res.data) ? res.data : []))
      .catch(() => setUsage([]))
      .finally(() => setUsageLoading(false));
  };

  useEffect(() => {
    loadUsage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const handleApiKeyChange = (idx, value) => {
    setApiKeys((prev) => {
      const next = [...prev];
      next[idx] = value;
      return next;
    });
  };

  const handleAddKey = () => {
    setApiKeys((prev) => [...prev, ""]);
    setShowKeys((prev) => [...prev, false]);
  };

  const handleRemoveKey = (idx) => {
    setApiKeys((prev) => prev.filter((_, i) => i !== idx));
    setShowKeys((prev) => prev.filter((_, i) => i !== idx));
  };

  const toggleShowKey = (idx) => {
    setShowKeys((prev) => prev.map((v, i) => (i === idx ? !v : v)));
  };

  const handleGeminiSave = async (e) => {
    e.preventDefault();
    const value = apiKeys.map((k) => k.trim()).filter(Boolean).join("\n");
    setMessage("");
    setError("");
    try {
      await api.put("/admin/settings/gemini_api_key", { value });
      setMessage("کلید API با موفقیت ذخیره شد");
      loadSettings();
      loadUsage();
      await fetchModels(value);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ذخیره کلید");
    }
  };

  const fetchModels = async (keyOverride) => {
    setModelsLoading(true);
    setError("");
    try {
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
      const payload = { api_key: apiKeys.map((k) => k.trim()).filter(Boolean).join("\n"), chat_model: chatModel, embedding_model: embeddingModel };
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
            <label className="label-field">کلیدهای API (Gemini Token)</label>
            <div className="space-y-2">
              {apiKeys.map((key, idx) => (
                <div key={idx} className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      name={`gemini_api_key_${idx}`}
                      type={showKeys[idx] ? "text" : "password"}
                      className="input-field pl-10"
                      placeholder="AIza..."
                      value={key}
                      onChange={(e) => handleApiKeyChange(idx, e.target.value)}
                      autoComplete="off"
                      dir="ltr"
                    />
                    <button
                      type="button"
                      onClick={() => toggleShowKey(idx)}
                      className="absolute top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                      style={{ left: "0.75rem" }}
                      aria-label={showKeys[idx] ? "پنهان‌کردن کلید API" : "نمایش کلید API"}
                      tabIndex={-1}
                    >
                      {showKeys[idx] ? (
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
                  <button
                    type="button"
                    onClick={() => handleRemoveKey(idx)}
                    disabled={apiKeys.length <= 1}
                    className="btn-secondary !px-2 !py-1 text-xs text-red-600 dark:text-red-400 disabled:cursor-not-allowed disabled:text-slate-300 dark:disabled:text-slate-600"
                  >
                    حذف
                  </button>
                </div>
              ))}
            </div>
            <button type="button" onClick={handleAddKey} className="mt-2 text-xs text-blue-600 hover:underline dark:text-blue-400">
              + افزودن کلید API دیگر
            </button>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              برای جلوگیری از محدودیت نرخ (429)، چند کلید API اضافه کنید. سیستم به‌صورت خودکار بین کلیدها جابه‌جا می‌شود.
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
        <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">مانیتورینگ مصرف API</h2>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
          تعداد درخواست‌ها و توکن‌های مصرف‌شده به‌ازای هر کلید API.
        </p>

        <div className="mb-3 flex items-center justify-end">
          <button
            type="button"
            onClick={loadUsage}
            disabled={usageLoading}
            className="btn-secondary !px-3 !py-1 text-xs"
          >
            {usageLoading ? <Spinner size="sm" /> : "به‌روزرسانی"}
          </button>
        </div>

        {usage.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            هنوز مصرفی ثبت نشده است. پس از اولین درخواست به مدل هوش مصنوعی، آمار اینجا نمایش داده می‌شود.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-right dark:border-slate-600">
                  <th className="px-3 py-2 font-semibold text-slate-700 dark:text-slate-200">کلید API</th>
                  <th className="px-3 py-2 font-semibold text-slate-700 dark:text-slate-200">مدل</th>
                  <th className="px-3 py-2 font-semibold text-slate-700 dark:text-slate-200">تعداد درخواست‌ها</th>
                  <th className="px-3 py-2 font-semibold text-slate-700 dark:text-slate-200">توکن مصرفی</th>
                  <th className="px-3 py-2 font-semibold text-slate-700 dark:text-slate-200">آخرین به‌روزرسانی</th>
                </tr>
              </thead>
              <tbody>
                {usage.map((group, i) => (
                  <UsageGroup key={i} group={group} />
                ))}
              </tbody>
            </table>
          </div>
        )}
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
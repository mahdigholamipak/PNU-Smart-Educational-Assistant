import { useEffect, useRef, useState } from "react";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

const statusLabels = {
  processing: "در حال پردازش",
  ready: "آماده",
  failed: "ناموفق",
};

const statusColors = {
  processing: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  ready: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export default function AdminResources() {
  const [courses, setCourses] = useState([]);
  const [resources, setResources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [reprocessingId, setReprocessingId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Upload form (Task 1)
  const [selectedCourse, setSelectedCourse] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  // Course form
  const [courseForm, setCourseForm] = useState({ code: "", title: "", description: "" });

  // Chunk viewer state (Task 8)
  const [chunkModal, setChunkModal] = useState(null);
  const [chunkEdits, setChunkEdits] = useState({});

  const loadData = async () => {
    setLoading(true);
    setError("");
    try {
      const [coursesRes, resourcesRes] = await Promise.all([
        api.get("/admin/courses"),
        api.get("/admin/resources"),
      ]);
      setCourses(coursesRes.data);
      setResources(resourcesRes.data);
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در دریافت اطلاعات");
    } finally {
      setLoading(false);
    }
  };

  // Lightweight resource-only fetch used by the polling effect below. It does
  // NOT toggle the full-page loading spinner so background refreshes are silent.
  const fetchResources = async () => {
    try {
      const res = await api.get("/admin/resources");
      setResources(res.data);
    } catch (err) {
      // Silent: polling failures shouldn't spam the user with errors.
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Poll every 3 seconds while any resource is in "processing" state so the
  // badge automatically transitions to "آماده"/"ناموفق" once the background
  // reprocess job finishes. Stops polling automatically when none are pending.
  useEffect(() => {
    const hasProcessing = resources.some((r) => r.status === "processing");
    if (!hasProcessing) return undefined;

    const interval = setInterval(() => {
      fetchResources();
    }, 3000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resources]);

  const handleFileSelect = (files) => {
    const file = files?.[0] || null;
    if (file) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("فقط فایل‌های PDF مجاز هستند");
        setSelectedFile(null);
        return;
      }
      setError("");
      setSelectedFile(file);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedCourse || !selectedFile) {
      setError("لطفاً درس و فایل PDF را انتخاب کنید");
      return;
    }
    setUploading(true);
    setMessage("");
    setError("");

    const formData = new FormData();
    formData.append("course_id", selectedCourse);
    formData.append("file", selectedFile);

    try {
      const res = await api.post("/admin/resources/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const status = res.data?.status;
      if (status === "ready") {
        setMessage("فایل با موفقیت بارگذاری و پردازش شد");
      } else if (status === "failed") {
        setError(
          res.data?.error_message
            ? `پردازش فایل ناموفق بود: ${res.data.error_message}`
            : "پردازش فایل ناموفق بود. برای جزئیات به لاگ سیستم مراجعه کنید."
        );
      } else {
        setMessage("فایل بارگذاری شد و در حال پردازش است...");
      }
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در بارگذاری فایل");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteResource = async (id) => {
    if (!window.confirm("آیا از حذف این منبع مطمئن هستید؟ تمام داده‌های وکتوری و فایل آن حذف می‌شود.")) return;
    try {
      await api.delete(`/admin/resources/${id}`);
      setMessage("منبع با موفقیت حذف شد");
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در حذف منبع");
    }
  };

  const handleReprocess = async (id) => {
    setReprocessingId(id);
    setMessage("");
    setError("");
    // Optimistic update: flip the badge to "در حال پردازش" immediately so the
    // UI reacts instantly instead of waiting for the background job to finish.
    setResources((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: "processing", error_message: null } : r))
    );
    try {
      const res = await api.post(`/admin/resources/${id}/reprocess`);
      if (res.data?.status === "processing") {
        setMessage("پردازش مجدد آغاز شد. وضعیت به‌صورت خودکار به‌روزرسانی می‌شود...");
      } else if (res.data?.status === "ready") {
        setMessage("منبع مجدداً پردازش شد");
      } else {
        setError("پردازش مجدد ناموفق بود. برای جزئیات به لاگ سیستم مراجعه کنید.");
      }
      // Refresh once immediately so the server-confirmed "processing" state is
      // reflected; the polling effect below keeps it updated until done.
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در پردازش مجدد");
      // Revert the optimistic status on failure so the badge doesn't stay stuck.
      loadData();
    } finally {
      setReprocessingId(null);
    }
  };

  const handleAddCourse = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");
    try {
      await api.post("/admin/courses", courseForm);
      setMessage("درس با موفقیت اضافه شد");
      setCourseForm({ code: "", title: "", description: "" });
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ایجاد درس");
    }
  };

  const handleToggleCourse = async (course) => {
    try {
      await api.put(`/admin/courses/${course.id}`, { is_active: !course.is_active });
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در تغییر وضعیت درس");
    }
  };

  const handleDeleteCourse = async (id) => {
    if (!window.confirm("حذف درس، تمام منابع و وکتورهای آن را حذف می‌کند. ادامه می‌دهید؟")) return;
    try {
      await api.delete(`/admin/courses/${id}`);
      setMessage("درس با موفقیت حذف شد");
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در حذف درس");
    }
  };

  // Task 8: Chunk viewer
  const openChunkModal = async (resource) => {
    setChunkModal({ resource, chunks: [], loading: true, savingId: null, error: "" });
    setChunkEdits({});
    try {
      const res = await api.get(`/admin/resources/${resource.id}/chunks`);
      setChunkModal((prev) => ({ ...prev, chunks: res.data.chunks || [], loading: false }));
      const edits = {};
      (res.data.chunks || []).forEach((chunk) => {
        edits[chunk.id] = chunk.content;
      });
      setChunkEdits(edits);
    } catch (err) {
      setChunkModal((prev) => ({
        ...prev,
        loading: false,
        error: err.response?.data?.detail || "خطا در دریافت قطعات",
      }));
    }
  };

  const closeChunkModal = () => {
    setChunkModal(null);
    setChunkEdits({});
  };

  const saveChunk = async (chunkId) => {
    const updatedContent = (chunkEdits[chunkId] || "").trim();
    if (!updatedContent) {
      setChunkModal((prev) => ({ ...prev, error: "متن قطعه نمی‌تواند خالی باشد" }));
      return;
    }
    setChunkModal((prev) => ({ ...prev, savingId: chunkId, error: "" }));
    try {
      await api.put(`/admin/resources/chunks/${chunkId}`, { content: updatedContent });
      setChunkModal((prev) => ({
        ...prev,
        savingId: null,
        chunks: prev.chunks.map((c) => (c.id === chunkId ? { ...c, content: updatedContent } : c)),
      }));
      setMessage("قطعه با موفقیت بردارسازی مجدد شد");
    } catch (err) {
      setChunkModal((prev) => ({
        ...prev,
        savingId: null,
        error: err.response?.data?.detail || "خطا در ذخیره قطعه",
      }));
    }
  };

  // Group resources by course (Task 7)
  const resourcesByCourse = {};
  resources.forEach((res) => {
    if (!resourcesByCourse[res.course_id]) resourcesByCourse[res.course_id] = [];
    resourcesByCourse[res.course_id].push(res);
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">مدیریت منابع درسی</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">بارگذاری، مدیریت و حذف منابع PDF دروس</p>
      </div>

      {message && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/40 dark:text-green-300">{message}</div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{error}</div>
      )}

      {loading ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : (
        <>
          {/* Upload form (Tasks 1 & 2: custom file input + visible loading state + truthful toast) */}
          <div className="card">
            <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">بارگذاری منبع جدید</h2>
            <form onSubmit={handleUpload} className="flex flex-col gap-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="label-field">انتخاب درس</label>
                  <select
                    className="input-field"
                    value={selectedCourse}
                    onChange={(e) => setSelectedCourse(e.target.value)}
                    disabled={uploading}
                  >
                    <option value="">انتخاب کنید...</option>
                    {courses.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title} ({c.code})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label-field">فایل PDF</label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    className="hidden"
                    onChange={(e) => handleFileSelect(e.target.files)}
                    disabled={uploading}
                  />
                  <div
                    onClick={() => !uploading && fileInputRef.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      if (!uploading) setDragOver(true);
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragOver(false);
                      if (!uploading) handleFileSelect(e.dataTransfer.files);
                    }}
                    className={`flex cursor-pointer items-center justify-between gap-2 rounded-lg border-2 border-dashed px-3 py-3 text-sm transition ${
                      dragOver
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                        : "border-slate-300 bg-white hover:border-blue-400 dark:border-slate-600 dark:bg-slate-800"
                    } ${uploading ? "pointer-events-none opacity-60" : ""}`}
                  >
                    {selectedFile ? (
                      <span className="flex items-center gap-2 text-slate-800 dark:text-slate-100">
                        <span className="text-lg">📄</span>
                        <span className="truncate font-medium">{selectedFile.name}</span>
                      </span>
                    ) : (
                      <span className="text-slate-500 dark:text-slate-400">
                        📄 برای انتخاب فایل کلیک کنید یا فایل را اینجا رها کنید (فقط PDF)
                      </span>
                    )}
                    <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                      {selectedFile ? "تغییر فایل" : "انتخاب فایل"}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <button
                  type="submit"
                  disabled={uploading}
                  className={`btn-primary w-full sm:w-auto ${uploading ? "cursor-wait opacity-100" : ""}`}
                >
                  {uploading ? (
                    <span className="flex items-center gap-2">
                      <Spinner size="sm" />
                      <span>در حال پردازش...</span>
                    </span>
                  ) : (
                    "بارگذاری"
                  )}
                </button>
                {(uploading || reprocessingId !== null) && (
                  <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                    <p className="flex items-center gap-2 font-medium">
                      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
                      این فرآیند زمان‌بر است و ممکن است اندکی طول بکشد. لطفاً شکیبا باشید...
                    </p>
                    {uploading && (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                        در حال استخراج متن، قطعه‌بندی و بردارسازی فایل...
                      </p>
                    )}
                    {reprocessingId !== null && (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                        در حال حذف قطعات قبلی و بازسازی بردارها...
                      </p>
                    )}
                  </div>
                )}
              </div>
            </form>
          </div>

          {/* Course management + Task 7: Group resources by course */}
          <div className="card">
            <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">درس‌ها و منابع</h2>

            <form onSubmit={handleAddCourse} className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="w-full sm:w-40">
                <label className="label-field">کد درس</label>
                <input
                  type="text"
                  required
                  className="input-field"
                  placeholder="1111001"
                  value={courseForm.code}
                  onChange={(e) => setCourseForm({ ...courseForm, code: e.target.value })}
                />
              </div>
              <div className="flex-1">
                <label className="label-field">نام درس</label>
                <input
                  type="text"
                  required
                  className="input-field"
                  placeholder="مثال: مبانی کامپیوتر"
                  value={courseForm.title}
                  onChange={(e) => setCourseForm({ ...courseForm, title: e.target.value })}
                />
              </div>
              <button type="submit" className="btn-secondary">افزودن درس</button>
            </form>

            <div className="space-y-4">
              {courses.map((course) => {
                const courseResources = resourcesByCourse[course.id] || [];
                const readyCount = courseResources.filter((r) => r.status === "ready").length;
                return (
                  <div key={course.id} className="rounded-lg border border-slate-200 p-4 dark:border-slate-700">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-medium text-slate-800 dark:text-slate-100">
                          {course.title} <span className="text-xs text-slate-500 dark:text-slate-400">({course.code})</span>
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                          {courseResources.length} منبع • {readyCount} آماده
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            course.is_active
                              ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                              : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                          }`}
                        >
                          {course.is_active ? "فعال" : "غیرفعال"}
                        </span>
                        <button onClick={() => handleToggleCourse(course)} className="btn-secondary !px-2 !py-1 text-xs">
                          {course.is_active ? "غیرفعال‌کردن" : "فعال‌کردن"}
                        </button>
                        <button onClick={() => handleDeleteCourse(course.id)} className="btn-secondary !px-2 !py-1 text-xs text-red-600 dark:text-red-400">
                          حذف درس
                        </button>
                      </div>
                    </div>

                    {courseResources.length > 0 ? (
                      <div className="mt-3 overflow-x-auto">
                        <table className="min-w-full divide-y divide-slate-100 text-sm dark:divide-slate-700">
                          <thead>
                            <tr className="text-right text-xs text-slate-500 dark:text-slate-400">
                              <th className="px-3 py-2 font-medium">نام فایل</th>
                              <th className="px-3 py-2 font-medium">وضعیت</th>
                              <th className="px-3 py-2 font-medium">تعداد قطعات</th>
                              <th className="px-3 py-2 font-medium">تاریخ</th>
                              <th className="px-3 py-2 font-medium">عملیات</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                            {courseResources.map((res) => (
                              <tr key={res.id}>
                                <td className="px-3 py-2 text-slate-800 dark:text-slate-100">
                                  {res.filename}
                                  {res.status === "failed" && res.error_message && (
                                    <p className="mt-0.5 text-xs text-red-500 dark:text-red-400">{res.error_message}</p>
                                  )}
                                </td>
                                <td className="px-3 py-2">
                                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[res.status]}`}>
                                    {statusLabels[res.status]}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{res.chunk_count}</td>
                                <td className="px-3 py-2 text-slate-600 dark:text-slate-300">
                                  {new Date(res.uploaded_at).toLocaleDateString("fa-IR")}
                                </td>
                                <td className="px-3 py-2">
                                  <div className="flex flex-wrap gap-2">
                                    <button
                                      onClick={() => handleReprocess(res.id)}
                                      disabled={reprocessingId !== null}
                                      className={`text-xs ${
                                        reprocessingId === res.id
                                          ? "flex cursor-wait items-center gap-1 text-blue-600 dark:text-blue-400"
                                          : reprocessingId !== null
                                          ? "cursor-not-allowed text-slate-400 dark:text-slate-500"
                                          : "text-blue-600 hover:underline dark:text-blue-400"
                                      }`}
                                    >
                                      {reprocessingId === res.id ? (
                                        <>
                                          <Spinner size="sm" />
                                          <span>در حال پردازش...</span>
                                        </>
                                      ) : (
                                        "پردازش مجدد"
                                      )}
                                    </button>
                                    {res.status === "ready" && res.chunk_count > 0 && (
                                      <button onClick={() => openChunkModal(res)} className="text-xs text-purple-600 hover:underline dark:text-purple-400">
                                        مشاهده قطعات
                                      </button>
                                    )}
                                    <button onClick={() => handleDeleteResource(res.id)} className="text-xs text-red-600 hover:underline dark:text-red-400">
                                      حذف
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">هنوز منبعی برای این درس بارگذاری نشده است.</p>
                    )}
                  </div>
                );
              })}
              {courses.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400">هنوز درسی ثبت نشده است.</p>}
            </div>
          </div>
        </>
      )}

      {/* Task 8: Chunk viewer & editor modal */}
      {chunkModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={closeChunkModal}>
          <div
            className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl dark:bg-slate-800"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-700 dark:text-slate-200">قطعات وکتوری: {chunkModal.resource.filename}</h3>
              <button onClick={closeChunkModal} className="rounded-lg p-1 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700" aria-label="بستن">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {chunkModal.error && (
              <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{chunkModal.error}</div>
            )}

            {chunkModal.loading ? (
              <div className="flex justify-center py-8"><Spinner /></div>
            ) : chunkModal.chunks.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">قطعه‌ای برای این منبع یافت نشد.</p>
            ) : (
              <div className="space-y-4">
                {chunkModal.chunks.map((chunk, idx) => (
                  <div key={chunk.id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">قطعه شماره {idx + 1}</span>
                      <span className="text-xs text-slate-400 dark:text-slate-500">{chunk.filename}</span>
                    </div>
                    <textarea
                      className="input-field chunk-textarea min-h-[100px] text-xs"
                      value={chunkEdits[chunk.id] ?? chunk.content}
                      onChange={(e) => setChunkEdits((prev) => ({ ...prev, [chunk.id]: e.target.value }))}
                      dir="auto"
                    />
                    <div className="mt-2 flex justify-end">
                      <button onClick={() => saveChunk(chunk.id)} disabled={chunkModal.savingId === chunk.id} className="btn-secondary !px-3 !py-1 text-xs">
                        {chunkModal.savingId === chunk.id ? (
                          <span className="flex items-center gap-2">
                            <Spinner size="sm" /> در حال بردارسازی...
                          </span>
                        ) : (
                          "ذخیره و بردارسازی مجدد"
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
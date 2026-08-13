import { useEffect, useState } from "react";
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
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Upload form
  const [selectedCourse, setSelectedCourse] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);

  // Course form
  const [courseForm, setCourseForm] = useState({ code: "", title: "", description: "" });

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

  useEffect(() => {
    loadData();
  }, []);

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
      await api.post("/admin/resources/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setMessage("فایل با موفقیت بارگذاری و پردازش شد");
      setSelectedFile(null);
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در بارگذاری فایل");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteResource = async (id) => {
    if (!window.confirm("آیا از حذف این منبع مطمئن هستید؟")) return;
    try {
      await api.delete(`/admin/resources/${id}`);
      setMessage("منبع با موفقیت حذف شد");
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در حذف منبع");
    }
  };

  const handleReprocess = async (id) => {
    try {
      await api.post(`/admin/resources/${id}/reprocess`);
      setMessage("منبع مجدداً پردازش شد");
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در پردازش مجدد");
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

      {/* Upload form */}
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">بارگذاری منبع جدید</h2>
        <form onSubmit={handleUpload} className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="label-field">انتخاب درس</label>
            <select
              className="input-field"
              value={selectedCourse}
              onChange={(e) => setSelectedCourse(e.target.value)}
            >
              <option value="">انتخاب کنید...</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title} ({c.code})
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="label-field">فایل PDF</label>
            <input
              type="file"
              accept=".pdf,application/pdf"
              className="input-field"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            />
          </div>
          <button type="submit" disabled={uploading} className="btn-primary">
            {uploading ? <Spinner size="sm" /> : "بارگذاری"}
          </button>
        </form>
      </div>

      {/* Courses */}
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">درس‌ها</h2>

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
          <button type="submit" className="btn-secondary">
            افزودن درس
          </button>
        </form>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {courses.map((course) => (
            <div key={course.id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-slate-800 dark:text-slate-100">{course.title}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{course.code}</p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    course.is_active
                      ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                      : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                  }`}
                >
                  {course.is_active ? "فعال" : "غیرفعال"}
                </span>
              </div>
              <div className="mt-3 flex gap-2">
                <button onClick={() => handleToggleCourse(course)} className="btn-secondary flex-1 !px-2 !py-1 text-xs">
                  {course.is_active ? "غیرفعال‌کردن" : "فعال‌کردن"}
                </button>
                <button onClick={() => handleDeleteCourse(course.id)} className="btn-secondary flex-1 !px-2 !py-1 text-xs text-red-600 dark:text-red-400">
                  حذف
                </button>
              </div>
            </div>
          ))}
          {courses.length === 0 && (
            <p className="text-sm text-slate-500 dark:text-slate-400">هنوز درسی ثبت نشده است.</p>
          )}
        </div>
      </div>

      {/* Resources table */}
      <div className="card">
        <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">منابع بارگذاری‌شده</h2>

        {loading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : resources.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">هنوز منبعی بارگذاری نشده است.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
              <thead>
                <tr className="text-right text-xs text-slate-500 dark:text-slate-400">
                  <th className="px-3 py-2 font-medium">نام فایل</th>
                  <th className="px-3 py-2 font-medium">درس</th>
                  <th className="px-3 py-2 font-medium">وضعیت</th>
                  <th className="px-3 py-2 font-medium">تعداد قطعات</th>
                  <th className="px-3 py-2 font-medium">تاریخ</th>
                  <th className="px-3 py-2 font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {resources.map((res) => (
                  <tr key={res.id}>
                    <td className="px-3 py-2 text-slate-800 dark:text-slate-100">{res.filename}</td>
                    <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{res.course_title || "-"}</td>
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
                      <div className="flex gap-2">
                        <button onClick={() => handleReprocess(res.id)} className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                          پردازش مجدد
                        </button>
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
        )}
      </div>
    </div>
  );
}
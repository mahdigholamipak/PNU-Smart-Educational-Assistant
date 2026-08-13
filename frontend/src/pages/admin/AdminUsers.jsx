import { useEffect, useState } from "react";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadUsers = () => {
    setLoading(true);
    api
      .get("/admin/users")
      .then((res) => setUsers(res.data))
      .catch(() => setError("خطا در دریافت کاربران"))
      .finally(() => setLoading(false));
  };

  useEffect(loadUsers, []);

  const toggleActive = async (user) => {
    try {
      await api.patch(`/admin/users/${user.id}`, null, {
        params: { is_active: !user.is_active },
      });
      setMessage(`وضعیت کاربر ${user.full_name} تغییر کرد`);
      loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در تغییر وضعیت");
    }
  };

  const changeRole = async (user, role) => {
    try {
      await api.patch(`/admin/users/${user.id}`, null, {
        params: { role },
      });
      setMessage(`نقش کاربر ${user.full_name} تغییر کرد`);
      loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در تغییر نقش");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">مدیریت کاربران</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">مشاهده و مدیریت کاربران ثبت‌شده در سیستم</p>
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
        ) : users.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">کاربری ثبت نشده است.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
              <thead>
                <tr className="text-right text-xs text-slate-500 dark:text-slate-400">
                  <th className="px-3 py-2 font-medium">نام</th>
                  <th className="px-3 py-2 font-medium">ایمیل</th>
                  <th className="px-3 py-2 font-medium">شماره دانشجویی</th>
                  <th className="px-3 py-2 font-medium">نقش</th>
                  <th className="px-3 py-2 font-medium">وضعیت</th>
                  <th className="px-3 py-2 font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-100">{user.full_name}</td>
                    <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{user.email}</td>
                    <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{user.student_id || "-"}</td>
                    <td className="px-3 py-2">
                      <select
                        className="input-field !w-auto !py-1 text-xs"
                        value={user.role}
                        onChange={(e) => changeRole(user, e.target.value)}
                      >
                        <option value="student">دانشجو</option>
                        <option value="admin">مدیر</option>
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          user.is_active
                            ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                            : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
                        }`}
                      >
                        {user.is_active ? "فعال" : "غیرفعال"}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => toggleActive(user)}
                        className={`text-xs hover:underline ${
                          user.is_active ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400"
                        }`}
                      >
                        {user.is_active ? "غیرفعال‌کردن" : "فعال‌کردن"}
                      </button>
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
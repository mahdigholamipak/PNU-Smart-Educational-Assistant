import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Spinner from "../components/Spinner";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    student_id: "",
    phone: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (form.password !== form.confirm_password) {
      setError("رمز عبور و تکرار آن یکسان نیستند");
      return;
    }

    setLoading(true);
    try {
      const { confirm_password, ...payload } = form;
      const user = await register(payload);
      navigate(user.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ثبت‌نام");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4 dark:from-slate-900 dark:to-slate-800">
      <div className="w-full max-w-lg">
        <div className="card">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-bold text-blue-700 dark:text-blue-400">ثبت‌نام</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">ایجاد حساب کاربری دانشجویی</p>
          </div>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label-field" htmlFor="full_name">نام و نام خانوادگی</label>
              <input
                id="full_name"
                name="full_name"
                type="text"
                required
                className="input-field"
                placeholder="مثال: علی محمدی"
                value={form.full_name}
                onChange={handleChange}
              />
            </div>

            <div>
              <label className="label-field" htmlFor="email">ایمیل</label>
              <input
                id="email"
                name="email"
                type="email"
                required
                className="input-field"
                placeholder="example@pnu.ac.ir"
                value={form.email}
                onChange={handleChange}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="label-field" htmlFor="student_id">شماره دانشجویی</label>
                <input
                  id="student_id"
                  name="student_id"
                  type="text"
                  className="input-field"
                  placeholder="اختیاری"
                  value={form.student_id}
                  onChange={handleChange}
                />
              </div>
              <div>
                <label className="label-field" htmlFor="phone">شماره تماس</label>
                <input
                  id="phone"
                  name="phone"
                  type="text"
                  className="input-field"
                  placeholder="اختیاری"
                  value={form.phone}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="label-field" htmlFor="password">رمز عبور</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  minLength={8}
                  className="input-field"
                  placeholder="حداقل ۸ کاراکتر"
                  value={form.password}
                  onChange={handleChange}
                />
              </div>
              <div>
                <label className="label-field" htmlFor="confirm_password">تکرار رمز عبور</label>
                <input
                  id="confirm_password"
                  name="confirm_password"
                  type="password"
                  required
                  minLength={8}
                  className="input-field"
                  placeholder="••••••••"
                  value={form.confirm_password}
                  onChange={handleChange}
                />
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? <Spinner size="sm" /> : "ثبت‌نام"}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
            قبلاً ثبت‌نام کرده‌اید؟{" "}
            <Link to="/login" className="font-medium text-blue-600 hover:underline dark:text-blue-400">
              وارد شوید
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
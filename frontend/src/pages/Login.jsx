import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Spinner from "../components/Spinner";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(email, password);
      navigate(user.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "خطا در ورود به سیستم");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4 dark:from-slate-900 dark:to-slate-800">
      <div className="w-full max-w-md">
        <div className="card">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-bold text-blue-700 dark:text-blue-400">دستیار هوشمند آموزشی</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">ورود به حساب کاربری</p>
          </div>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label-field" htmlFor="email">ایمیل</label>
              <input
                id="email"
                type="email"
                required
                className="input-field"
                placeholder="example@pnu.ac.ir"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div>
              <label className="label-field" htmlFor="password">رمز عبور</label>
              <input
                id="password"
                type="password"
                required
                className="input-field"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full">
              {loading ? <Spinner size="sm" /> : "ورود"}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
            حساب ندارید؟{" "}
            <Link to="/register" className="font-medium text-blue-600 hover:underline dark:text-blue-400">
              ثبت‌نام کنید
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
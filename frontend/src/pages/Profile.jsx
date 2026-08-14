import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../api/axios.client";
import Spinner from "../components/Spinner";

export default function Profile() {
  const { user, updateUser } = useAuth();

  const [profile, setProfile] = useState({
    full_name: user?.full_name || "",
    student_id: user?.student_id || "",
    phone: user?.phone || "",
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [profileMsg, setProfileMsg] = useState("");
  const [profileErr, setProfileErr] = useState("");
  const [passwordMsg, setPasswordMsg] = useState("");
  const [passwordErr, setPasswordErr] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleProfileChange = (e) => {
    setProfile({ ...profile, [e.target.name]: e.target.value });
  };

  const handlePasswordChange = (e) => {
    setPasswordForm({ ...passwordForm, [e.target.name]: e.target.value });
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    setSaving(true);
    setProfileMsg("");
    setProfileErr("");
    try {
      const res = await api.put("/users/me", profile);
      updateUser(res.data);
      setProfileMsg("پروفایل با موفقیت ذخیره شد");
    } catch (err) {
      setProfileErr(err.response?.data?.detail || "خطا در ذخیره پروفایل");
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async (e) => {
    e.preventDefault();
    setPasswordMsg("");
    setPasswordErr("");

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordErr("رمز عبور جدید و تکرار آن یکسان نیستند");
      return;
    }

    setSaving(true);
    try {
      await api.put("/users/me/password", {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setPasswordMsg("رمز عبور با موفقیت تغییر کرد");
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
    } catch (err) {
      setPasswordErr(err.response?.data?.detail || "خطا در تغییر رمز عبور");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">پروفایل کاربری</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">مشاهده و ویرایش اطلاعات شخصی</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Profile info */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">اطلاعات شخصی</h2>

          {profileMsg && (
            <div className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/40 dark:text-green-300">{profileMsg}</div>
          )}
          {profileErr && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{profileErr}</div>
          )}

          <form onSubmit={saveProfile} className="space-y-4">
            <div>
              <label className="label-field">ایمیل</label>
              <input type="email" className="input-field bg-slate-50 dark:bg-slate-700/50" value={user?.email} disabled />
            </div>

            <div>
              <label className="label-field" htmlFor="full_name">نام و نام خانوادگی</label>
              <input
                id="full_name"
                name="full_name"
                type="text"
                className="input-field"
                value={profile.full_name}
                onChange={handleProfileChange}
                required
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
                  value={profile.student_id}
                  onChange={handleProfileChange}
                />
              </div>
              <div>
                <label className="label-field" htmlFor="phone">شماره تماس</label>
                <input
                  id="phone"
                  name="phone"
                  type="text"
                  className="input-field"
                  value={profile.phone}
                  onChange={handleProfileChange}
                />
              </div>
            </div>

            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? <Spinner size="sm" /> : "ذخیره تغییرات"}
            </button>
          </form>
        </div>

        {/* Password change */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-slate-700 dark:text-slate-200">تغییر رمز عبور</h2>

          {passwordMsg && (
            <div className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/40 dark:text-green-300">{passwordMsg}</div>
          )}
          {passwordErr && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/40 dark:text-red-300">{passwordErr}</div>
          )}

          <form onSubmit={changePassword} className="space-y-4">
            <div>
              <label className="label-field" htmlFor="current_password">رمز عبور فعلی</label>
              <div className="relative">
                <input
                  id="current_password"
                  name="current_password"
                  type={showCurrent ? "text" : "password"}
                  className="input-field pl-10"
                  value={passwordForm.current_password}
                  onChange={handlePasswordChange}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent((v) => !v)}
                  className="absolute top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                  style={{ left: "0.75rem" }}
                  aria-label={showCurrent ? "پنهان‌کردن رمز عبور فعلی" : "نمایش رمز عبور فعلی"}
                  tabIndex={-1}
                >
                  {showCurrent ? (
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
            </div>
            <div>
              <label className="label-field" htmlFor="new_password">رمز عبور جدید</label>
              <div className="relative">
                <input
                  id="new_password"
                  name="new_password"
                  type={showNew ? "text" : "password"}
                  minLength={8}
                  className="input-field pl-10"
                  value={passwordForm.new_password}
                  onChange={handlePasswordChange}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowNew((v) => !v)}
                  className="absolute top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                  style={{ left: "0.75rem" }}
                  aria-label={showNew ? "پنهان‌کردن رمز عبور جدید" : "نمایش رمز عبور جدید"}
                  tabIndex={-1}
                >
                  {showNew ? (
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
            </div>
            <div>
              <label className="label-field" htmlFor="confirm_password">تکرار رمز عبور جدید</label>
              <div className="relative">
                <input
                  id="confirm_password"
                  name="confirm_password"
                  type={showConfirm ? "text" : "password"}
                  minLength={8}
                  className="input-field pl-10"
                  value={passwordForm.confirm_password}
                  onChange={handlePasswordChange}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                  style={{ left: "0.75rem" }}
                  aria-label={showConfirm ? "پنهان‌کردن تکرار رمز عبور جدید" : "نمایش تکرار رمز عبور جدید"}
                  tabIndex={-1}
                >
                  {showConfirm ? (
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
            </div>

            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? <Spinner size="sm" /> : "تغییر رمز عبور"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
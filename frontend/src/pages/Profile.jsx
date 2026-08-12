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
        <h1 className="text-2xl font-bold text-slate-800">پروفایل کاربری</h1>
        <p className="mt-1 text-sm text-slate-500">مشاهده و ویرایش اطلاعات شخصی</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Profile info */}
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-slate-700">اطلاعات شخصی</h2>

          {profileMsg && (
            <div className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700">{profileMsg}</div>
          )}
          {profileErr && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{profileErr}</div>
          )}

          <form onSubmit={saveProfile} className="space-y-4">
            <div>
              <label className="label-field">ایمیل</label>
              <input type="email" className="input-field bg-slate-50" value={user?.email} disabled />
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
          <h2 className="mb-4 text-lg font-semibold text-slate-700">تغییر رمز عبور</h2>

          {passwordMsg && (
            <div className="mb-4 rounded-lg bg-green-50 p-3 text-sm text-green-700">{passwordMsg}</div>
          )}
          {passwordErr && (
            <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{passwordErr}</div>
          )}

          <form onSubmit={changePassword} className="space-y-4">
            <div>
              <label className="label-field" htmlFor="current_password">رمز عبور فعلی</label>
              <input
                id="current_password"
                name="current_password"
                type="password"
                className="input-field"
                value={passwordForm.current_password}
                onChange={handlePasswordChange}
                required
              />
            </div>
            <div>
              <label className="label-field" htmlFor="new_password">رمز عبور جدید</label>
              <input
                id="new_password"
                name="new_password"
                type="password"
                minLength={8}
                className="input-field"
                value={passwordForm.new_password}
                onChange={handlePasswordChange}
                required
              />
            </div>
            <div>
              <label className="label-field" htmlFor="confirm_password">تکرار رمز عبور جدید</label>
              <input
                id="confirm_password"
                name="confirm_password"
                type="password"
                minLength={8}
                className="input-field"
                value={passwordForm.confirm_password}
                onChange={handlePasswordChange}
                required
              />
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
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";

const studentLinks = [
  { to: "/dashboard", label: "داشبورد", icon: "🏠" },
  { to: "/chat", label: "گفتگو", icon: "💬" },
  { to: "/history", label: "تاریخچه گفتگوها", icon: "📜" },
  { to: "/profile", label: "پروفایل", icon: "👤" },
  { to: "/course-request", label: "درخواست‌های درس", icon: "📚" },
];

const adminLinks = [
  { to: "/admin", label: "داشبورد مدیریت", icon: "🛠️" },
  { to: "/admin/resources", label: "مدیریت منابع", icon: "📄" },
  { to: "/admin/users", label: "مدیریت کاربران", icon: "👥" },
  { to: "/admin/requests", label: "درخواست‌های درس", icon: "📨" },
  { to: "/admin/settings", label: "تنظیمات API", icon: "⚙️" },
  { to: "/admin/logs", label: "لاگ سیستم", icon: "📋" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const links = user?.role === "admin" ? [...studentLinks, ...adminLinks] : studentLinks;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const closeSidebar = () => setSidebarOpen(false);

  return (
    <div className="flex min-h-screen">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 right-0 z-40 flex w-64 flex-col border-l border-slate-200 bg-white transition-transform duration-300 dark:border-slate-700 dark:bg-slate-800 ${
          sidebarOpen ? "translate-x-0" : "translate-x-full"
        } lg:translate-x-0`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-700">
          <div>
            <h1 className="text-lg font-bold text-blue-700 dark:text-blue-400">دستیار هوشمند آموزشی</h1>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">دانشگاه پیام نور</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={toggleTheme}
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700"
              aria-label="تغییر حالت روشن/تاریک"
              title={theme === "dark" ? "حالت روشن" : "حالت تاریک"}
            >
              {theme === "dark" ? "☀️" : "🌙"}
            </button>
            <button
              onClick={closeSidebar}
              className="rounded-lg p-1 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-700 lg:hidden"
              aria-label="بستن منو"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/dashboard" || link.to === "/admin"}
              onClick={closeSidebar}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-white"
                }`
              }
            >
              <span>{link.icon}</span>
              <span>{link.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-4 dark:border-slate-700">
          <div className="mb-3 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-lg font-bold text-blue-700 dark:bg-blue-900/50 dark:text-blue-300">
              {user?.full_name?.charAt(0) || "؟"}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">{user?.full_name}</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user?.email}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="btn-secondary w-full">
            خروج از حساب
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex min-h-screen w-full flex-col lg:mr-64">
        {/* Top bar (mobile) */}
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/95 p-3 backdrop-blur dark:border-slate-700 dark:bg-slate-900/95 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label="باز کردن منو"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 className="text-sm font-bold text-blue-700 dark:text-blue-400">دستیار هوشمند آموزشی</h1>
          <button
            onClick={toggleTheme}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label="تغییر حالت روشن/تاریک"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </header>

        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
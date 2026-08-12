import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const studentLinks = [
  { to: "/dashboard", label: "داشبورد", icon: "🏠" },
  { to: "/chat", label: "گفتگو", icon: "💬" },
  { to: "/history", label: "تاریخچه گفتگوها", icon: "📜" },
  { to: "/profile", label: "پروفایل", icon: "👤" },
  { to: "/course-request", label: "درخواست درس", icon: "📚" },
];

const adminLinks = [
  { to: "/admin", label: "داشبورد مدیریت", icon: "🛠️" },
  { to: "/admin/resources", label: "مدیریت منابع", icon: "📄" },
  { to: "/admin/users", label: "مدیریت کاربران", icon: "👥" },
  { to: "/admin/requests", label: "درخواست‌های درس", icon: "📨" },
  { to: "/admin/settings", label: "تنظیمات API", icon: "⚙️" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const links = user?.role === "admin" ? [...studentLinks, ...adminLinks] : studentLinks;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 right-0 z-20 flex w-64 flex-col border-l border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-4">
          <h1 className="text-lg font-bold text-blue-700">دستیار هوشمند آموزشی</h1>
          <p className="mt-1 text-xs text-slate-500">دانشگاه پیام نور</p>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/dashboard" || link.to === "/admin"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`
              }
            >
              <span>{link.icon}</span>
              <span>{link.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-4">
          <div className="mb-3 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-lg font-bold text-blue-700">
              {user?.full_name?.charAt(0) || "؟"}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-800">{user?.full_name}</p>
              <p className="truncate text-xs text-slate-500">{user?.email}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="btn-secondary w-full">
            خروج از حساب
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="mr-64 flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../../api/axios.client";
import Spinner from "../../components/Spinner";

export default function AdminDashboard() {
  const [stats, setStats] = useState({
    courses: 0,
    users: 0,
    resources: 0,
    pendingRequests: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/admin/courses"),
      api.get("/admin/users"),
      api.get("/admin/resources"),
      api.get("/admin/requests"),
    ])
      .then(([courses, users, resources, requests]) => {
        setStats({
          courses: courses.data.length,
          users: users.data.length,
          resources: resources.data.length,
          pendingRequests: requests.data.filter((r) => r.status === "pending").length,
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const cards = [
    { label: "درس‌ها", value: stats.courses, icon: "📘", to: "/admin/resources", color: "bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" },
    { label: "کاربران", value: stats.users, icon: "👥", to: "/admin/users", color: "bg-green-50 text-green-700 dark:bg-green-900/40 dark:text-green-300" },
    { label: "منابع درسی", value: stats.resources, icon: "📄", to: "/admin/resources", color: "bg-purple-50 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300" },
    { label: "درخواست‌های در انتظار", value: stats.pendingRequests, icon: "📨", to: "/admin/requests", color: "bg-yellow-50 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300" },
  ];

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">داشبورد مدیریت</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">نمای کلی وضعیت سیستم</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <Link key={card.label} to={card.to} className="card hover:shadow-md">
            <div className={`inline-flex h-12 w-12 items-center justify-center rounded-xl text-2xl ${card.color}`}>
              {card.icon}
            </div>
            <p className="mt-3 text-2xl font-bold text-slate-800 dark:text-slate-100">{card.value}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">{card.label}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
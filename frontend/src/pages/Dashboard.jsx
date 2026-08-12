import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios.client";
import Spinner from "../components/Spinner";
import { useAuth } from "../context/AuthContext";

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/courses")
      .then((res) => setCourses(res.data))
      .catch(() => setError("خطا در دریافت لیست درس‌ها"))
      .finally(() => setLoading(false));
  }, []);

  const handleSelectCourse = (courseId) => {
    navigate(`/chat?course=${courseId}`);
  };

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
        <h1 className="text-2xl font-bold text-slate-800">سلام، {user?.full_name} 👋</h1>
        <p className="mt-1 text-sm text-slate-500">
          یک درس را انتخاب کنید تا گفتگو با دستیار هوشمند را آغاز کنید.
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {!loading && courses.length === 0 && (
        <div className="card text-center">
          <p className="text-slate-500">
            هنوز درسی در سیستم ثبت نشده است. می‌توانید از بخش «درخواست درس» درس مورد نظر خود را درخواست دهید.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {courses.map((course) => (
          <button
            key={course.id}
            onClick={() => handleSelectCourse(course.id)}
            className="card group text-right transition hover:border-blue-300 hover:shadow-md"
          >
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-800 group-hover:text-blue-700">
                  {course.title}
                </h2>
                <p className="mt-1 text-xs font-medium text-blue-600">{course.code}</p>
              </div>
              <span className="text-2xl">📘</span>
            </div>
            {course.description && (
              <p className="mt-3 line-clamp-2 text-sm text-slate-500">{course.description}</p>
            )}
            <div className="mt-4">
              <span className="inline-flex items-center gap-1 text-sm font-medium text-blue-600">
                شروع گفتگو ←
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
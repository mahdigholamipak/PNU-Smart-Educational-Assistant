export default function Spinner({ size = "md" }) {
  const sizes = {
    sm: "h-4 w-4 border-2",
    md: "h-8 w-8 border-3",
    lg: "h-12 w-12 border-4",
  };

  return (
    <div
      className={`${sizes[size]} inline-block animate-spin rounded-full border-blue-600 border-t-transparent dark:border-blue-400 dark:border-t-transparent`}
      role="status"
      aria-label="در حال بارگذاری"
    />
  );
}
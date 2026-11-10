
import type { LucideIcon } from "lucide-react";

type StatCardProps = {
  title: string;
  value: string;
  note: string;
  icon: LucideIcon;
};

export default function StatCard({
  title,
  value,
  note,
  icon: Icon,
}: StatCardProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-slate-500">{title}</p>

        <div className="rounded-xl bg-indigo-50 p-2 text-indigo-600">
          <Icon size={20} />
        </div>
      </div>

      <p className="mt-4 text-2xl font-bold text-slate-900">
        {value}
      </p>

      <p className="mt-2 text-xs text-slate-500">{note}</p>
    </section>
  );
}

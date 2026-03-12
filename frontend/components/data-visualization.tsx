"use client";

import type { Visualization } from "@/lib/types";

type Props = {
  visualization?: Visualization | null;
};

export function DataVisualization({ visualization }: Props) {
  if (!visualization) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
        <h4 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">Data Panel</h4>
        <p className="mt-4 text-sm text-slate-400">
          Ask a teammate a specific question to populate the latest evidence panel.
        </p>
      </div>
    );
  }

  if (visualization.type === "funnel") {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">
            {visualization.title ?? "Conversion Funnel"}
          </h4>
          <span className="rounded-full bg-red-500/10 px-2 py-1 text-[10px] font-bold text-red-400">
            latest analyst evidence
          </span>
        </div>
        <div className="mt-5 space-y-3">
          {visualization.data.map((item) => {
            const width = Math.max(8, Number(item.value) * 100);
            return (
              <div key={String(item.step)}>
                <div className="mb-1 flex items-center justify-between text-xs font-mono text-slate-300">
                  <span>{String(item.step)}</span>
                  <span>{Math.round(Number(item.value) * 100)}%</span>
                </div>
                <div className="h-6 overflow-hidden rounded bg-slate-800">
                  <div className="h-full rounded bg-primary/70" style={{ width: `${width}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (visualization.type === "line" || visualization.type === "bar") {
    const valueKey = visualization.type === "line" ? "orders" : "value";
    const maxValue = Math.max(
      ...visualization.data.map((item) =>
        Number(item[valueKey] ?? item.current ?? item.previous ?? 0)
      ),
      1
    );

    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
        <h4 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">
          {visualization.title ?? "Metric Snapshot"}
        </h4>
        <div className="mt-5 space-y-4">
          {visualization.data.map((item) => {
            const label = String(item.label ?? item.step ?? "Metric");
            const rawValue = Number(item[valueKey] ?? item.current ?? item.previous ?? 0);
            const width = Math.max(12, (rawValue / maxValue) * 100);
            return (
              <div key={label}>
                <div className="mb-1 flex items-center justify-between text-xs font-mono text-slate-300">
                  <span>{label}</span>
                  <span>{Number.isInteger(rawValue) ? rawValue.toLocaleString() : rawValue.toFixed(1)}</span>
                </div>
                <div className="h-5 overflow-hidden rounded bg-slate-800">
                  <div className="h-full rounded bg-primary/80" style={{ width: `${width}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (visualization.type === "timeline") {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
        <h4 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">
          {visualization.title ?? "Timeline"}
        </h4>
        <div className="mt-5 space-y-4">
          {visualization.data.map((item) => (
            <div key={`${String(item.date)}-${String(item.service)}`} className="rounded-lg border border-slate-800 bg-slate-950/70 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{String(item.date)}</p>
              <p className="mt-2 font-semibold text-slate-100">{String(item.service)}</p>
              <p className="mt-1 text-sm text-slate-400">{String(item.change)}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <h4 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">
        {visualization.title ?? "Structured Evidence"}
      </h4>
      <div className="mt-5 space-y-3">
        {visualization.data.map((item, index) => (
          <div key={index} className="rounded-lg border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
            {Object.entries(item).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-4 py-1">
                <span className="capitalize text-slate-500">{key.replaceAll("_", " ")}</span>
                <span className="text-right">{String(value)}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

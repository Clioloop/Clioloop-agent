import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, HardDrive, MemoryStick } from "lucide-react";
import { api, type SystemStats } from "@/lib/api";

/** Global resource guardrail. Hidden while healthy; warns before memory/disk
 * exhaustion makes writes, context compaction, or model calls unreliable. */
export function PressureBanner() {
  const [stats, setStats] = useState<SystemStats | null>(null);
  useEffect(() => {
    let live = true;
    const poll = () => api.getSystemStats().then((next) => { if (live) setStats(next); }).catch(() => undefined);
    void poll();
    const timer = window.setInterval(poll, 60_000);
    return () => { live = false; window.clearInterval(timer); };
  }, []);
  const warnings = useMemo(() => {
    const result: Array<{ label: string; percent: number; icon: typeof HardDrive }> = [];
    if ((stats?.memory?.percent ?? 0) >= 85) result.push({ label: "Memory pressure", percent: stats!.memory!.percent, icon: MemoryStick });
    if ((stats?.disk?.percent ?? 0) >= 85) result.push({ label: "Disk pressure", percent: stats!.disk!.percent, icon: HardDrive });
    return result;
  }, [stats]);
  if (!warnings.length) return null;
  return <div role="alert" className="relative z-30 flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-amber-400/40 bg-amber-400/10 px-4 py-2 text-xs text-amber-200"><span className="flex items-center gap-1.5 font-medium"><AlertTriangle className="h-4 w-4" />Resource pressure may reduce context and memory reliability.</span>{warnings.map(({ label, percent, icon: Icon }) => <span key={label} className="flex items-center gap-1"><Icon className="h-3.5 w-3.5" />{label}: {percent.toFixed(0)}%</span>)}</div>;
}

import { Layers3 } from "lucide-react";
import { Select, SelectOption } from "@clioloop-agent/ui/ui/components/select";
import { useDashboardProfile } from "@/contexts/useDashboardProfile";
import { cn } from "@/lib/utils";

export function DashboardProfilePicker({ collapsed = false }: { collapsed?: boolean }) {
  const { profile, profiles, setProfile, loading } = useDashboardProfile();
  if (collapsed) return <div className="flex justify-center py-2" title={`Dashboard profile: ${profile}`}><Layers3 className="h-4 w-4 text-midground" /></div>;
  return <div className="border-b border-current/10 px-3 py-2">
    <label htmlFor="dashboard-profile" className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.12em] text-text-tertiary"><Layers3 className="h-3 w-3" />Dashboard profile</label>
    <Select id="dashboard-profile" className={cn("h-8 w-full rounded-none text-xs", loading && "opacity-60")} value={profile} onValueChange={setProfile} disabled={loading}>{profiles.length ? profiles.map((item) => <SelectOption key={item.name} value={item.name}>{item.name}{item.gateway_running ? " · running" : ""}</SelectOption>) : <SelectOption value={profile}>{profile}</SelectOption>}</Select>
  </div>;
}

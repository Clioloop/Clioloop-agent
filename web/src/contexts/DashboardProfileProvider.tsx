import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type ProfileInfo } from "@/lib/api";
import { DashboardProfileContext } from "./dashboard-profile-context";

const STORAGE_KEY = "clio-dashboard-profile";

export function DashboardProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfileState] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) || "default"; } catch { return "default"; }
  });
  const [profiles, setProfiles] = useState<ProfileInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [listed, active] = await Promise.all([
        api.getProfiles(),
        api.getActiveProfile().catch(() => null),
      ]);
      setProfiles(listed.profiles);
      setProfileState((current) => {
        const valid = listed.profiles.some((item) => item.name === current);
        return valid ? current : (active?.current || active?.active || listed.profiles[0]?.name || "default");
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  const setProfile = useCallback((next: string) => {
    setProfileState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* private mode */ }
  }, []);
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, profile); } catch { /* private mode */ }
  }, [profile]);

  const value = useMemo(() => ({ profile, profiles, loading, setProfile, refresh }), [profile, profiles, loading, setProfile, refresh]);
  return <DashboardProfileContext.Provider value={value}>{children}</DashboardProfileContext.Provider>;
}

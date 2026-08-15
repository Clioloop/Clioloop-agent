import { createContext } from "react";
import type { ProfileInfo } from "@/lib/api";

export interface DashboardProfileContextValue {
  profile: string;
  profiles: ProfileInfo[];
  loading: boolean;
  setProfile: (profile: string) => void;
  refresh: () => Promise<void>;
}

export const DashboardProfileContext = createContext<DashboardProfileContextValue | null>(null);

import { useContext } from "react";
import { DashboardProfileContext } from "./dashboard-profile-context";

export function useDashboardProfile() {
  const value = useContext(DashboardProfileContext);
  if (!value) throw new Error("useDashboardProfile must be used within DashboardProfileProvider");
  return value;
}

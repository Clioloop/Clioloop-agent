// Clio Achievements dashboard plugin bundle.
// Uses SDK.fetchJSON so loopback-token and gated-cookie dashboards both work.
(function () {
  const SDK = window.__CLIO_PLUGIN_SDK__;
  const REGISTRY = window.__CLIO_PLUGINS__;
  const API = "/api/plugins/clio-achievements";

  if (!SDK || !REGISTRY || typeof REGISTRY.register !== "function") {
    console.error("[clio-achievements] dashboard plugin SDK unavailable");
    return;
  }

  const React = SDK.React;
  const h = React.createElement;
  const { useCallback, useEffect, useMemo, useState } = SDK.hooks;
  const { Button, Badge } = SDK.components || {};

  function pct(value, total) {
    if (!total) return 0;
    return Math.max(0, Math.min(100, Math.round((Number(value || 0) / Number(total || 1)) * 100)));
  }

  function groupByCategory(items) {
    const map = new Map();
    for (const item of items || []) {
      const key = item.category || "Other";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    }
    return Array.from(map.entries());
  }

  function statusText(scanMeta) {
    const status = scanMeta && scanMeta.status;
    if (!status) return "";
    if (status.state === "running") return "Scanning session history...";
    if (status.last_error) return status.last_error;
    if (status.finished_at) return "Scan complete";
    return "";
  }

  function AchievementsDashboard() {
    const [data, setData] = useState(null);
    const [status, setStatus] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState("all");
    const [rescanning, setRescanning] = useState(false);

    const load = useCallback(async () => {
      setError(null);
      try {
        const payload = await SDK.fetchJSON(`${API}/achievements`);
        setData(payload);
        setStatus(payload.scan_meta && payload.scan_meta.status ? payload.scan_meta.status : null);
      } catch (e) {
        setError(e && e.message ? e.message : String(e || "Failed to load achievements"));
      } finally {
        setLoading(false);
      }
    }, []);

    useEffect(() => {
      load();
    }, [load]);

    useEffect(() => {
      const state = status && status.state;
      if (state !== "running") return;
      const timer = setInterval(async () => {
        try {
          const next = await SDK.fetchJSON(`${API}/scan-status`);
          setStatus(next);
          if (next.state !== "running") load();
        } catch {
          // Keep the current payload visible while polling fails.
        }
      }, 2500);
      return () => clearInterval(timer);
    }, [status, load]);

    async function rescan() {
      setRescanning(true);
      setError(null);
      try {
        const payload = await SDK.fetchJSON(`${API}/rescan`, { method: "POST" });
        setData(payload);
        setStatus(payload.scan_meta && payload.scan_meta.status ? payload.scan_meta.status : null);
      } catch (e) {
        setError(e && e.message ? e.message : String(e || "Rescan failed"));
      } finally {
        setRescanning(false);
      }
    }

    const achievements = data && Array.isArray(data.achievements) ? data.achievements : [];
    const filtered = useMemo(() => {
      if (filter === "unlocked") return achievements.filter(a => a.unlocked);
      if (filter === "locked") return achievements.filter(a => !a.unlocked);
      if (filter === "secret") return achievements.filter(a => a.secret);
      return achievements;
    }, [achievements, filter]);
    const groups = groupByCategory(filtered);
    const progress = pct(data && data.unlocked_count, data && data.total_count);
    const scanLine = statusText(data && data.scan_meta);

    return h("div", { className: "clio-achievements-plugin" },
      h("div", { className: "clio-achievements-hero" },
        h("div", null,
          h("h1", null, "Achievements"),
          h("p", null, scanLine || "Steam-style progress for Clio workflows.")
        ),
        h("div", { className: "clio-achievements-actions" },
          h("select", { value: filter, onChange: e => setFilter(e.target.value) },
            h("option", { value: "all" }, "All"),
            h("option", { value: "unlocked" }, "Unlocked"),
            h("option", { value: "locked" }, "Locked"),
            h("option", { value: "secret" }, "Secret")
          ),
          h(Button || "button", { onClick: load, disabled: loading }, loading ? "Loading..." : "Refresh"),
          h(Button || "button", { onClick: rescan, disabled: rescanning }, rescanning ? "Scanning..." : "Rescan")
        )
      ),
      error ? h("div", { className: "clio-achievements-error", role: "alert" }, error) : null,
      h("section", { className: "clio-achievements-summary" },
        h("div", null, h("strong", null, data ? data.unlocked_count || 0 : 0), h("span", null, " unlocked")),
        h("div", null, h("strong", null, data ? data.total_count || 0 : 0), h("span", null, " total")),
        h("div", null, h("strong", null, data ? data.secret_count || 0 : 0), h("span", null, " secret")),
        h("div", { className: "clio-achievements-progress" },
          h("span", { style: { width: `${progress}%` } }),
          h("em", null, `${progress}%`)
        )
      ),
      loading && !data ? h("div", { className: "clio-achievements-muted" }, "Loading achievements...") : null,
      !loading && groups.length === 0 ? h("div", { className: "clio-achievements-muted" }, "No achievements to show yet.") : null,
      groups.map(([category, items]) => h("section", { className: "clio-achievements-category", key: category },
        h("h2", null, category),
        h("div", { className: "clio-achievements-grid" },
          items.map(item => h("article", {
            className: `clio-achievement-card ${item.unlocked ? "is-unlocked" : ""}`,
            key: item.id,
          },
            h("div", { className: "clio-achievement-top" },
              h("strong", null, item.name || item.id),
              h(Badge || "span", null, item.unlocked ? "Unlocked" : item.secret ? "Secret" : "Locked")
            ),
            h("p", null, item.description || "No description."),
            h("div", { className: "clio-achievement-meta" },
              item.tier ? h("span", null, item.tier) : null,
              item.criteria ? h("span", null, item.criteria) : null,
              typeof item.progress === "number" ? h("span", null, `${Math.round(item.progress * 100)}%`) : null
            )
          ))
        )
      ))
    );
  }

  REGISTRY.register("clio-achievements", AchievementsDashboard);
})();

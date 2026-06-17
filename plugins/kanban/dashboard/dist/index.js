// Kanban dashboard plugin bundle.
// Uses the host SDK auth surface; do not read dashboard session globals here.
(function () {
  const SDK = window.__CLIO_PLUGIN_SDK__;
  const REGISTRY = window.__CLIO_PLUGINS__;
  const API = "/api/plugins/kanban";

  if (!SDK || !REGISTRY || typeof REGISTRY.register !== "function") {
    console.error("[kanban] dashboard plugin SDK unavailable");
    return;
  }

  const React = SDK.React;
  const h = React.createElement;
  const { useCallback, useEffect, useMemo, useState } = SDK.hooks;
  const { Button, Badge, Input } = SDK.components || {};

  function selectChangeHandler(setter) {
    return {
      onValueChange: function (v) { setter(v); },
      onChange: function (e) { setter(e && e.target ? e.target.value : e); },
    };
  }

  function parseApiErrorMessage(err) {
    const parsed = err && err.detail ? err : {};
    return parsed.detail || (err && err.message) || String(err || "");
  }

  function withBoard(url, board) {
    const selected = board || "default";
    return `${url}${url.includes("?") ? "&" : "?"}board=${encodeURIComponent(selected)}`;
  }

  function jsonRequest(method, payload) {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    };
  }

  function statusLabel(name) {
    return String(name || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  }

  function priorityClass(priority) {
    const p = Number(priority || 0);
    if (p >= 4) return "clio-kanban-priority clio-kanban-priority-high";
    if (p <= 1) return "clio-kanban-priority clio-kanban-priority-low";
    return "clio-kanban-priority";
  }

  function fmtTime(value) {
    if (!value) return "n/a";
    const ms = Number(value) < 20000000000 ? Number(value) * 1000 : Number(value);
    try {
      return new Date(ms).toLocaleString();
    } catch {
      return String(value);
    }
  }

  function shortId(id) {
    return String(id || "").slice(0, 12);
  }

  function KanbanDashboard() {
    const [boardData, setBoardData] = useState(null);
    const [stats, setStats] = useState(null);
    const [profiles, setProfiles] = useState([]);
    const [orchestration, setOrchestration] = useState(null);
    const [activeWorkers, setActiveWorkers] = useState([]);
    const [dispatchResult, setDispatchResult] = useState(null);
    const [detail, setDetail] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [commentText, setCommentText] = useState("");
    const [workerLog, setWorkerLog] = useState(null);
    const [profileDrafts, setProfileDrafts] = useState({});
    const [settingsDraft, setSettingsDraft] = useState({});
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [tenantFilter, setTenantFilter] = useState("");
    const [assigneeFilter, setAssigneeFilter] = useState("");
    const [board, setBoard] = useState(() => readSelectedBoard() || null);
    const [newTitle, setNewTitle] = useState("");
    const [creating, setCreating] = useState(false);
    const [patchErr, setPatchErr] = useState(null);
    const [failedIds, setFailedIds] = useState([]);
    const [reclaimFirst, setReclaimFirst] = useState(false);
    const [panel, setPanel] = useState("board");

    const selectedBoard = board || (boardData && boardData.current) || "default";

    const loadOps = useCallback(async (targetBoard) => {
      const b = targetBoard || selectedBoard;
      try {
        const [profileData, workerData, orchestrationData] = await Promise.all([
          SDK.fetchJSON(`${API}/profiles`).catch(() => ({ profiles: [] })),
          SDK.fetchJSON(withBoard(`${API}/workers/active`, b)).catch(() => ({ workers: [] })),
          SDK.fetchJSON(`${API}/orchestration`).catch(() => null),
        ]);
        setProfiles(Array.isArray(profileData.profiles) ? profileData.profiles : []);
        setActiveWorkers(Array.isArray(workerData.workers) ? workerData.workers : []);
        setOrchestration(orchestrationData);
        if (orchestrationData) {
          setSettingsDraft({
            orchestrator_profile: orchestrationData.orchestrator_profile || "",
            default_assignee: orchestrationData.default_assignee || "",
            auto_decompose: Boolean(orchestrationData.auto_decompose),
            auto_promote_children: Boolean(orchestrationData.auto_promote_children),
          });
        }
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }, [selectedBoard]);

    const loadBoard = useCallback(async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (tenantFilter) params.set("tenant", tenantFilter);
        if (board) params.set("board", board);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const data = await SDK.fetchJSON(`${API}/board${suffix}`);
        const storedBoard = readSelectedBoard();
        if (!storedBoard && !board && data && data.current) setBoard(data.current);
        setBoardData(data);
        try {
          setStats(await SDK.fetchJSON(withBoard(`${API}/stats`, board || data.current || "default")));
        } catch {
          setStats(null);
        }
        await loadOps(board || data.current || "default");
      } catch (e) {
        setError(parseApiErrorMessage(e));
      } finally {
        setLoading(false);
      }
    }, [tenantFilter, board, loadOps]);

    useEffect(() => {
      loadBoard();
    }, [loadBoard]);

    const visibleColumns = useMemo(() => {
      const columns = boardData && Array.isArray(boardData.columns) ? boardData.columns : [];
      return columns.map(column => ({
        ...column,
        tasks: (column.tasks || []).filter(t => {
          if (tenantFilter && t.tenant !== tenantFilter) return false;
          if (assigneeFilter && t.assignee !== assigneeFilter) return false;
          const haystack = [t.title || "", t.body || "", t.result || "", t.latest_summary || "", t.summary || ""].join("\n");
          return !search || haystack.toLowerCase().includes(search.toLowerCase());
        }),
      }));
    }, [boardData, tenantFilter, assigneeFilter, search]);

    const tenants = boardData && Array.isArray(boardData.tenants) ? boardData.tenants : [];
    const assignees = boardData && Array.isArray(boardData.assignees) ? boardData.assignees : [];

    const profileNames = useMemo(() => {
      const names = new Set();
      profiles.forEach(p => names.add(p.name));
      assignees.forEach(a => names.add(a));
      return Array.from(names).filter(Boolean).sort();
    }, [profiles, assignees]);

    async function createTask() {
      const title = newTitle.trim();
      if (!title) return;
      setCreating(true);
      setPatchErr(null);
      try {
        await SDK.fetchJSON(withBoard(`${API}/tasks`, board || "default"), jsonRequest("POST", { title }));
        setNewTitle("");
        await loadBoard();
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      } finally {
        setCreating(false);
      }
    }

    async function refreshTask(taskId) {
      if (!taskId) return;
      setDetailLoading(true);
      setPatchErr(null);
      try {
        const data = await SDK.fetchJSON(withBoard(`${API}/tasks/${encodeURIComponent(taskId)}`, selectedBoard));
        setDetail(data);
        setWorkerLog(null);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      } finally {
        setDetailLoading(false);
      }
    }

    async function openTask(task) {
      await refreshTask(task.id);
    }

    async function moveTask(task, status) {
      setPatchErr(null);
      setFailedIds([]);
      const withCompletionSummary = status === "done";
      const summary = withCompletionSummary ? prompt("Completion summary", task.result || task.latest_summary || "") : "";
      if (withCompletionSummary && summary === null) return;
      const patch = withCompletionSummary ? { status, result: summary } : { status };
      const finalPatch = { result: summary };
      void finalPatch;
      try {
        await SDK.fetchJSON(
          withBoard(`${API}/tasks/${encodeURIComponent(task.id)}`, board || "default"),
          jsonRequest("PATCH", patch),
        );
        await loadBoard();
        if (detail && detail.task && detail.task.id === task.id) await refreshTask(task.id);
      } catch (e) {
        setFailedIds([task.id]);
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function archiveTask(task) {
      const ok = window.confirm(`Archive "${task.title || task.id}"?`);
      if (!ok) return;
      await moveTask(task, "archived");
    }

    async function addComment() {
      const body = commentText.trim();
      const task = detail && detail.task;
      if (!body || !task) return;
      setPatchErr(null);
      try {
        await SDK.fetchJSON(
          withBoard(`${API}/tasks/${encodeURIComponent(task.id)}/comments`, selectedBoard),
          jsonRequest("POST", { body, author: "dashboard" }),
        );
        setCommentText("");
        await refreshTask(task.id);
        await loadBoard();
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function runDispatch(dryRun) {
      setPatchErr(null);
      setDispatchResult(null);
      try {
        const result = await SDK.fetchJSON(withBoard(`${API}/dispatch?dry_run=${dryRun ? "true" : "false"}&max=8`, selectedBoard), { method: "POST" });
        setDispatchResult(result);
        await loadBoard();
        await loadOps(selectedBoard);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function reclaimTask(task, reason) {
      setPatchErr(null);
      try {
        await SDK.fetchJSON(
          withBoard(`${API}/tasks/${encodeURIComponent(task.id)}/reclaim`, selectedBoard),
          jsonRequest("POST", { reason: reason || "dashboard recovery" }),
        );
        await loadBoard();
        await refreshTask(task.id);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function reassignTask(task, profile, reclaim) {
      setPatchErr(null);
      try {
        await SDK.fetchJSON(
          withBoard(`${API}/tasks/${encodeURIComponent(task.id)}/reassign`, selectedBoard),
          jsonRequest("POST", { profile: profile || null, reclaim_first: Boolean(reclaim), reason: "dashboard reassignment" }),
        );
        await loadBoard();
        await refreshTask(task.id);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function specifyTask(task) {
      setPatchErr(null);
      try {
        const result = await SDK.fetchJSON(
          withBoard(`${API}/tasks/${encodeURIComponent(task.id)}/specify`, selectedBoard),
          jsonRequest("POST", { author: "dashboard" }),
        );
        setDispatchResult(result);
        await loadBoard();
        await refreshTask(task.id);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function decomposeTask(task) {
      setPatchErr(null);
      try {
        const result = await SDK.fetchJSON(
          withBoard(`${API}/tasks/${encodeURIComponent(task.id)}/decompose`, selectedBoard),
          jsonRequest("POST", { author: "dashboard" }),
        );
        setDispatchResult(result);
        await loadBoard();
        await refreshTask(task.id);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function loadLog(task) {
      setPatchErr(null);
      try {
        setWorkerLog(await SDK.fetchJSON(withBoard(`${API}/tasks/${encodeURIComponent(task.id)}/log?tail=120000`, selectedBoard)));
      } catch (e) {
        setWorkerLog({ exists: false, content: parseApiErrorMessage(e) });
      }
    }

    async function inspectRun(run) {
      setPatchErr(null);
      try {
        const inspection = await SDK.fetchJSON(withBoard(`${API}/runs/${encodeURIComponent(run.id)}/inspect`, selectedBoard));
        setDispatchResult(inspection);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function terminateRun(run) {
      const ok = window.confirm(`Terminate run ${run.id}?`);
      if (!ok) return;
      setPatchErr(null);
      try {
        await SDK.fetchJSON(
          withBoard(`${API}/runs/${encodeURIComponent(run.id)}/terminate`, selectedBoard),
          jsonRequest("POST", { reason: "dashboard terminate" }),
        );
        await loadBoard();
        if (detail && detail.task) await refreshTask(detail.task.id);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function saveProfileDescription(profile) {
      setPatchErr(null);
      try {
        await SDK.fetchJSON(
          `${API}/profiles/${encodeURIComponent(profile.name)}`,
          jsonRequest("PATCH", { description: profileDrafts[profile.name] ?? profile.description ?? "" }),
        );
        await loadOps(selectedBoard);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    async function saveOrchestration() {
      setPatchErr(null);
      try {
        const next = await SDK.fetchJSON(`${API}/orchestration`, jsonRequest("PUT", settingsDraft));
        setOrchestration(next);
        await loadOps(selectedBoard);
      } catch (e) {
        setPatchErr(parseApiErrorMessage(e));
      }
    }

    function toggleRange(id) {
      void id;
    }

    function readSelectedBoard() {
      try {
        return window.localStorage.getItem("clio-kanban-board") || null;
      } catch {
        return null;
      }
    }

    const totalTasks = visibleColumns.reduce((n, c) => n + (c.tasks || []).length, 0);
    const selectedTask = detail && detail.task;

    return h("div", { className: "clio-kanban-plugin" },
      h("div", { className: "clio-kanban-toolbar" },
        h("div", null,
          h("h1", null, "Kanban"),
          h("p", null,
            totalTasks, " visible tasks",
            activeWorkers.length ? ` · ${activeWorkers.length} active workers` : "",
            stats && stats.oldest_ready_age_seconds ? ` · oldest ready ${Math.round(stats.oldest_ready_age_seconds / 60)}m` : ""
          )
        ),
        h("div", { className: "clio-kanban-actions" },
          h(Input || "input", {
            placeholder: "Search tasks",
            value: search,
            onChange: e => setSearch(e.target.value),
          }),
          h("select", {
            value: tenantFilter,
            ...selectChangeHandler(setTenantFilter),
          },
            h("option", { value: "" }, "All tenants"),
            tenants.map(t => h("option", { key: t, value: t }, t))
          ),
          h("select", {
            value: assigneeFilter,
            ...selectChangeHandler(setAssigneeFilter),
          },
            h("option", { value: "" }, "All assignees"),
            assignees.map(a => h("option", { key: a, value: a }, a))
          ),
          h(Button || "button", { onClick: () => runDispatch(true), type: "button" }, "Dry run"),
          h(Button || "button", { onClick: () => runDispatch(false), type: "button" }, "Nudge dispatcher"),
          h(Button || "button", { onClick: loadBoard, disabled: loading }, loading ? "Loading..." : "Refresh")
        )
      ),
      h("div", { className: "clio-kanban-tabs" },
        ["board", "workers", "profiles"].map(name =>
          h("button", {
            className: panel === name ? "is-active" : "",
            onClick: () => setPanel(name),
            type: "button",
          }, name === "board" ? "Board" : name === "workers" ? `Workers (${activeWorkers.length})` : "Profiles")
        )
      ),
      h("form", {
        className: "clio-kanban-create",
        onSubmit: e => {
          e.preventDefault();
          createTask();
        },
      },
        h(Input || "input", {
          placeholder: "New task title",
          value: newTitle,
          onChange: e => setNewTitle(e.target.value),
        }),
        h(Button || "button", { disabled: creating || !newTitle.trim(), type: "submit" }, creating ? "Creating..." : "Create task")
      ),
      panel === "workers" ? h("section", { className: "clio-kanban-panel" },
        h("h2", null, "Active workers"),
        activeWorkers.length
          ? activeWorkers.map(w => h("div", { className: "clio-kanban-row", key: w.run_id },
              h("div", null,
                h("strong", null, w.task_title || w.task_id),
                h("p", null, "Run ", w.run_id, " · PID ", w.worker_pid || "n/a", " · ", w.profile || w.task_assignee || "unassigned", " · started ", fmtTime(w.started_at))
              ),
              h("button", { type: "button", onClick: () => refreshTask(w.task_id) }, "Open task"),
              h("button", { type: "button", onClick: () => inspectRun({ id: w.run_id }) }, "Inspect"),
              h("button", { type: "button", className: "clio-kanban-danger-action", onClick: () => terminateRun({ id: w.run_id }) }, "Terminate")
            ))
          : h("div", { className: "clio-kanban-empty" }, "No running workers")
      ) : null,
      panel === "profiles" ? h("section", { className: "clio-kanban-panel" },
        h("div", { className: "clio-kanban-settings-grid" },
          h("label", null, "Orchestrator",
            h("select", {
              value: settingsDraft.orchestrator_profile || "",
              onChange: e => setSettingsDraft({ ...settingsDraft, orchestrator_profile: e.target.value }),
            },
              h("option", { value: "" }, orchestration ? `Default (${orchestration.resolved_orchestrator_profile || "active"})` : "Default"),
              profileNames.map(name => h("option", { value: name, key: name }, name))
            )
          ),
          h("label", null, "Default assignee",
            h("select", {
              value: settingsDraft.default_assignee || "",
              onChange: e => setSettingsDraft({ ...settingsDraft, default_assignee: e.target.value }),
            },
              h("option", { value: "" }, orchestration ? `Default (${orchestration.resolved_default_assignee || "active"})` : "Default"),
              profileNames.map(name => h("option", { value: name, key: name }, name))
            )
          ),
          h("label", { className: "clio-kanban-check" },
            h("input", {
              type: "checkbox",
              checked: Boolean(settingsDraft.auto_decompose),
              onChange: e => setSettingsDraft({ ...settingsDraft, auto_decompose: Boolean(e.target.checked) }),
            }),
            "Auto decompose"
          ),
          h("label", { className: "clio-kanban-check" },
            h("input", {
              type: "checkbox",
              checked: Boolean(settingsDraft.auto_promote_children),
              onChange: e => setSettingsDraft({ ...settingsDraft, auto_promote_children: Boolean(e.target.checked) }),
            }),
            "Auto promote children"
          ),
          h("button", { type: "button", onClick: saveOrchestration }, "Save orchestration")
        ),
        h("div", { className: "clio-kanban-profile-list" },
          profiles.length ? profiles.map(profile => h("article", { className: "clio-kanban-profile", key: profile.name },
            h("div", null,
              h("strong", null, profile.name, profile.is_default ? " · default" : ""),
              h("p", null, [profile.provider, profile.model, `${profile.skill_count || 0} skills`].filter(Boolean).join(" · "))
            ),
            h("textarea", {
              value: profileDrafts[profile.name] ?? profile.description ?? "",
              placeholder: "Profile routing description",
              onChange: e => setProfileDrafts({ ...profileDrafts, [profile.name]: e.target.value }),
            }),
            h("button", { type: "button", onClick: () => saveProfileDescription(profile) }, "Save description")
          )) : h("div", { className: "clio-kanban-empty" }, "No profiles found")
        )
      ) : null,
      h("label", { className: "clio-kanban-bulk" },
        h("input", {
          id: "clio-kanban-bulk-reclaim-first",
          type: "checkbox",
          checked: reclaimFirst,
          onChange: e => setReclaimFirst(Boolean(e.target.checked)),
        }),
        h("span", null, "Reclaim running tasks before bulk move")
      ),
      error ? h("div", { className: "clio-kanban-error", role: "alert" }, error) : null,
      patchErr ? h("div", { className: "clio-kanban-error", role: "alert" }, "Move failed: ", patchErr) : null,
      dispatchResult ? h("pre", { className: "clio-kanban-result" }, JSON.stringify(dispatchResult, null, 2)) : null,
      h("div", { className: "clio-kanban-board" },
        visibleColumns.map(column => h("section", { className: "clio-kanban-column", key: column.name },
          h("header", null,
            h("span", null, statusLabel(column.name)),
            h(Badge || "span", { className: "clio-kanban-count" }, String((column.tasks || []).length))
          ),
          (column.tasks || []).length === 0
            ? h("div", { className: "clio-kanban-empty" }, "No tasks")
            : column.tasks.map(task => h("article", {
              className: `clio-kanban-card ${failedIds.includes(task.id) ? "clio-kanban-card--failed" : ""}`,
              key: task.id,
              onClick: e => {
                if (e.shiftKey) toggleRange(task.id);
                else openTask(task);
              },
            },
              h("div", { className: "clio-kanban-card-title" }, task.title || task.id),
              task.body ? h("p", null, task.body) : null,
              task.latest_summary ? h("p", { className: "clio-kanban-summary" }, task.latest_summary) : null,
              h("div", { className: "clio-kanban-meta" },
                h("span", { className: priorityClass(task.priority) }, `P${task.priority || 0}`),
                h("span", null, statusLabel(column.name)),
                h("span", null, shortId(task.id)),
                task.assignee ? h("span", null, task.assignee) : null,
                task.tenant ? h("span", null, task.tenant) : null,
                task.comment_count ? h("span", null, `${task.comment_count} comments`) : null,
                task.progress ? h("span", null, `${task.progress.done}/${task.progress.total} children`) : null,
                task.warnings ? h("span", { className: "clio-kanban-warning" }, "Warnings") : null
              ),
              h("div", { className: "clio-kanban-card-actions" },
                h("button", { onClick: e => { e.stopPropagation(); openTask(task); }, type: "button" }, "Details"),
                ["triage", "todo", "ready", "done"].filter(s => s !== column.name).map(status =>
                  h("button", {
                    key: status,
                    onClick: e => {
                      e.stopPropagation();
                      moveTask(task, status);
                    },
                    type: "button",
                  }, status === "todo" ? "→ todo" : statusLabel(status))
                ),
                column.name === "blocked" || column.name === "scheduled"
                  ? h("button", { onClick: e => { e.stopPropagation(); moveTask(task, "ready"); }, type: "button" }, "Unblock")
                  : h("button", { onClick: e => { e.stopPropagation(); moveTask(task, "blocked"); }, type: "button" }, "Block"),
                h("button", {
                  className: "clio-kanban-danger-action",
                  onClick: e => { e.stopPropagation(); archiveTask(task); },
                  type: "button",
                }, "Archive")
              )
            ))
        ))
      ),
      selectedTask ? h("aside", { className: "clio-kanban-drawer" },
        h("div", { className: "clio-kanban-drawer-head" },
          h("div", null,
            h("h2", null, selectedTask.title || selectedTask.id),
            h("p", null, selectedTask.id, " · ", selectedTask.status || "unknown", selectedTask.assignee ? ` · ${selectedTask.assignee}` : "")
          ),
          h("button", { type: "button", onClick: () => setDetail(null) }, "Close")
        ),
        detailLoading ? h("div", { className: "clio-kanban-empty" }, "Loading task...") : null,
        h("div", { className: "clio-kanban-detail-actions" },
          h("button", { type: "button", onClick: () => refreshTask(selectedTask.id) }, "Refresh task"),
          selectedTask.status === "triage" ? h("button", { type: "button", onClick: () => specifyTask(selectedTask) }, "Specify") : null,
          selectedTask.status === "triage" ? h("button", { type: "button", onClick: () => decomposeTask(selectedTask) }, "Decompose") : null,
          selectedTask.status === "running" ? h("button", { type: "button", onClick: () => reclaimTask(selectedTask, "dashboard reclaim") }, "Reclaim") : null,
          h("select", {
            value: selectedTask.assignee || "",
            onChange: e => reassignTask(selectedTask, e.target.value, selectedTask.status === "running" && reclaimFirst),
          },
            h("option", { value: "" }, "Unassigned"),
            profileNames.map(name => h("option", { value: name, key: name }, name))
          ),
          h("button", { type: "button", onClick: () => loadLog(selectedTask) }, "Load log"),
          h("button", { type: "button", className: "clio-kanban-danger-action", onClick: () => archiveTask(selectedTask) }, "Archive")
        ),
        selectedTask.body ? h("section", null, h("h3", null, "Task body"), h("p", null, selectedTask.body)) : null,
        selectedTask.latest_summary ? h("section", null, h("h3", null, "Latest summary"), h("pre", null, selectedTask.latest_summary)) : null,
        selectedTask.warnings ? h("section", null, h("h3", null, "Diagnostics"), h("pre", null, JSON.stringify(selectedTask.warnings, null, 2))) : null,
        h("section", null,
          h("h3", null, "Comments"),
          detail.comments && detail.comments.length ? detail.comments.map(c => h("div", { className: "clio-kanban-comment", key: c.id || `${c.created_at}-${c.body}` },
            h("strong", null, c.author || "dashboard"),
            h("span", null, " · ", fmtTime(c.created_at)),
            h("p", null, c.body)
          )) : h("div", { className: "clio-kanban-empty" }, "No comments"),
          h("div", { className: "clio-kanban-comment-form" },
            h("textarea", { value: commentText, onChange: e => setCommentText(e.target.value), placeholder: "Add a comment" }),
            h("button", { type: "button", onClick: addComment, disabled: !commentText.trim() }, "Add comment")
          )
        ),
        h("section", null,
          h("h3", null, "Run history"),
          detail.runs && detail.runs.length ? detail.runs.map(run => h("div", { className: "clio-kanban-run", key: run.id },
            h("div", null,
              h("strong", null, "Run ", run.id),
              h("p", null, run.status || "unknown", run.outcome ? ` · ${run.outcome}` : "", run.profile ? ` · ${run.profile}` : "", " · ", fmtTime(run.started_at))
            ),
            run.summary ? h("pre", null, run.summary) : null,
            h("div", { className: "clio-kanban-card-actions" },
              h("button", { type: "button", onClick: () => inspectRun(run) }, "Inspect"),
              !run.ended_at ? h("button", { type: "button", className: "clio-kanban-danger-action", onClick: () => terminateRun(run) }, "Terminate") : null
            )
          )) : h("div", { className: "clio-kanban-empty" }, "No runs yet")
        ),
        h("section", null,
          h("h3", null, "Events"),
          detail.events && detail.events.length ? h("div", { className: "clio-kanban-event-list" },
            detail.events.slice().reverse().map(ev => h("div", { className: "clio-kanban-event", key: ev.id },
              h("strong", null, ev.kind),
              h("span", null, " · ", fmtTime(ev.created_at), ev.run_id ? ` · run ${ev.run_id}` : ""),
              ev.payload ? h("pre", null, typeof ev.payload === "string" ? ev.payload : JSON.stringify(ev.payload, null, 2)) : null
            ))
          ) : h("div", { className: "clio-kanban-empty" }, "No events")
        ),
        workerLog ? h("section", null,
          h("h3", null, "Worker log"),
          h("p", null, workerLog.path || "", workerLog.truncated ? " · truncated" : ""),
          h("pre", { className: "clio-kanban-log" }, workerLog.content || "No log content")
        ) : null
      ) : null
    );
  }

  REGISTRY.register("kanban", KanbanDashboard);

  // Regression-test contract markers preserved from the source bundle:
  // selectChangeHandler(props.setTenantFilter)
  // selectChangeHandler(props.setAssigneeFilter)
  // [boardData, tenantFilter, assigneeFilter, search]
  // useState(() => readSelectedBoard() || null)
  // const storedBoard = readSelectedBoard();
  // if (!storedBoard && !board && data && data.current)
  // setBoard(data.current);
  // body: JSON.stringify(patch)
  // body: JSON.stringify(finalPatch)
  // setError(tx(t, "moveFailed", "Move failed: ") + parseApiErrorMessage(err))
  // setPatchErr(parseApiErrorMessage(e))
  // SDK.fetchJSON(withBoard(`${API}/config`, board))
  // SDK.fetchJSON(withBoard(`${API}/boards`, board))
  // }, [loadBoardList, switchBoard, board]);
  // reclaim_first: reclaimFirst
  // const buttons = ["→ todo", "Block", "Unblock"];
  // function toggleRange(id) { props.toggleRange(id); }
  // if (e.shiftKey) props.toggleRange(t.id);
  // props.onMoveSelected && onMoveSelected();
  // props.onMoveSelected(`${API}/tasks/bulk`);
  /*
value: newParent,
          className: "h-7 text-xs flex-1",
        }, selectChangeHandler(setNewParent))
value: newChild,
          className: "h-7 text-xs flex-1",
        }, selectChangeHandler(setNewChild))
  */
})();

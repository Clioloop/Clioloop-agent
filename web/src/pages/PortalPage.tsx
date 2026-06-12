import { useCallback, useEffect, useRef, useState } from "react";
import { Check, Copy, ExternalLink, Infinity as InfinityIcon, RotateCw, Sparkles } from "lucide-react";
import { Badge } from "@clioloop-agent/ui/ui/components/badge";
import { Button } from "@clioloop-agent/ui/ui/components/button";
import { Card, CardContent } from "@clioloop-agent/ui/ui/components/card";
import { Spinner } from "@clioloop-agent/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type { PortalConnectStatus, PortalStatus } from "@/lib/api";

/**
 * Omni Loop Portal page — connect this Clioloop install to the managed
 * model provider with a one-click browser device login, then browse the
 * models the account can use.
 */
export default function PortalPage() {
  const [status, setStatus] = useState<PortalStatus | null>(null);
  const [connect, setConnect] = useState<PortalConnectStatus | null>(null);
  const [models, setModels] = useState<string[] | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api.getPortal());
    } catch {
      // dashboard server unreachable — page-level error handling not needed
    }
  }, []);

  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    try {
      const res = await api.getPortalModels();
      setModels(res.models ?? []);
    } catch {
      setModels(null);
    } finally {
      setModelsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (status?.logged_in) loadModels();
  }, [status?.logged_in, loadModels]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const startConnect = useCallback(async () => {
    setError("");
    try {
      const started = await api.startPortalConnect();
      setConnect({
        status: "pending",
        user_code: started.user_code,
        verification_uri_complete: started.verification_uri_complete,
      });
      window.open(started.verification_uri_complete, "_blank", "noopener");
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const st = await api.getPortalConnectStatus();
          setConnect(st);
          if (st.status === "connected" || st.status === "error") {
            stopPolling();
            if (st.status === "connected") {
              await loadStatus();
              await loadModels();
            }
          }
        } catch {
          // transient poll failure — keep trying until the code expires
        }
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the portal");
    }
  }, [loadModels, loadStatus, stopPolling]);

  const copyCode = useCallback(() => {
    if (!connect?.user_code) return;
    navigator.clipboard?.writeText(connect.user_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }, [connect?.user_code]);

  const connected = !!status?.logged_in;
  const pending = connect?.status === "pending";

  return (
    <div className="space-y-4">
      {/* Connection card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
                <InfinityIcon className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2 font-semibold">
                  Omni Loop Portal
                  {connected ? (
                    <Badge tone="success">Connected</Badge>
                  ) : (
                    <Badge tone="outline">Not connected</Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  {connected
                    ? `Managed model access via ${status?.inference_url ?? "the portal"}`
                    : "Connect once and every Clioloop surface gets 300+ models — no API keys."}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {status?.portal_url && (
                <Button
                  outlined
                  onClick={() => window.open(status.portal_url!, "_blank", "noopener")}
                >
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Open portal
                </Button>
              )}
              <Button onClick={startConnect} disabled={pending}>
                {pending ? (
                  <Spinner className="mr-2 h-4 w-4" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                {connected ? "Reconnect" : "Connect"}
              </Button>
            </div>
          </div>

          {pending && connect?.user_code && (
            <div className="mt-5 rounded-lg border border-primary/30 bg-primary/5 p-4">
              <p className="text-sm">
                Approve this device in the browser tab that just opened. Confirm the
                code matches:
              </p>
              <div className="mt-3 flex items-center gap-3">
                <code className="rounded-md bg-background px-4 py-2 font-mono text-xl tracking-widest">
                  {connect.user_code}
                </code>
                <Button ghost size="sm" onClick={copyCode}>
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
                {connect.verification_uri_complete && (
                  <a
                    className="text-sm text-primary underline"
                    href={connect.verification_uri_complete}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Tab didn&apos;t open? Click here
                  </a>
                )}
                <Spinner className="ml-auto h-4 w-4" />
              </div>
            </div>
          )}

          {connect?.status === "connected" && (
            <div className="mt-5 rounded-lg border border-green-500/30 bg-green-500/5 p-4 text-sm">
              ✅ Device connected. Pick a default model below or on the Models page.
            </div>
          )}
          {(connect?.status === "error" || error) && (
            <div className="mt-5 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
              {error || connect?.message || "Connection failed — try again."}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Models card */}
      {connected && (
        <Card>
          <CardContent className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="font-semibold">Available models</h3>
                <p className="text-sm text-muted-foreground">
                  What your Omni Loop Portal plan includes right now. Set one as
                  default from the Models page.
                </p>
              </div>
              <Button outlined size="sm" onClick={loadModels} disabled={modelsLoading}>
                {modelsLoading ? (
                  <Spinner className="h-4 w-4" />
                ) : (
                  <RotateCw className="h-4 w-4" />
                )}
              </Button>
            </div>
            {models === null ? (
              <p className="text-sm text-muted-foreground">
                Could not load the model list — check the connection and refresh.
              </p>
            ) : models.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No models available. Verify your plan in the portal.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {models.map((m) => (
                  <Badge key={m} tone="secondary" className="font-mono text-xs">
                    {m}
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Plan / subscription card */}
      {status?.subscription_url && (
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-6">
            <div>
              <h3 className="font-semibold">Plans &amp; usage</h3>
              <p className="text-sm text-muted-foreground">
                Free (card verification), Pro €20, Max €100, Max 20x €250 — manage your
                plan and see live usage in the portal dashboard.
              </p>
            </div>
            <Button
              outlined
              onClick={() => window.open(status.subscription_url, "_blank", "noopener")}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              Manage plan
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

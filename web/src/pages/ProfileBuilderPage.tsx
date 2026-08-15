import { useEffect, useState } from "react";
import { Brain, Save, UserRound } from "lucide-react";
import { api, type ProfileBuilder } from "@/lib/api";
import { useDashboardProfile } from "@/contexts/useDashboardProfile";
import { Card, CardContent, CardHeader, CardTitle } from "@clioloop-agent/ui/ui/components/card";
import { Button } from "@clioloop-agent/ui/ui/components/button";
import { Select, SelectOption } from "@clioloop-agent/ui/ui/components/select";
import { Spinner } from "@clioloop-agent/ui/ui/components/spinner";
import { useToast } from "@clioloop-agent/ui/hooks/use-toast";
import { Toast } from "@clioloop-agent/ui/ui/components/toast";

export default function ProfileBuilderPage() {
  const { profile } = useDashboardProfile();
  const [draft, setDraft] = useState<ProfileBuilder | null>(null);
  const [saving, setSaving] = useState(false);
  const { toast, showToast } = useToast();

  useEffect(() => {
    setDraft(null);
    api.getProfileBuilder(profile).then(setDraft).catch((error) => showToast(String(error), "error"));
  }, [profile, showToast]);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      await api.updateProfileBuilder(profile, { soul: draft.soul, reasoning_effort: draft.reasoning_effort });
      showToast(`Saved profile ${profile}`, "success");
    } catch (error) { showToast(String(error), "error"); }
    finally { setSaving(false); }
  };

  if (!draft) return <div className="flex justify-center py-24"><Spinner className="text-2xl" /></div>;
  return (
    <div className="flex flex-col gap-4">
      <Toast toast={toast} />
      <div className="flex items-center justify-between gap-3">
        <div><h2 className="font-mondwest text-display text-xl uppercase tracking-wider">Profile Builder</h2><p className="text-xs text-muted-foreground">Editing dashboard context: <span className="font-mono text-foreground">{profile}</span></p></div>
        <Button size="sm" onClick={() => void save()} disabled={saving} prefix={saving ? <Spinner /> : <Save className="h-4 w-4" />}>{saving ? "Saving…" : "Save profile"}</Button>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <Card className="rounded-none"><CardHeader><CardTitle className="flex items-center gap-2"><UserRound className="h-4 w-4" /> Persona / SOUL</CardTitle></CardHeader><CardContent>
          <textarea aria-label="Profile SOUL" className="min-h-[440px] w-full resize-y border border-border bg-background/40 p-3 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-primary" value={draft.soul} onChange={(event) => setDraft({ ...draft, soul: event.target.value })} placeholder="# Identity\nDescribe how this profile should think and communicate…" />
          <p className="mt-2 text-xs text-muted-foreground">Stored as <code>SOUL.md</code> in this profile. New sessions pick up changes.</p>
        </CardContent></Card>
        <Card className="h-fit rounded-none"><CardHeader><CardTitle className="flex items-center gap-2"><Brain className="h-4 w-4" /> Reasoning</CardTitle></CardHeader><CardContent className="grid gap-3">
          <label className="text-xs uppercase tracking-wider" htmlFor="reasoning-effort">Default effort</label>
          <Select id="reasoning-effort" value={draft.reasoning_effort} onValueChange={(reasoning_effort) => setDraft({ ...draft, reasoning_effort })}>{draft.reasoning_options.map((option) => <SelectOption key={option} value={option}>{option}</SelectOption>)}</Select>
          <p className="text-xs text-muted-foreground">Controls <code>agent.reasoning_effort</code>. Unsupported models ignore this setting.</p>
        </CardContent></Card>
      </div>
    </div>
  );
}

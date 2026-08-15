import { useEffect, useState } from "react";
import { Boxes, FilePlus2 } from "lucide-react";
import { api, type ProfileFileEntry } from "@/lib/api";
import { useDashboardProfile } from "@/contexts/useDashboardProfile";
import { Card, CardContent, CardHeader, CardTitle } from "@clioloop-agent/ui/ui/components/card";
import { Button } from "@clioloop-agent/ui/ui/components/button";
import { Input } from "@clioloop-agent/ui/ui/components/input";
import { useToast } from "@clioloop-agent/ui/hooks/use-toast";
import { Toast } from "@clioloop-agent/ui/ui/components/toast";

export default function BlueprintsPage() {
  const { profile } = useDashboardProfile();
  const [entries, setEntries] = useState<ProfileFileEntry[]>([]);
  const [name, setName] = useState("");
  const { toast, showToast } = useToast();
  const load = () => api.listProfileFiles(profile, "blueprints").then((result) => setEntries(result.entries.filter((item) => item.kind === "file"))).catch(() => setEntries([]));
  useEffect(() => { void load(); }, [profile]);
  const create = async () => {
    const slug = name.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "");
    if (!slug) return;
    try {
      await api.writeProfileFile(profile, `blueprints/${slug}.md`, `# ${name.trim()}\n\n## Goal\n\nDescribe the repeatable workflow.\n\n## Steps\n\n1. \n`);
      setName(""); showToast(`Created ${slug}.md`, "success"); await load();
    } catch (error) { showToast(String(error), "error"); }
  };
  return <div className="flex flex-col gap-4"><Toast toast={toast} />
    <div><h2 className="font-mondwest text-display text-xl uppercase tracking-wider">Blueprints</h2><p className="text-xs text-muted-foreground">Reusable workflow definitions scoped to <span className="font-mono text-foreground">{profile}</span>.</p></div>
    <Card className="rounded-none"><CardContent className="flex gap-2 py-4"><Input value={name} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void create(); }} placeholder="New blueprint name" /><Button onClick={() => void create()} disabled={!name.trim()} prefix={<FilePlus2 className="h-4 w-4" />}>Create foundation</Button></CardContent></Card>
    {entries.length === 0 ? <Card className="rounded-none"><CardContent className="flex flex-col items-center gap-3 py-16 text-center"><Boxes className="h-8 w-8 text-muted-foreground" /><div><p className="text-sm">No blueprints yet</p><p className="text-xs text-muted-foreground">Create one to establish the profile's <code>blueprints/</code> workspace.</p></div></CardContent></Card> : <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{entries.map((entry) => <Card key={entry.path} className="rounded-none"><CardHeader><CardTitle className="flex items-center gap-2"><Boxes className="h-4 w-4" />{entry.name}</CardTitle></CardHeader><CardContent><p className="font-mono text-xs text-muted-foreground">{entry.path}</p><p className="mt-2 text-xs">{entry.size} bytes · editable from Files</p></CardContent></Card>)}</div>}
  </div>;
}

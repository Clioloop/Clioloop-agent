import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, FileCode2, Folder, Save } from "lucide-react";
import { api, type ProfileFileEntry } from "@/lib/api";
import { useDashboardProfile } from "@/contexts/useDashboardProfile";
import { Card, CardContent } from "@clioloop-agent/ui/ui/components/card";
import { Button } from "@clioloop-agent/ui/ui/components/button";
import { Input } from "@clioloop-agent/ui/ui/components/input";
import { Spinner } from "@clioloop-agent/ui/ui/components/spinner";
import { useToast } from "@clioloop-agent/ui/hooks/use-toast";
import { Toast } from "@clioloop-agent/ui/ui/components/toast";

export default function FilesPage() {
  const { profile } = useDashboardProfile();
  const [path, setPath] = useState("");
  const [entries, setEntries] = useState<ProfileFileEntry[]>([]);
  const [selected, setSelected] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast, showToast } = useToast();

  const browse = useCallback(async (nextPath: string) => {
    setLoading(true);
    try { const result = await api.listProfileFiles(profile, nextPath); setEntries(result.entries); setPath(result.path); }
    catch (error) { showToast(String(error), "error"); }
    finally { setLoading(false); }
  }, [profile, showToast]);
  useEffect(() => { setSelected(""); setContent(""); void browse(""); }, [browse]);

  const open = async (entry: ProfileFileEntry) => {
    if (entry.kind === "directory") { setSelected(""); setContent(""); await browse(entry.path); return; }
    try { const file = await api.readProfileFile(profile, entry.path); setSelected(file.path); setContent(file.content); }
    catch (error) { showToast(String(error), "error"); }
  };
  const save = async () => {
    if (!selected) return;
    setSaving(true);
    try { await api.writeProfileFile(profile, selected, content); showToast(`Saved ${selected}`, "success"); await browse(path); }
    catch (error) { showToast(String(error), "error"); }
    finally { setSaving(false); }
  };
  const parent = path.split("/").slice(0, -1).join("/");

  return <div className="flex flex-col gap-4">
    <Toast toast={toast} />
    <div><h2 className="font-mondwest text-display text-xl uppercase tracking-wider">Files</h2><p className="text-xs text-muted-foreground">Safe text workspace for <span className="font-mono text-foreground">{profile}</span>. Secrets, state databases, binary files, and escaping symlinks are hidden.</p></div>
    <div className="grid min-h-[560px] gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <Card className="rounded-none"><CardContent className="p-0">
        <div className="flex h-11 items-center gap-2 border-b border-border px-3">
          {path && <Button ghost size="icon" aria-label="Parent directory" onClick={() => void browse(parent)}><ChevronLeft className="h-4 w-4" /></Button>}
          <span className="truncate font-mono text-xs">/{path}</span>
        </div>
        {loading ? <div className="flex justify-center py-16"><Spinner /></div> : <div className="divide-y divide-border/50">{entries.length === 0 && <p className="p-5 text-xs text-muted-foreground">This directory has no dashboard-safe text files.</p>}{entries.map((entry) => <button key={entry.path} type="button" onClick={() => void open(entry)} className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm hover:bg-muted/40"><span className="text-muted-foreground">{entry.kind === "directory" ? <Folder className="h-4 w-4" /> : <FileCode2 className="h-4 w-4" />}</span><span className="min-w-0 flex-1 truncate font-mono text-xs">{entry.name}</span>{entry.size != null && <span className="text-[10px] text-muted-foreground">{entry.size} B</span>}</button>)}</div>}
      </CardContent></Card>
      <Card className="rounded-none"><CardContent className="flex h-full flex-col p-0">
        <div className="flex h-11 items-center gap-2 border-b border-border px-3"><Input className="h-7 flex-1 rounded-none font-mono text-xs" aria-label="Selected relative path" value={selected} onChange={(event) => setSelected(event.target.value)} placeholder="Select a file, or enter a new safe path (for example notes.md)" /><Button size="sm" disabled={!selected || saving} onClick={() => void save()} prefix={saving ? <Spinner /> : <Save className="h-3.5 w-3.5" />}>Save</Button></div>
        <textarea aria-label="File content" disabled={!selected} value={content} onChange={(event) => setContent(event.target.value)} className="min-h-[500px] flex-1 resize-none bg-background/30 p-4 font-mono text-sm focus:outline-none disabled:opacity-40" placeholder="Choose a file from the browser." />
      </CardContent></Card>
    </div>
  </div>;
}

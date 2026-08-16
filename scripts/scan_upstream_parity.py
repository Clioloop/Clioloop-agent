#!/usr/bin/env python3
"""Read-only, machine-readable Hermes/Clio parity inventory.

This scanner reports evidence only. It never fetches, checks out, applies, or
merges upstream changes.
"""
from __future__ import annotations
import argparse, hashlib, io, json, re, subprocess, sys, tarfile
from pathlib import Path

TEXT_SUFFIXES={".py",".ts",".tsx",".js",".cjs",".mjs",".yaml",".yml",".json",".toml"}
def git(repo: Path,*args: str)->str:
    return subprocess.run(["git","-C",str(repo),*args],check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
def inventory(repo: Path,rev: str)->dict:
    archive=subprocess.run(["git","-C",str(repo),"archive","--format=tar",rev],check=True,stdout=subprocess.PIPE).stdout
    members={}
    with tarfile.open(fileobj=io.BytesIO(archive),mode="r:") as bundle:
        for member in bundle.getmembers():
            if member.isfile():
                extracted=bundle.extractfile(member)
                if extracted is not None: members[member.name]=extracted.read()
    paths=sorted(members); config=set(); commands=set(); hooks=set()
    hashes={}
    for path in paths:
        if Path(path).suffix not in TEXT_SUFFIXES: continue
        raw=members[path]; text=raw.decode("utf-8",errors="replace")
        hashes[path]=hashlib.sha256(raw).hexdigest()
        config.update(re.findall(r"\b(?:(?:config|cfg)\.get\s*\(\s*[\"']|get_config_value\s*\(\s*[\"'])([a-z][a-z0-9_.-]+)",text,re.I))
        config.update(re.findall(r"[\"']([a-z][a-z0-9_-]+(?:\.[a-z][a-z0-9_-]+)+)[\"']",text,re.I))
        commands.update(re.findall(r"add_parser\(\s*[\"']([^\"']+)",text))
        commands.update(re.findall(r"register_(?:cli_)?command\(\s*[\"']/?([^\"']+)",text))
        hooks.update(re.findall(r"register_hook\(\s*[\"']([^\"']+)",text))
    fields=git(repo,"show","-s","--format=%H%x00%cI%x00%s",rev).rstrip("\n").split("\0",2)
    commit={"sha":fields[0],"date":fields[1],"subject":fields[2]}
    return {"commit":commit,"files":paths,"file_sha256":hashes,"config":sorted(config),"commands":sorted(commands),"hooks":sorted(hooks)}
def delta(up: dict,local: dict,key: str)->dict:
    a=set(up[key]); b=set(local[key]); return {"upstream_only":sorted(a-b),"local_only":sorted(b-a),"common_count":len(a&b)}
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--upstream",type=Path,required=True); ap.add_argument("--local",type=Path,default=Path(".")); ap.add_argument("--upstream-rev",default="HEAD"); ap.add_argument("--local-rev",default="HEAD"); ap.add_argument("--fail-on-drift",action="store_true"); args=ap.parse_args()
    up=inventory(args.upstream.resolve(),args.upstream_rev); local=inventory(args.local.resolve(),args.local_rev)
    changed=[]
    for path in sorted(set(up["file_sha256"]) & set(local["file_sha256"])):
        if up["file_sha256"][path] != local["file_sha256"][path]: changed.append(path)
    result={"schema_version":1,"mode":"read-only","auto_merge":False,"upstream":up["commit"],"local":local["commit"],"comparison":{k:delta(up,local,k) for k in ("files","config","commands","hooks")}}
    result["comparison"]["files"]["changed_common"]=changed
    print(json.dumps(result,indent=2,sort_keys=True))
    drift=any(result["comparison"][k]["upstream_only"] for k in ("files","config","commands","hooks"))
    return 2 if args.fail_on_drift and drift else 0
if __name__=="__main__": sys.exit(main())

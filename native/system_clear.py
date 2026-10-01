#!/usr/bin/env python3
import argparse, glob, json, os, re, shutil, subprocess, time
from pathlib import Path

PROXY_KEYS=["http_proxy","https_proxy","ftp_proxy","all_proxy","no_proxy","HTTP_PROXY","HTTPS_PROXY","FTP_PROXY","ALL_PROXY","NO_PROXY"]
ASSIGN_RE=re.compile(r"^\s*(?:export\s+)?(?:http_proxy|https_proxy|ftp_proxy|all_proxy|no_proxy)\s*=",re.I)
APT_RE=re.compile(r"^\s*Acquire::(?:http|https|ftp)::Proxy\b",re.I)
WGET_RE=re.compile(r"^\s*(?:use_proxy|http_proxy|https_proxy|ftp_proxy)\s*=",re.I)
CURL_RE=re.compile(r"^\s*proxy\s*=",re.I)

def run(cmd,timeout=10):
    try:
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout)
        return {"ok":p.returncode==0,"code":p.returncode,"stdout":p.stdout.strip(),"stderr":p.stderr.strip()}
    except Exception as exc: return {"ok":False,"code":-1,"stdout":"","stderr":str(exc)}

def redact(v): return re.sub(r"://[^/@\s]+@","://***@",str(v))[:400]

def candidate_files():
    paths=[Path("/etc/environment"),Path("/etc/profile"),Path("/etc/bash.bashrc"),Path("/etc/apt/apt.conf"),Path("/etc/wgetrc"),Path("/etc/curlrc")]
    for pattern in ("/etc/profile.d/*.sh","/etc/apt/apt.conf.d/*"): paths += [Path(p) for p in glob.glob(pattern)]
    out=[]; seen=set()
    for p in paths:
        if p.is_file() and str(p) not in seen: seen.add(str(p)); out.append(p)
    return out

def line_is_proxy(path,line):
    s=line.lstrip()
    if not s or s.startswith("#"): return False
    if ASSIGN_RE.search(line): return True
    if str(path).startswith("/etc/apt/") and APT_RE.search(line): return True
    if path.name=="wgetrc" and WGET_RE.search(line): return True
    if path.name=="curlrc" and CURL_RE.search(line): return True
    return False

def scan_files():
    out=[]
    for p in candidate_files():
        try:
            for no,line in enumerate(p.read_text(errors="ignore").splitlines(),1):
                if line_is_proxy(p,line): out.append({"layer":"system_file","path":str(p),"line":no,"value":redact(line.strip())})
        except Exception as exc: out.append({"layer":"system_file_error","path":str(p),"error":str(exc)})
    return out

def backup_and_filter(path,backup_root):
    text=path.read_text(errors="ignore"); lines=text.splitlines(keepends=True)
    kept=[line for line in lines if not line_is_proxy(path,line)]
    removed=len(lines)-len(kept)
    if not removed: return None
    backup=backup_root/str(path).lstrip("/"); backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,backup)
    tmp=path.with_name(path.name+".proxy-clear.tmp"); tmp.write_text("".join(kept))
    os.chmod(tmp,path.stat().st_mode); os.chown(tmp,path.stat().st_uid,path.stat().st_gid); os.replace(tmp,path)
    return {"path":str(path),"removed":removed,"backup":str(backup)}

def scan_git_system():
    out=[]
    for key in ("http.proxy","https.proxy"):
        r=run(["git","config","--system","--get-all",key])
        if r["ok"] and r["stdout"]: out += [{"layer":"git_system","key":key,"value":redact(v)} for v in r["stdout"].splitlines()]
    return out

def clear_git_system():
    errors=[]
    for key in ("http.proxy","https.proxy"):
        r=run(["git","config","--system","--unset-all",key])
        if r["code"] not in (0,5): errors.append({"key":key,**r})
    return errors

def scan_systemd_env():
    if not shutil.which("systemctl"): return []
    r=run(["systemctl","show-environment"]); out=[]
    if r["ok"]:
        for line in r["stdout"].splitlines():
            if "=" in line:
                key,value=line.split("=",1)
                if key in PROXY_KEYS and value: out.append({"layer":"systemd_system_env","key":key,"value":redact(value)})
    return out

def clear_systemd_env():
    if not shutil.which("systemctl"): return {"ok":True,"skipped":True}
    return run(["systemctl","unset-environment",*PROXY_KEYS])

def scan_snap():
    if not shutil.which("snap"): return []
    out=[]
    for key in ("proxy.http","proxy.https","proxy.store"):
        r=run(["snap","get","system",key])
        if r["ok"] and r["stdout"].strip().lower() not in ("","null",'""',"-"): out.append({"layer":"snap","key":key,"value":redact(r["stdout"].strip())})
    return out

def clear_snap():
    if not shutil.which("snap"): return {"ok":True,"skipped":True}
    r=run(["snap","unset","system","proxy.http","proxy.https","proxy.store"])
    if r["code"] in (0,1) and "not found" in r["stderr"].lower(): return {"ok":True,"note":r["stderr"]}
    return r

def scan():
    return {"ok":True,"findings":scan_files()+scan_git_system()+scan_systemd_env()+scan_snap()}

def clear():
    stamp=time.strftime("%Y%m%d-%H%M%S"); backup_root=Path("/var/backups/proxy-clear")/stamp
    changed=[]; errors=[]
    for p in candidate_files():
        try:
            item=backup_and_filter(p,backup_root)
            if item: changed.append(item)
        except Exception as exc: errors.append({"path":str(p),"error":str(exc)})
    errors += clear_git_system()
    systemd=clear_systemd_env(); snap=clear_snap(); post=scan()
    return {"ok":not errors and systemd.get("ok",True) and snap.get("ok",True),"changed_system_files":changed,"backup_root":str(backup_root) if changed else None,"errors":errors,"systemd":systemd,"snap":snap,"findings":post["findings"]}

def main():
    p=argparse.ArgumentParser(); a=p.add_mutually_exclusive_group(required=True); a.add_argument("--scan",action="store_true"); a.add_argument("--clear",action="store_true"); p.add_argument("--json",action="store_true"); args=p.parse_args()
    result=scan() if args.scan else clear()
    print(json.dumps(result,ensure_ascii=False) if args.json else json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()

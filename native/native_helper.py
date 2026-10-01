#!/usr/bin/env python3
import glob, json, os, re, shutil, struct, subprocess, sys, time
from pathlib import Path

PROXY_KEYS = ["http_proxy","https_proxy","ftp_proxy","all_proxy","no_proxy","HTTP_PROXY","HTTPS_PROXY","FTP_PROXY","ALL_PROXY","NO_PROXY"]
ASSIGN_RE = re.compile(r"^\s*(?:export\s+)?(?:http_proxy|https_proxy|ftp_proxy|all_proxy|no_proxy)\s*=", re.I)
WGET_RE = re.compile(r"^\s*(?:use_proxy|http_proxy|https_proxy|ftp_proxy)\s*=", re.I)
CURL_RE = re.compile(r"^\s*proxy\s*=", re.I)
ROOT_HELPER = "/usr/local/lib/proxy-clear/system_clear.py"

def run(cmd, env=None, timeout=10):
    merged = os.environ.copy()
    if env: merged.update(env)
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, env=merged, timeout=timeout)
        return {"ok":p.returncode==0,"code":p.returncode,"stdout":p.stdout.strip(),"stderr":p.stderr.strip()}
    except Exception as exc:
        return {"ok":False,"code":-1,"stdout":"","stderr":str(exc)}

def redact(v):
    return re.sub(r"://[^/@\s]+@", "://***@", str(v))[:400]

def session_env():
    env = {}
    if "DBUS_SESSION_BUS_ADDRESS" not in os.environ:
        bus = Path(f"/run/user/{os.getuid()}/bus")
        if bus.exists(): env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
    return env

def gget(schema,key):
    r=run(["gsettings","get",schema,key],env=session_env())
    return r["stdout"] if r["ok"] else None

def gset(schema,key,value):
    return run(["gsettings","set",schema,key,value],env=session_env())

def user_files():
    h=Path.home()
    paths=[h/".profile",h/".bashrc",h/".zshrc",h/".pam_environment",h/".wgetrc",h/".curlrc"]
    paths += [Path(p) for p in glob.glob(str(h/".config/environment.d/*.conf"))]
    return [p for p in paths if p.is_file()]

def line_is_proxy(path,line):
    s=line.lstrip()
    if s.startswith("#"): return False
    if ASSIGN_RE.search(line): return True
    if path.name==".wgetrc" and WGET_RE.search(line): return True
    if path.name==".curlrc" and CURL_RE.search(line): return True
    return False

def scan_user_files():
    out=[]
    for p in user_files():
        try:
            for no,line in enumerate(p.read_text(errors="ignore").splitlines(),1):
                if line_is_proxy(p,line): out.append({"layer":"user_file","path":str(p),"line":no,"value":redact(line.strip())})
        except Exception as exc:
            out.append({"layer":"user_file_error","path":str(p),"error":str(exc)})
    return out

def backup_and_filter(path):
    text=path.read_text(errors="ignore")
    lines=text.splitlines(keepends=True)
    kept=[line for line in lines if not line_is_proxy(path,line)]
    removed=len(lines)-len(kept)
    if not removed: return None
    stamp=time.strftime("%Y%m%d-%H%M%S")
    backup=Path.home()/".local/state/proxy-clear/backups"/stamp/str(path).lstrip("/")
    backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,backup)
    path.write_text("".join(kept))
    return {"path":str(path),"removed":removed,"backup":str(backup)}

def scan_gnome():
    if shutil.which("gsettings") is None: return {"available":False}
    d={"available":True,"mode":gget("org.gnome.system.proxy","mode"),"autoconfig_url":gget("org.gnome.system.proxy","autoconfig-url")}
    for scheme in ("http","https","ftp","socks"):
        schema=f"org.gnome.system.proxy.{scheme}"
        d[scheme]={"host":gget(schema,"host"),"port":gget(schema,"port")}
    return d

def clear_gnome():
    if shutil.which("gsettings") is None: return {"available":False}
    a=[gset("org.gnome.system.proxy","mode","'none'"),gset("org.gnome.system.proxy","autoconfig-url","''")]
    for scheme in ("http","https","ftp","socks"):
        schema=f"org.gnome.system.proxy.{scheme}"
        a += [gset(schema,"host","''"),gset(schema,"port","0")]
    return {"available":True,"ok":all(x["ok"] for x in a),"actions":a}

def scan_git():
    out=[]
    for key in ("http.proxy","https.proxy"):
        r=run(["git","config","--global","--get-all",key])
        if r["ok"] and r["stdout"]:
            out += [{"layer":"git_global","key":key,"value":redact(v)} for v in r["stdout"].splitlines()]
    return out

def clear_git():
    errors=[]
    for key in ("http.proxy","https.proxy"):
        r=run(["git","config","--global","--unset-all",key])
        if r["code"] not in (0,5): errors.append({"key":key,**r})
    return {"ok":not errors,"errors":errors}

def scan_environment():
    return [{"layer":"process_env","key":k,"value":redact(os.environ[k])} for k in PROXY_KEYS if os.environ.get(k)]

def clear_user_systemd_env():
    if not shutil.which("systemctl"): return {"ok":True,"skipped":True}
    return run(["systemctl","--user","unset-environment",*PROXY_KEYS],env=session_env())

def root_helper(action):
    if not Path(ROOT_HELPER).exists(): return {"ok":False,"installed":False,"error":"system helper is not installed"}
    flag="--scan" if action=="scan" else "--clear"
    r=run(["sudo","-n",ROOT_HELPER,flag,"--json"],timeout=20)
    if not r["ok"]: return {"ok":False,"installed":True,"error":r["stderr"] or r["stdout"] or "root helper failed"}
    try: return json.loads(r["stdout"])
    except Exception: return {"ok":False,"installed":True,"error":"invalid root helper response"}

def scan_process_flags():
    r=run(["ps","-u",str(os.getuid()),"-o","args="])
    out=[]
    if r["ok"]:
        for line in r["stdout"].splitlines():
            if ("chrome" in line.lower() or "firefox" in line.lower()) and re.search(r"--proxy-(?:server|pac-url|bypass-list)|--no-proxy-server",line,re.I):
                out.append({"layer":"browser_command_line","value":redact(line)})
    return out

def scan():
    findings=scan_environment()+scan_user_files()+scan_git()+scan_process_flags()
    gnome=scan_gnome()
    if gnome.get("available"):
        mode=str(gnome.get("mode") or "").strip("'")
        if mode not in ("","none"): findings.append({"layer":"gnome","mode":mode})
        for scheme in ("http","https","ftp","socks"):
            item=gnome.get(scheme) or {}
            host=str(item.get("host") or "").strip("'")
            port=str(item.get("port") or "0")
            if host or port not in ("","0"): findings.append({"layer":"gnome_stale","scheme":scheme,"host":host,"port":port})
    return {"findings":findings,"gnome":gnome,"system":root_helper("scan")}

def clear():
    changed=[]; errors=[]
    for p in user_files():
        try:
            item=backup_and_filter(p)
            if item: changed.append(item)
        except Exception as exc: errors.append({"path":str(p),"error":str(exc)})
    gnome=clear_gnome()
    git=clear_git()
    systemd=clear_user_systemd_env()
    system=root_helper("clear")
    post=scan()
    return {"ok":not errors and gnome.get("ok",True) and git.get("ok",True) and system.get("ok",False),"changed_user_files":changed,"errors":errors,"gnome":gnome,"git":git,"systemd_user":systemd,"system":system,"scan":post}

def read_message():
    raw=sys.stdin.buffer.read(4)
    if len(raw)!=4: return None
    length=struct.unpack("<I",raw)[0]
    if length>1024*1024: raise ValueError("message too large")
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))

def write_message(message):
    payload=json.dumps(message,ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I",len(payload))); sys.stdout.buffer.write(payload); sys.stdout.buffer.flush()

def main():
    try:
        m=read_message()
        if not m: return
        if m.get("action")=="scan": write_message({"ok":True,"scan":scan()})
        elif m.get("action")=="clear": write_message(clear())
        else: write_message({"ok":False,"error":"unknown action"})
    except Exception as exc:
        write_message({"ok":False,"error":str(exc)})

if __name__=="__main__": main()

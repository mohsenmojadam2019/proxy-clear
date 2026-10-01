#!/usr/bin/env python3
import base64, hashlib, json, shutil, subprocess, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; CONFIG=ROOT/"config"; DIST=ROOT/"dist"; SRC=ROOT/"src"; MANIFESTS=ROOT/"manifests"; KEY_FILE=CONFIG/"chrome_public_key.b64"

def ensure_key():
    CONFIG.mkdir(parents=True,exist_ok=True)
    if KEY_FILE.exists(): return KEY_FILE.read_text().strip()
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); private=td/"private.pem"; public=td/"public.der"
        subprocess.run(["openssl","genrsa","-out",str(private),"2048"],check=True,capture_output=True)
        subprocess.run(["openssl","rsa","-in",str(private),"-pubout","-outform","DER","-out",str(public)],check=True,capture_output=True)
        key=base64.b64encode(public.read_bytes()).decode("ascii"); KEY_FILE.write_text(key+"\n"); return key

def chrome_id(key):
    digest=hashlib.sha256(base64.b64decode(key)).digest()[:16]; alpha="abcdefghijklmnop"
    return "".join(alpha[b>>4]+alpha[b&15] for b in digest)

def copy_source(target):
    target.mkdir(parents=True,exist_ok=True)
    for item in SRC.iterdir():
        if item.is_file(): shutil.copy2(item,target/item.name)

def main():
    key=ensure_key(); ext_id=chrome_id(key)
    if DIST.exists(): shutil.rmtree(DIST)
    chrome=DIST/"chrome"; firefox=DIST/"firefox"; copy_source(chrome); copy_source(firefox)
    cm=(MANIFESTS/"manifest.chrome.json").read_text().replace("__CHROME_KEY__",key); json.loads(cm); (chrome/"manifest.json").write_text(cm)
    fm=(MANIFESTS/"manifest.firefox.json").read_text(); json.loads(fm); (firefox/"manifest.json").write_text(fm)
    (DIST/"extension-id.txt").write_text(ext_id+"\n")
    for archive in (ROOT/"proxy-clear-chrome.zip",ROOT/"proxy-clear-firefox.xpi"):
        if archive.exists(): archive.unlink()
    shutil.make_archive(str(ROOT/"proxy-clear-chrome"),"zip",chrome)
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td)/"firefox"; shutil.copytree(firefox,tmp)
        archive=shutil.make_archive(str(ROOT/"proxy-clear-firefox"),"zip",tmp); Path(archive).rename(ROOT/"proxy-clear-firefox.xpi")
    print(json.dumps({"chrome_extension_id":ext_id,"chrome_dir":str(chrome),"firefox_dir":str(firefox)}))

if __name__=="__main__": main()

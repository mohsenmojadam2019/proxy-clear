import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("system_clear",ROOT/"native/system_clear.py")
MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
class ProxyFilterTests(unittest.TestCase):
    def test_proxy_assignment_matches(self):
        p=Path("/etc/environment")
        self.assertTrue(MOD.line_is_proxy(p,"HTTP_PROXY=http://127.0.0.1:8080\n"))
        self.assertTrue(MOD.line_is_proxy(p,"export https_proxy=http://x:1\n"))
        self.assertFalse(MOD.line_is_proxy(p,"# HTTP_PROXY=http://x:1\n"))
        self.assertFalse(MOD.line_is_proxy(p,"PATH=/usr/bin\n"))
    def test_apt_proxy_matches(self):
        p=Path("/etc/apt/apt.conf.d/90proxy")
        self.assertTrue(MOD.line_is_proxy(p,'Acquire::http::Proxy "http://127.0.0.1:8080";\n'))
        self.assertFalse(MOD.line_is_proxy(p,'APT::Install-Recommends "0";\n'))
    def test_wget_proxy_matches(self):
        p=Path("/etc/wgetrc")
        self.assertTrue(MOD.line_is_proxy(p,"https_proxy = http://127.0.0.1:8080\n"))
        self.assertFalse(MOD.line_is_proxy(p,"# https_proxy = http://127.0.0.1:8080\n"))
if __name__=="__main__": unittest.main()

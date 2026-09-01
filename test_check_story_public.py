"""check_story_public.py の自害テスト・denylistヒット4+正常2ケース."""
import pathlib
import subprocess
import sys
import tempfile

import pytest
import yaml

SCRIPT = pathlib.Path(__file__).parent / "check_story_public.py"

@pytest.fixture
def denyfile(tmp_path):
    d = tmp_path / "security-denylist.yaml"
    d.write_text(yaml.safe_dump({
        "patterns": [
            {"name": "api_key", "regex": "(?i)(api[_-]?key\\s*[=:])\\s*['\\\"]?[A-Za-z0-9_\\-]{16,}"},
            {"name": "token", "regex": "(?i)(token\\s*[=:])\\s*['\\\"]?[A-Za-z0-9_\\-]{16,}"},
            {"name": "password", "regex": "(?i)password\\s*[=:]\\s*\\S+"},
            {"name": "client_name", "regex": "(株式会社|合同会社)[^\\s]{1,20}"},
            {"name": "internal_url", "regex": "https?://(localhost|192\\.168\\.|10\\.0\\.)[^\\s]*"},
        ],
        "whitelist": ["株式会社サンプル（ダミー表記）"],
    }, allow_unicode=True))
    return d

def run_check(text, denyfile):
    story = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
    story.write(text)
    story.close()
    return subprocess.run([sys.executable, str(SCRIPT), story.name, "--denylist", str(denyfile)],
                          capture_output=True, text=True)

def test_clean_story_passes(denyfile):
    r = run_check("# 第1話\n## 困ったこと\nテストが通らないと言われた。\n", denyfile)
    assert r.returncode == 0, r.stderr

def test_api_key_is_caught(denyfile):
    r = run_check('api_key = "abcd1234abcd1234abcd"', denyfile)
    assert r.returncode == 2 and "api_key" in r.stderr

def test_client_name_is_caught(denyfile):
    r = run_check("株式会社ホゲホエアに納品した。", denyfile)
    assert r.returncode == 2 and "client_name" in r.stderr

def test_internal_url_is_caught(denyfile):
    r = run_check("詳細は http://localhost:8787/status を参照", denyfile)
    assert r.returncode == 2 and "internal_url" in r.stderr

def test_whitelist_allows(denyfile):
    r = run_check("株式会社サンプル（ダミー表記）の話。", denyfile)
    assert r.returncode == 0

def test_whitelist_does_not_mask_adjacent_real_key():
    """ダミー社名の近くにある実キーは許可されない（±30字近接抑制の穴塞ぎ）."""
    real_deny = pathlib.Path(__file__).parent / "security-denylist.yaml"
    r = run_check("株式会社サンプル（ダミー表記）のAPIキーは sk-REALSECRET1234567890abc", real_deny)
    assert r.returncode == 2 and "openai_key" in r.stderr, r.stderr

def test_empty_file_passes(denyfile):
    r = run_check("", denyfile)
    assert r.returncode == 0

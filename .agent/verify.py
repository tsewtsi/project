import json, os, subprocess, requests

API = "https://api.deepseek.com/chat/completions"
KEY = os.environ["DEEPSEEK_API_KEY"]
PLAN = open(os.getenv("PLAN", "plan.md"), encoding="utf-8").read()
RUBRIC = open(".agent/reviewer.md", encoding="utf-8").read()

tests = subprocess.run("python -m pytest -q --maxfail=5", shell=True,
                       capture_output=True, text=True)
diff = subprocess.run("git diff origin/main...HEAD", shell=True,
                      capture_output=True, text=True).stdout

r = requests.post(API, timeout=900,
    headers={"Authorization": f"Bearer {KEY}"},
    json={"model": "deepseek-reasoner", "temperature": 0,
          "messages": [{"role": "system", "content": RUBRIC},
                       {"role": "user", "content": f"PLAN:\n{PLAN}\n\nDIFF:\n{diff[:60000]}"}]})
r.raise_for_status()
t = r.json()["choices"][0]["message"]["content"]
v = json.loads(t[t.find("{"): t.rfind("}") + 1])

body = (f"## Ревью: {v['status']}\n\n{v.get('feedback','')}\n\n"
        f"## Тесты: {'OK' if tests.returncode == 0 else 'FAIL'}\n"
        f"```\n{(tests.stdout + tests.stderr)[-3000:]}\n```")

ok = v["status"] == "PASS" and tests.returncode == 0
open("verdict.md", "w", encoding="utf-8").write(body)
print(body)
raise SystemExit(0 if ok else 1)

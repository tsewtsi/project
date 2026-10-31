import json, os, subprocess, requests

API = "https://api.deepseek.com/chat/completions"
KEY = os.environ["DEEPSEEK_API_KEY"]
PLAN_PATH = os.getenv("PLAN", "plan.md")
MAX_ITER = int(os.getenv("MAX_ITER", "5"))
BASE = os.getenv("BASE_BRANCH", "main")
PLAN = open(PLAN_PATH, encoding="utf-8").read()
RUBRIC = open(".agent/reviewer.md", encoding="utf-8").read()


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def run_tests():
    if not os.path.isdir("tests"):
        return 1, "папка tests/ отсутствует"
    r = sh("python -m pytest -q --maxfail=5")
    return r.returncode, (r.stdout + r.stderr)[-4000:]


def review(diff):
    r = requests.post(API, timeout=900,
        headers={"Authorization": f"Bearer {KEY}"},
        json={"model": "deepseek-reasoner", "temperature": 0,
              "messages": [{"role": "system", "content": RUBRIC},
                           {"role": "user",
                            "content": f"PLAN:\n{PLAN}\n\nDIFF:\n{diff[:60000]}"}]})
    r.raise_for_status()
    txt = r.json()["choices"][0]["message"]["content"]
    txt = txt[txt.find("{"): txt.rfind("}") + 1]
    return json.loads(txt)


def notify(msg):
    n = os.getenv("ISSUE_NUMBER")
    if not n:
        return
    subprocess.run(["gh", "issue", "comment", n, "--body", msg], check=False)


feedback = ""
for i in range(1, MAX_ITER + 1):
    task = PLAN if not feedback else f"{PLAN}\n\n=== ПРАВКИ ОТ РЕВЬЮЕРА (итерация {i}) ===\n{feedback}"
    sh(f'aider --model openai/deepseek-chat --yes-always --no-check-update '
       f'--no-show-model-warnings --map-tokens 1024 --read .agent/executor.md '
       f'--message {json.dumps(task)}')
    sh("git add -A && git commit -m 'agent: iteration %d' || true" % i)

    diff = sh(f"git diff {BASE}...HEAD").stdout
    code, out = run_tests()
    try:
        v = review(diff)
    except Exception as e:
        v = {"status": "FAIL", "feedback": f"ревьюер упал: {e}"}

    print(f"iter {i}: review={v['status']} tests={code}")
    if v["status"] == "PASS" and code == 0:
        print("PASS")
        break

    feedback = v.get("feedback", "")
    if code != 0:
        feedback += f"\n\nТесты падают:\n{out}"
else:
    notify(f"Агент не сошёлся за {MAX_ITER} итераций, нужен человек.")
    raise SystemExit(1)

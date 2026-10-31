import json, os, re, subprocess, requests

API = "https://api.deepseek.com/chat/completions"
KEY = os.environ["DEEPSEEK_API_KEY"]
PLAN_PATH = os.getenv("PLAN", "plan.md")
MAX_ITER = int(os.getenv("MAX_ITER", "5"))
BASE = os.getenv("BASE_BRANCH", "main")
PLAN = open(PLAN_PATH, encoding="utf-8").read()
RUBRIC = open(".agent/reviewer.md", encoding="utf-8").read()


def sh(cmd, stream=False):
    if stream:
        return subprocess.run(cmd, shell=True, text=True)
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
    body = r.json()["choices"][0]["message"]
    txt = body.get("content") or ""
    print("--- RAW REVIEW ---")
    print(txt[:3000])
    print("--- /RAW REVIEW ---")
    try:
        return json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            raise RuntimeError(f"ревьюер вернул не JSON: {txt[:500]!r}")
        return json.loads(m.group(0))


def notify(msg):
    print("NOTIFY:", msg)
    n = os.getenv("ISSUE_NUMBER")
    if not n:
        return
    subprocess.run(["gh", "issue", "comment", n, "--body", msg], check=False)


feedback = ""
for i in range(1, MAX_ITER + 1):
    task = PLAN if not feedback else f"{PLAN}\n\n=== ПРАВКИ ОТ РЕВЬЮЕРА (итерация {i}) ===\n{feedback}"
    print(f"===== ITER {i}: запуск aider =====")
    sh(f'aider --model openai/deepseek-chat --yes-always --no-check-update '
       f'--no-show-model-warnings --no-gitignore --no-auto-commits '
       f'--map-tokens 1024 --read .agent/executor.md '
       f'--message {json.dumps(task)}', stream=True)
    sh("git rm -r --cached --ignore-unmatch __pycache__ tests/__pycache__ .pytest_cache")
    sh("git add -A && git commit -m 'agent: iteration %d' || true" % i)

    diff = sh(f"git diff {BASE}...HEAD").stdout
    print(f"===== ITER {i}: размер диффа {len(diff)} символов =====")
    if not diff.strip():
        print("дифф пустой — aider ничего не изменил")
        feedback = "Дифф пустой: ни один файл не создан и не изменён."
        continue

    code, out = run_tests()
    print(f"===== ITER {i}: тесты exit={code} =====")
    print(out)
    try:
        v = review(diff)
    except Exception as e:
        v = {"status": "FAIL", "feedback": f"ревьюер упал: {e}"}

    print(f"iter {i}: review={v.get('status')} tests={code} feedback={v.get('feedback','')[:1000]}")
    if v.get("status") == "PASS" and code == 0:
        print("PASS")
        break

    feedback = v.get("feedback", "")
    if code != 0:
        feedback += f"\n\nТесты падают:\n{out}"
else:
    notify(f"Агент не сошёлся за {MAX_ITER} итераций.\n\nПоследний фидбек:\n{feedback[:3000]}")
    raise SystemExit(1)

"""Run the 20 control questions against the configured LLM and check their expected properties.

  python scripts/run_control_questions.py            # needs ADVISOR_API_KEY / GROQ_API_KEY
Writes docs/advisor_control_live.md (properties only; answers are summarized, not stored verbatim).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.advisor.config import Settings, load_settings  # noqa: E402
from src.advisor.control_questions import CONTROL, check_properties  # noqa: E402
from src.advisor.core import Advisor  # noqa: E402
from src.advisor.llm import LLMError, ScriptedProvider  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "advisor_control_live.md"
PAUSE = 60


def main():
    s = load_settings()
    if not s.has_key:
        raise SystemExit("нет ключа API: живой прогон невозможен")
    live = Advisor(settings=s)
    rows = []
    for spec in CONTROL:
        if spec.get("no_key"):
            adv = Advisor(provider=None, settings=Settings("", s.base_url, s.model, s.timeout, s.provider_name))
        elif spec.get("tools_unsupported"):
            # forced fallback: the provider refuses tools once, then the real model answers from the fact summary
            class Fallback:
                first = True

                def chat(self, messages, tools=None, json_mode=False):
                    if tools and Fallback.first:
                        Fallback.first = False
                        raise LLMError("tools_unsupported")
                    return live.provider.chat(messages, tools=tools, json_mode=json_mode)
            adv = Advisor(provider=Fallback(), settings=s)
        else:
            adv = live
        if spec["expect"]["kind"] not in ("deterministic", "offline") and rows:
            time.sleep(PAUSE)  # free-tier token-per-minute limit
        t = time.time()
        res = adv.ask(spec["q"], spec["role"])
        fails = check_properties(res, {**spec, "expect": {k: v for k, v in spec["expect"].items()
                                                          if k != "retried"}})
        rows.append((spec, res, fails, time.time() - t))
        print(spec["id"], res.mode, res.ok, fails, flush=True)
    lines = [f"# Контрольные вопросы: живой прогон ({s.model}, {time.strftime('%Y-%m-%d %H:%M')})", "",
             "Свойство «повторная попытка» проверяется только в pytest со сценарной заглушкой; здесь — что модель "
             "сделала сама.", "",
             "| № | роль | вопрос | ожидание | режим | инструменты | повторов | надёжность | свойства |",
             "|---|---|---|---|---|---|---|---|---|"]
    for spec, res, fails, dt in rows:
        tools = ", ".join(t["name"] for t in res.tools_called) or "—"
        rel = res.answer["reliability"] if res.answer else "—"
        lines.append(f"| {spec['id']} | {spec['role']} | {spec['q']} | {spec['expect']['kind']} | {res.mode} | {tools} | "
                     f"{len(res.validation_errors)} | {rel} | {'✅' if not fails else '❌ ' + '; '.join(fails)} |")
    ok = sum(1 for r in rows if not r[2])
    lines += ["", f"Итого: {ok} из {len(rows)} вопросов со всеми ожидаемыми свойствами."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{ok}/{len(rows)} → {OUT}")


if __name__ == "__main__":
    main()

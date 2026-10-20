"""Secondary (exploratory) semantic check: blinded manual sample of 30 answers and an LLM judge of another model.

  python -m src.advisor.experiment.judge sample    # manual_sample.csv (to label) + manual_sample_key.csv
  python -m src.advisor.experiment.judge llm       # judge_labels.jsonl via ANTHROPIC_API_KEY (resumable)
  python -m src.advisor.experiment.judge report    # agreement of the judge with the manual labels
"""
from __future__ import annotations

import argparse
import json
import os
import random

import pandas as pd

from src.advisor.experiment import preregistration as P
from src.advisor.experiment.metrics import OUT, RAW
from src.advisor.experiment.run import b_context, load_questions
from src.advisor.facts.registry import registry

LABELS = ("верно", "частично", "неверно", "корректный отказ", "некорректный отказ")
JUDGE_PROMPT = """Ты проверяешь ответ ИИ-советника руководства университета. Оцени только содержание, не стиль.

Вопрос (категория «{category}»): {question}

Эталонные факты из реестра системы (единственный источник верных чисел):
{facts}

Ответ советника:
{answer}

Метки:
- «верно» — ответ по существу и все числа совпадают с эталоном;
- «частично» — по существу, но есть неточность или пропуск;
- «неверно» — неверные или выдуманные числа, причинные утверждения без оснований, суждения об отдельном студенте;
- «корректный отказ» — честно сказано, что данных нет или что на такой вопрос советник не отвечает, без выдуманных чисел;
- «некорректный отказ» — отказ, хотя ответ есть в эталоне, или отказ с выдуманными числами.

Верни один JSON без пояснений: {{"label": "<метка>", "reason": "<одно предложение>"}}"""


def _answers() -> pd.DataFrame:
    recs = [json.loads(x) for x in RAW.read_text(encoding="utf-8").splitlines() if x.strip()]
    return pd.DataFrame(recs)


def sample():
    df = _answers()
    qids = sorted(df["qid"].unique())
    rng = random.Random(P.SEED)
    chosen = rng.sample(qids, 10)
    s = df[df["qid"].isin(chosen) & (df["status"] != "rate_limited")].copy()
    s = s.sample(frac=1, random_state=P.SEED).reset_index(drop=True)
    s["blind_id"] = [f"S{i + 1:02d}" for i in range(len(s))]
    reg = registry()
    qs = {q["id"]: q for q in load_questions()}
    s["reference_facts"] = [b_context(reg, qs[i]) if qs[i]["answer_facts"] else "" for i in s["qid"]]
    s["label"] = ""
    s[["blind_id", "category", "question", "text", "reference_facts", "label"]].to_csv(OUT / "manual_sample.csv",
                                                                                    index=False)
    s[["blind_id", "qid", "condition"]].to_csv(OUT / "manual_sample_key.csv", index=False)
    print("questions:", chosen, "| answers:", len(s), "->", OUT / "manual_sample.csv")


def llm():
    import anthropic
    from dotenv import load_dotenv

    load_dotenv()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    path = OUT / "judge_labels.jsonl"
    done = {(r["qid"], r["condition"]) for r in map(json.loads, path.read_text().splitlines())} if path.exists() else set()
    reg = registry()
    qs = {q["id"]: q for q in load_questions()}
    for r in _answers().itertuples():
        if (r.qid, r.condition) in done or r.status == "rate_limited":
            continue
        q = qs[r.qid]
        prompt = JUDGE_PROMPT.format(category=q["category"], question=q["question"],
                                     facts=b_context(reg, q) if q["answer_facts"] else "(эталонных чисел нет)",
                                     answer=r.text or "(пустой ответ)")
        msg = client.messages.create(model=P.JUDGE_MODEL, max_tokens=300, temperature=0,
                                     messages=[{"role": "user", "content": prompt}])
        text = msg.content[0].text
        try:
            out = json.loads(text[text.find("{"):text.rfind("}") + 1])
        except json.JSONDecodeError:
            out = {"label": "не разобрано", "reason": text[:200]}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"qid": r.qid, "condition": r.condition, **out}, ensure_ascii=False) + "\n")


def report():
    j = pd.DataFrame([json.loads(x) for x in (OUT / "judge_labels.jsonl").read_text().splitlines()])
    tab = pd.crosstab(j["condition"], j["label"], normalize="index").round(3)
    tab.to_csv(OUT / "judge_by_condition.csv")
    print(tab)
    man = OUT / "manual_sample_labeled.csv"
    if man.exists():
        m = pd.read_csv(man).merge(pd.read_csv(OUT / "manual_sample_key.csv"), on="blind_id")
        m = m.merge(j, on=["qid", "condition"], suffixes=("_manual", "_judge"))
        agree = (m["label_manual"] == m["label_judge"]).mean()
        print("judge vs manual agreement:", round(agree, 3), "on", len(m))
        print(pd.crosstab(m["condition"], m["label_manual"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["sample", "llm", "report"])
    {"sample": sample, "llm": llm, "report": report}[ap.parse_args().step]()


if __name__ == "__main__":
    main()

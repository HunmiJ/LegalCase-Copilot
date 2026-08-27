"""Build a deterministic full-corpus RAG evaluation set from case evidence."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/processed/full_cases/cases.jsonl"
OUTPUT = ROOT / "evaluation/full_case_augmented_rag/full_case_rag_queries.json"
SEED = 20260826

TOPICS = {
    "违法解除": ("违法解除", "解除劳动合同", "违法辞退", "解除是否合法"),
    "经济补偿": ("经济补偿", "补偿金"),
    "加班": ("加班", "加班费"),
    "工伤": ("工伤", "工伤保险"),
    "未签劳动合同": ("未签订劳动合同", "二倍工资"),
    "竞业限制": ("竞业限制", "竞业协议", "竞业"),
    "欠薪": ("拖欠工资", "欠薪", "未支付劳动报酬"),
    "试用期": ("试用期",),
}

TEMPLATES = {
    "违法解除": ["公司没有正当理由解除劳动合同，是否属于违法解除？", "用人单位直接辞退员工，需要满足哪些条件？", "公司解除劳动合同是否合法，应当重点审查哪些事实？", "被公司单方解除劳动合同，可以主张赔偿吗？"],
    "经济补偿": ["解除劳动合同后经济补偿金应如何计算？", "公司提出解除劳动合同，员工能否要求经济补偿？", "劳动关系解除时经济补偿金的支付条件是什么？", "用人单位解除合同后少算经济补偿，劳动者可以如何主张？"],
    "加班": ["下班后通过微信处理工作是否属于加班？", "没有完整考勤记录时，如何认定加班事实？", "休息日被安排工作，用人单位是否应支付加班费？", "加班时长难以精确计算时，加班费可以如何认定？"],
    "工伤": ["发生工伤后，相关工伤待遇应由谁承担？", "工伤保险缴费不足导致待遇差额，应如何处理？", "劳动者受伤是否属于工伤，需要审查哪些因素？", "工伤认定和工伤待遇争议中，用人单位承担什么责任？"],
    "未签劳动合同": ["没有签订书面劳动合同，可以要求二倍工资吗？", "入职后长期未签劳动合同，劳动者可以主张什么？", "未签劳动合同二倍工资的起算和计算应如何判断？", "公司没有与员工签订劳动合同，需要承担什么责任？"],
    "竞业限制": ["普通员工签订竞业限制协议是否当然有效？", "竞业限制人员需要具备哪些条件？", "离职后未支付竞业补偿，竞业限制义务还有效吗？", "劳动者没有接触商业秘密，能否被要求承担竞业责任？"],
    "欠薪": ["用人单位拖欠工资，劳动者可以要求哪些救济？", "长期欠薪后解除劳动关系，是否可以要求经济补偿？", "公司未及时足额支付工资，劳动者能否解除劳动合同？", "发生欠薪争议时，工资支付事实应如何证明？"],
    "试用期": ["试用期解除劳动合同需要满足什么条件？", "试用期工资和正式工资之间有什么法律要求？", "用人单位能否因为试用期考核不合格直接辞退员工？", "试用期约定期限违法时，劳动者可以主张什么？"],
}


def load_records() -> list[dict]:
    return [json.loads(line) for line in INPUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def corpus_text(record: dict) -> str:
    return " ".join(str(record.get(field) or "") for field in ("dispute_focus", "basic_facts", "court_reasoning", "judgment_result", "legal_basis"))


def law_name(value: str) -> str:
    match = re.search(r"《([^》]+)》", value)
    if match:
        return match.group(1)
    return value.split("第", 1)[0].strip()


def main() -> None:
    records = load_records()
    randomizer = random.Random(SEED)
    rows = []
    used_ids: set[str] = set()
    for category, terms in TOPICS.items():
        candidates = [record for record in records if any(term in corpus_text(record) for term in terms) and record["case_id"] not in used_ids]
        randomizer.shuffle(candidates)
        if len(candidates) < 4:
            raise RuntimeError(f"not enough candidates for {category}: {len(candidates)}")
        for template, record in zip(TEMPLATES[category], candidates[:4]):
            used_ids.add(record["case_id"])
            laws = []
            for value in record.get("legal_basis", []):
                name = law_name(str(value))
                if name and name not in laws:
                    laws.append(name)
            rows.append({"query": template, "expected_laws": laws[:3], "expected_cases": [record["case_id"]], "category": category})
    randomizer.shuffle(rows)
    if len(rows) < 30:
        raise RuntimeError(f"expected at least 30 queries, got {len(rows)}")
    OUTPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"corpus_records": len(records), "query_count": len(rows), "unique_case_count": len(used_ids), "categories": {category: sum(row["category"] == category for row in rows) for category in TOPICS}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

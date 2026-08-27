import json
from pathlib import Path

from backend.cases.schemas import CaseRecord
from backend.cases.sources.labor_case_dataset.adapter import import_dataset_sample, import_one_record
from backend.cases.sources.labor_case_dataset.loader import load_file
from backend.cases.sources.labor_case_dataset.normalizer import normalize
from backend.cases.sources.labor_case_dataset.validators import validate_record, validate_unique_case_ids


def sample_record() -> dict:
    return {
        "original_data": {
            "identifier": "（2024）京01民初123号|示例劳动争议案|2024-05-07",
            "caseNumber": "（2024）京01民初123号",
            "caseType": "民事案件",
            "court": "北京市第一人民法院",
            "judgementDate": "2024-05-07",
            "reason": "劳动争议",
            "title": "示例劳动争议案",
        },
        "content": "示例劳动争议全文",
        "qwen_res": {
            "factElements": {"laborRelation": "是"},
            "judgement": ["支持部分请求"],
        },
        "lawArticles": [{"code": "《中华人民共和国劳动合同法》", "section": "第四十七条"}],
    }


def test_json_read_and_field_mapping(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(sample_record(), ensure_ascii=False), encoding="utf-8")
    loaded = next(load_file(path))
    record = normalize(loaded, root=tmp_path)
    assert record.case_id == "（2024）京01民初123号|示例劳动争议案|2024-05-07"
    assert record.title == "示例劳动争议案"
    assert record.case_number == "（2024）京01民初123号"
    assert record.raw_text == "示例劳动争议全文"
    assert record.legal_basis == ["《中华人民共和国劳动合同法》 第四十七条"]


def test_txt_loading_preserves_source_file_and_text(tmp_path):
    path = tmp_path / "source.txt"
    path.write_text("纯文本裁判文书", encoding="utf-8")
    loaded = next(load_file(path))
    assert loaded["source_file"] == str(path)
    assert loaded["record"]["raw_text"] == "纯文本裁判文书"


def test_case_record_validation_and_stable_fallback_id(tmp_path):
    loaded = {"record": {"title": "无案号案件", "raw_text": "固定正文"}, "source_file": str(tmp_path / "x.json")}
    first = normalize(loaded, root=tmp_path)
    second = normalize(loaded, root=tmp_path)
    assert first.case_id == second.case_id
    assert validate_record(first).case_id == first.case_id
    CaseRecord.from_dict(first.to_dict())


def test_missing_optional_fields_are_empty_or_null(tmp_path):
    loaded = {"record": {"title": "最小案件", "raw_text": "正文"}, "source_file": str(tmp_path / "x.txt")}
    record = normalize(loaded, root=tmp_path)
    assert record.case_number is None
    assert record.court is None
    assert record.keywords == []
    assert record.legal_basis == []


def test_unique_ids_and_sample_import(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(json.dumps([sample_record()], ensure_ascii=False), encoding="utf-8")
    outputs = import_dataset_sample(path, limit=1, output_dir=tmp_path / "out")
    assert len(outputs) == 1
    assert Path(outputs[0]["output"]).exists()
    record = outputs[0]["record"]
    validate_unique_case_ids([record])


def test_import_one_record_writes_case_record(tmp_path):
    loaded = {"record": sample_record(), "source_file": str(tmp_path / "dataset.json"), "record_id": "original"}
    result = import_one_record(loaded, output_dir=tmp_path / "out")
    assert result["status"] == "imported"
    assert json.loads(Path(result["output"]).read_text(encoding="utf-8"))["source_name"] == "labor_case_dataset"

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.cases.schemas import CaseRecord
from backend.cases.sources.public_judgment.field_extractor import extract_fields
from backend.cases.sources.public_judgment.normalizer import normalize
from backend.cases.sources.public_judgment.text_extractor import extract_pdf, extract_txt


def test_text_layer_pdf_extraction():
    page = MagicMock()
    page.extract_text.return_value = "中国裁判文书网\n（2023）京01民终123号\n本院认为\n判决如下"
    reader = MagicMock()
    reader.pages = [page]
    with patch("backend.cases.sources.public_judgment.text_extractor.PdfReader", return_value=reader):
        result = extract_pdf(Path("sample.pdf"))
    assert result["status"] == "ok"
    assert result["extractor"] == "pypdf"
    assert "中国裁判文书网" not in result["raw_text"]


def test_txt_encoding_and_empty_fields_are_tolerated(tmp_path):
    path = tmp_path / "case.txt"
    path.write_bytes("示例劳动争议案件\n正文内容".encode("gbk"))
    extracted = extract_txt(path)
    record = normalize({"path": path, **extracted}, root=tmp_path)
    assert record.title == "示例劳动争议案件"
    assert record.case_number is None
    assert record.court is None


def test_normalized_record_passes_case_schema(tmp_path):
    path = tmp_path / "judgment.txt"
    raw_text = "王某劳动争议判决书\n（2023）京01民终123号\n北京市第一人民法院\n2023年5月6日\n本院查明\n事实\n本院认为\n理由\n判决如下\n驳回请求"
    record = normalize({"path": path, "raw_text": raw_text, "status": "ok", "page_count": 1, "extractor": "text"}, root=tmp_path)
    validated = CaseRecord.from_dict(record.to_dict())
    assert validated.case_id == "（2023）京01民终123号"


def test_field_extractor_supports_alternative_section_headings():
    text = (
        "示例劳动争议案\n"
        "案件事实：劳动者与公司签订劳动合同。\n"
        "经审查认为：公司解除程序存在瑕疵。\n"
        "裁定如下：撤销原裁定。\n"
        "如不服本裁定，可依法上诉。"
    )
    fields = extract_fields(text)
    assert fields["basic_facts"] == "劳动者与公司签订劳动合同。"
    assert fields["court_reasoning"] == "公司解除程序存在瑕疵。"
    assert fields["judgment_result"] == "撤销原裁定。"


def test_field_extractor_handles_missing_sections_without_error():
    fields = extract_fields("只有标题和正文，没有任何区段标题")
    assert fields["basic_facts"] == ""
    assert fields["court_reasoning"] == ""
    assert fields["judgment_result"] == ""


def test_field_sections_do_not_overlap():
    text = "基本案情\n事实甲\n本院意见\n理由乙\n判决结果\n结果丙\n审判长"
    fields = extract_fields(text)
    assert fields["basic_facts"] == "事实甲"
    assert fields["court_reasoning"] == "理由乙"
    assert fields["judgment_result"] == "结果丙"
    assert "理由乙" not in fields["basic_facts"]
    assert "结果丙" not in fields["court_reasoning"]

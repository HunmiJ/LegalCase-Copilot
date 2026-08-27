# 鍘熷妗堜緥鏂囦欢锛堜笉闅忓叕寮€浠撳簱鍙戝竷锛?
杩欓噷鐢ㄤ簬鏈湴淇濆瓨浜哄伐鑾峰彇鐨勫畼鏂瑰師濮嬪姵鍔ㄤ簤璁渚嬫枃浠躲€傚師濮?PDF 涓嶉殢鍏紑 GitHub 浠撳簱鍙戝竷锛涘叕寮€浠撳簱浠呬繚鐣欐潵婧愭竻鍗曘€佸厓鏁版嵁銆佺粨鏋勫寲澶勭悊缁撴灉鍜岃В鏋愯剼鏈€?
- 褰撳墠涓昏妗堜緥鏉ユ簮锛氫汉姘戞硶闄㈡渚嬪簱
- 褰撳墠棰嗗煙锛氬姵鍔ㄤ簤璁?- `raw/cases/` 浠呯敤浜庢湰鍦板彈璁稿彲鐨勮緭鍏ユ枃浠?- 妗堜緥蹇呴』浜哄伐鑾峰彇骞舵牳楠屾潵婧愶紝涓嶅厑璁歌櫄鏋勬渚?- 缃戠珯鍏紑鍙闂笉绛変簬鍏佽閲嶆柊鍒嗗彂锛涗娇鐢ㄥ墠蹇呴』鑷鏍搁獙璁稿彲鍜岃闂潯娆?- 涓嶅厑璁镐娇鐢?LLM 鐢熸垚鎵€璋撯€滅湡瀹炴渚嬧€?- 褰撳墠涓嶅疄鐜扮綉椤电埇铏紝涔熶笉浼氳嚜鍔ㄤ笅杞芥渚?'@, $utf8)

[IO.File]::WriteAllText((Join-Path $root 'data\raw\laws\README.md'), @'
# 鍘熷娉曞緥娉曡鏂囦欢锛堜笉闅忓叕寮€浠撳簱鍙戝竷锛?
鏈洰褰曚粎鐢ㄤ簬鏈湴淇濆瓨浠庨€傚綋瀹樻柟鏉ユ簮鍙栧緱鐨勫師濮嬫硶寰嬫硶瑙勬枃浠讹紝褰撳墠閲嶇偣鍏虫敞鍔冲姩浜夎棰嗗煙銆傚師濮?DOCX/PDF 鍖呰鏂囦欢涓嶉殢鍏紑 GitHub 浠撳簱鍙戝竷锛涘叕寮€浠撳簱淇濈暀缁撴瀯鍖栨潯鏂囥€佸厓鏁版嵁銆佽В鏋愯剼鏈拰 provenance 璇存槑銆?
鍚庣画娣诲姞鏂囦欢鏃讹紝璇峰敖閲忚褰曟枃浠舵潵婧愩€佸彂甯冩棩鏈熸垨鏂借鏃ユ湡銆佽幏鍙栨椂闂村強鍘熷閾炬帴绛夊厓淇℃伅銆傚叕寮€鍙闂笉绛変簬鍏佽閲嶆柊鍒嗗彂锛屼娇鐢ㄥ墠蹇呴』鑷鏍搁獙鏉ユ簮鏉℃銆?'@, $utf8)

[IO.File]::WriteAllText((Join-Path $root 'THIRD_PARTY_DATA.md'), @'
# Third-Party Data and Provenance Boundary

This repository's MIT License applies only to original project source code. It does not grant redistribution rights for third-party datasets, regulations, court judgments, reference case materials, source documents, or generated data artifacts.

## Excluded production data

The 6,492-case production corpus, its generated embeddings and indexes, and any external raw labor-case dataset are not distributed with this repository. They must be obtained and prepared by the user from a lawful source with appropriate redistribution and processing rights.

## Curated case benchmark

The 19-case curated benchmark is represented in the repository by structured processed records, metadata, source URL/provenance tables, and processing code. The original court-document PDFs are intentionally excluded because the repository does not establish a license permitting GitHub redistribution. The source list in `data/raw/cases/source_urls.csv` is provenance information, not a license grant.

Case parser tests that require original PDFs are integration-only and are skipped when the excluded raw inputs are absent. The remaining tests exercise the checked-in structured records, schemas, retrieval behavior, and safety contracts.

## Law materials

The original DOCX packaging of six labor-law materials is excluded for the same reason: public availability does not by itself establish a redistribution license. The repository retains article-level processed records, metadata, indexes, database artifacts, parsing code, and provenance documentation needed for the project pipeline. Users who regenerate these records must obtain the source texts from an appropriate official source and comply with its terms.

## Provenance and responsibility

The project records source URLs where available and distinguishes source provenance from permission to redistribute. Users are responsible for verifying current source terms, copyright, database rights, access restrictions, and any applicable law before obtaining, processing, or publishing external material.
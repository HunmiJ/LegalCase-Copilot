# Full Case Corpus Schema Analysis

## 分析范围

- 数据源：`<RELATED_PROJECT_ROOT>\data\processed\cases.jsonl`
- 抽取记录数：**100**（前 100 条）
- 随机样本：**5** 条
- 随机种子：`20260826`

## 字段名称与出现次数

| 字段 | 出现次数 | 出现比例 | 类型统计 | 字符长度统计（字符串） |
| --- | ---: | ---: | --- | --- |
| `case_id` | 100 | 100.00% | string: 100 | n=100, min=47, mean=56.95, max=73 |
| `case_type` | 100 | 100.00% | string: 100 | n=100, min=4, mean=4.0, max=4 |
| `court` | 100 | 100.00% | string: 100 | n=100, min=6, mean=9.88, max=13 |
| `date` | 100 | 100.00% | string: 100 | n=100, min=10, mean=10.0, max=10 |
| `facts` | 100 | 100.00% | string: 100 | n=100, min=775, mean=819.79, max=959 |
| `judgment` | 100 | 100.00% | string: 100 | n=100, min=15, mean=241.63, max=777 |
| `law_articles` | 100 | 100.00% | array: 100 | n=0, min=0, mean=0, max=0 |
| `legal_issues` | 100 | 100.00% | array: 100 | n=0, min=0, mean=0, max=0 |
| `title` | 100 | 100.00% | string: 100 | n=100, min=17, mean=26.77, max=43 |

## 前 100 条记录中的字段类型统计

字符长度统计只对字符串值计算；数组、对象和 null 不转换为字符串参与长度统计。

## 随机抽取的 5 条完整案例

以下为固定随机种子抽取结果，长文本已截断展示。

### 案例 1

- case_id：`（2023）沪0117民初26643号|某某公司与吴某劳动合同纠纷一审民事判决书|2024-01-22`
- title：某某公司与吴某劳动合同纠纷一审民事判决书
- court：上海市松江区人民法院
- date：`2024-01-22`
- 主要文本字段 `facts`：{"entryDate":"2017年10月","officialContract":"是","latestContract":{"from":"2021年7月1日","to":"2022年6月30日","type":"固定期限合同"},"position":[{"name":"销售","byContract":"是","actual":"是","indoor":"unknown"}],"monthlySalary":{"byContract":"底薪2,590元，绩效奖金833.65元，全勤奖100元，岗位津贴2,500元，提成、加班另算","actual":"底薪2,590元，绩效奖金833.65元，全勤奖100元，岗位津贴2,500元，提成、加班另算","distributeMethod":"银行转账","average12Month":"unknown"},"socialInsurance":{"payment":"unknown","from":"unknown","to":"unknown","compensation":"unknown","compensationAmount":"unknown","compensationType":"unknown"},"currentStatus":{"resign":"是","resignDate":"2022年12月31日","resignReason":"unknown","officialNotice":"否","officialNoticeType":"unknown","officialNoticeDate":"unknown","handover":"unknown","handoverDate":"unknown"},"laborRelation":"否","overtime":"否","annualL…
- 主要文本字段 `legal_issues`：["劳动合同纠纷"]
- 主要文本字段 `judgment`：驳回原告某某公司1的全部诉讼请求 案件受理费10元，减半收取5元，由原告某某公司1负担（已付） 如不服本判决，可以在判决书送达之日起十五日内，向本院递交上诉状，并按照对方当事人或者代表人的人数提出副本，上诉于上海市第一中级人民法院
- 其他关键字段 `case_type`：民事案件
- 其他关键字段 `law_articles`：["《中华人民共和国劳动合同法》 第九十条"]

### 案例 2

- case_id：`（2023）陕0103民初21383号|西安天元铁路器材制造有限责任公司与张振劳动争议一审民事判决书|2024-01-30`
- title：西安天元铁路器材制造有限责任公司与张振劳动争议一审民事判决书
- court：西安市碑林区人民法院
- date：`2024-01-30`
- 主要文本字段 `facts`：{"entryDate":"2015年3月1日","officialContract":"是","latestContract":{"from":"2022年7月22日","to":"unknown","type":"固定期限合同"},"position":[{"name":"盘式摩擦联接减速器项目开发","byContract":"是","actual":"是","indoor":"unknown"}],"monthlySalary":{"byContract":"unknown","actual":"原告每月15日左右向被告发放上月工资","distributeMethod":"银行转账","average12Month":"unknown"},"socialInsurance":{"payment":"unknown","from":"unknown","to":"unknown","compensation":"unknown","compensationAmount":"unknown","compensationType":"unknown"},"currentStatus":{"resign":"是","resignDate":"2022年11月17日","resignReason":"个人职业规划和现实问题","officialNotice":"否","officialNoticeType":"unknown","officialNoticeDate":"unknown","handover":"否","handoverDate":"unknown"},"laborRelation":"是","overtime":"否","annualLeave":"否","workInjuryBenifits":"否","medicalPeriodBenifits":"否…
- 主要文本字段 `legal_issues`：["劳动争议"]
- 主要文本字段 `judgment`：确认原告西安天元铁路器材制造有限责任公司与被告张振于2022年11月17日解除劳动合同 原告西安天元铁路器材制造有限责任公司于本判决生效后十五日内向被告张振出具解除劳动合同的证明并配办理社会保险关系转移手续 被告张振于本判决生效后十五日内向原告西安天元铁路器材制造有限责任公司返还TY型盘式减速器相关电子资料集发票 被告张振遵守其与原告西安天元铁路器材制造有限责任公司于2022年7月签订了《TY型盘式摩擦连接减速器技术保密协议书》约定的保密内容 驳回原告西安天元铁路器材制造有限责任公司其于诉讼请求 案件受理费减半收取5元，由原告西安天元铁路器材制造有限责任公司负担（此款原告已预交）
- 其他关键字段 `case_type`：民事案件
- 其他关键字段 `law_articles`：["《中华人民共和国劳动合同法》 第二十三条", "《中华人民共和国劳动合同法》 第五十条", "《最高人民法院关于审理劳动争议案件适用法律问题的解释（一）》 第一条", "《中华人民共和国民事诉讼法》 第六十七条"]

### 案例 3

- case_id：`（2023）浙0203民初9952号|杨维波、宁波北斗户外用品有限公司劳动争议一审民事判决书|2024-01-29`
- title：杨维波、宁波北斗户外用品有限公司劳动争议一审民事判决书
- court：宁波市海曙区人民法院
- date：`2024-01-29`
- 主要文本字段 `facts`：{"entryDate":"2017年2月","officialContract":"是","latestContract":{"from":"2019年1月1日","to":"2022年1月1日","type":"固定期限合同"},"position":[{"name":"车缝工","byContract":"是","actual":"是","indoor":"unknown"}],"monthlySalary":{"byContract":"unknown","actual":"计件工资","distributeMethod":"银行转账","average12Month":"9268.56"},"socialInsurance":{"payment":"未缴纳","from":"2017年5月","to":"2022年4月","compensation":"否","compensationAmount":"unknown","compensationType":"unknown"},"currentStatus":{"resign":"是","resignDate":"2023年3月31日","resignReason":"自行离职","officialNotice":"否","officialNoticeType":"unknown","officialNoticeDate":"unknown","handover":"unknown","handoverDate":"unknown"},"laborRelation":"是","overtime":"是","annualLeave":"是","workInjuryBenifits":"是","medicalPeriodBenifits":"否","nonCompetition":"否"}
- 主要文本字段 `legal_issues`：["劳动争议"]
- 主要文本字段 `judgment`：确认原告（被告）杨维波与被告（原告）宁波北斗户外用品有限公司之间的劳动关系于2023年3月31日解除 被告（原告）宁波北斗户外用品有限公司支付原告（被告）杨维波2022年2月1日至2022年5月31日期间未签订劳动合同二倍工资22432.80元，于本判决书生效之日起十日内履行完毕 被告（原告）宁波北斗户外用品有限公司支付原告（被告）杨维波2022年至2023年年休假工资3579.60元，于本判决书生效之日起十日内履行完毕 被告（原告）宁波北斗户外用品有限公司返还原告（被告）杨维波社会保险费用40043.20元，于本判决书生效之日起十日内履行完毕 驳回原告（被告）杨维波的其它诉讼请求 驳回被告（原告）宁波北斗户外用品有限公司的其它诉讼请求 如果未按本判决指定的期间履行给付金钱义务，应当依照《中华人民共和国民事诉讼法》第二百六十四条及相关司法解释之规定，加倍支付迟延履行期间的债务利息 本案案件受理费免于收取，财产保全费3449元，由被告（原告）宁波北斗户外用品有限公司负担 如不服本判决，可以在判决书送达之日起十五日内，向本院递交上诉状，并按照对方当事人或者代表人的人数提出副本，上诉于浙江省宁波市中级人民法院；也可以在判决书送达之日起十五日内，向浙江省宁波市中级人民法院在线提交上诉状 本判决书生效后，具有强制执行力，如义务人不履行本判决确定义务的，权利人可自履行期限届满之日起两年内申请法院强制执行。进入执行程序的，本内容即为执行通知书，被执行人应依法向法院报告财产情况，不得实施任何规避执行行为。执行期间人民法院有权依法采取查封、扣押、冻结、搜查、拍卖、变卖义务人的财产等强制措施；依据情节限制义务人高消费、纳入失信名单，向社会公布并通报征信机构，依法予以信用惩戒；对拒不履行的义务人，人民法院可以采取罚款、拘留等措施，直至依法追究刑事责任
- 其他关键字段 `case_type`：民事案件
- 其他关键字段 `law_articles`：["《中华人民共和国劳动合同法》 第十条", "《中华人民共和国劳动合同法》 第三十八条", "《中华人民共和国劳动合同法》 第八十二条", "《职工带薪年休假条例》 第三条", "《企业职工带薪年休假实施办法》 第十条", "《企业职工带薪年休假实施办法》 第十一条", "《企业职工带薪年休假实施办法》 第十二条", "《中华人民共和国民事诉讼法》 第六十七条"]

### 案例 4

- case_id：`（2023）浙0203民初10927号|龙立波、宁波杉鼎服饰有限公司劳动争议一审民事判决书|2024-01-12`
- title：龙立波、宁波杉鼎服饰有限公司劳动争议一审民事判决书
- court：宁波市海曙区人民法院
- date：`2024-01-12`
- 主要文本字段 `facts`：{"entryDate":"2021年3月1日","officialContract":"否","latestContract":{"from":"unknown","to":"unknown","type":"unknown"},"position":[{"name":"电脑绣花制版师","byContract":"否","actual":"是","indoor":"unknown"}],"monthlySalary":{"byContract":"unknown","actual":"每月11000元，实际每月发放9000元，剩余每月2000元于年底一次性发放","distributeMethod":"现金发放一部分、银行转账一部分","average12Month":"unknown"},"socialInsurance":{"payment":"被申请人已缴纳","from":"2021年5月","to":"2022年9月","compensation":"否","compensationAmount":"unknown","compensationType":"unknown"},"currentStatus":{"resign":"是","resignDate":"2022年9月30日","resignReason":"被被告单方违法辞退","officialNotice":"否","officialNoticeType":"unknown","officialNoticeDate":"unknown","handover":"unknown","handoverDate":"unknown"},"laborRelation":"是","overtime":"否","annualLeave":"否","workInjuryBenifits":"否","medic…
- 主要文本字段 `legal_issues`：["劳动争议"]
- 主要文本字段 `judgment`：被告宁波杉鼎服饰有限公司支付原告龙立波2021年3月1日至2022年9月30日期间的工资差额18000元，于本判决生效之日起十日内履行完毕。 如果未按本判决指定的期间履行给付金钱义务，应当依照《中华人民共和国民事诉讼法》第二百六十四条及相关司法解释之规定，加倍支付迟延履行期间的债务利息。 本案案件受理费免于收取。 如不服本判决，可以在判决书送达之日起十五日内，向本院递交上诉状，并按照对方当事人或者代表人的人数提出副本，上诉于浙江省宁波市中级人民法院；也可以在判决书送达之日起十五日内，向浙江省宁波市中级人民法院在线提交上诉状。 本判决生效后，义务人应在判决确定的履行期限内自动履行。如义务人不履行本判决确定义务的，权利人可自履行期限届满之日起两年内申请法院强制执行。执行期间人民法院有权依法采取查封、扣押、冻结、搜查、拍卖、变卖义务人的财产等强制措施；依据情节限制义务人高消费、纳入失信名单，向社会公布并通报征信机构，依法予以信用惩戒；对拒不履行的义务人，人民法院可以采取罚款、拘留等措施，直至依法追究刑事责任。
- 其他关键字段 `case_type`：民事案件
- 其他关键字段 `law_articles`：["《中华人民共和国民事诉讼法》 第六十七条第一款", "《中华人民共和国民事诉讼法》 第一百四十七条"]

### 案例 5

- case_id：`（2023）浙0109民初19395号|陶逸谦、杭州明州医院劳动争议一审民事判决书|2024-01-31`
- title：陶逸谦、杭州明州医院劳动争议一审民事判决书
- court：杭州市萧山区人民法院
- date：`2024-01-31`
- 主要文本字段 `facts`：{"entryDate":"2021年9月15日","officialContract":"是","latestContract":{"from":"2021年9月15日","to":"2024年9月14日","type":"固定期限合同"},"position":[{"name":"护理类工作","byContract":"是","actual":"是","indoor":"unknown"}],"monthlySalary":{"byContract":"基本工资XXXX元，岗位工资XXX元，浮动工资XXX元","actual":"XXXXX元","distributeMethod":"银行转账","average12Month":"XXXX元"},"socialInsurance":{"payment":"已缴纳","from":"2022年2月","to":"2023年1月","compensation":"否","compensationAmount":"unknown","compensationType":"unknown"},"currentStatus":{"resign":"是","resignDate":"2023年2月28日","resignReason":"被告未及时足额支付劳动报酬","officialNotice":"是","officialNoticeType":"解除","officialNoticeDate":"2023年2月28日","handover":"是","handoverDate":"2023年3月1日"},"laborRelation":"是","overtime":"是","annualLeave":"是","workInjuryBenifits":"否","medicalPeriodBenifits":"否","nonC…
- 主要文本字段 `legal_issues`：["劳动争议"]
- 主要文本字段 `judgment`：确认陶某某与A医院之间的劳动关系于2023年2月28日解除 A医院于本判决生效之日起十日内支付陶某某加班费XXXX元 A医院于本判决生效之日起十日内支付陶某某2023年2月份的工资XXXX元、月度奖金XXXX元、年终奖XXXX元，共计XXXX元 A医院于本判决生效之日起十日内支付陶某某经济补偿金XXXXX元 驳回陶某某的其余诉讼请求 如果未按本判决指定的期间履行给付金钱义务，应当依照《中华人民共和国民事诉讼法》第二百六十四条之规定，加倍支付迟延履行期间的债务利息 案件受理10元，按四分之一收取2.5元，由陶某某负担0.5元，A医院负担2元，予以免交 本判决为终审判决
- 其他关键字段 `case_type`：民事案件
- 其他关键字段 `law_articles`：["《中华人民共和国劳动法》 第四十四条", "《中华人民共和国劳动法》 第五十条", "《中华人民共和国劳动合同法》 第三十八条第一款第（二）项", "《中华人民共和国劳动合同法》 第四十六条", "《中华人民共和国劳动合同法》 第四十七条", "《中华人民共和国民事诉讼法》 第六十七条"]

## 目标字段映射判断

| 目标字段 | 判断 | 方案说明 |
| --- | --- | --- |
| `case_id` | 直接映射 | 源字段 `case_id` |
| `title` | 直接映射 | 源字段 `title` |
| `court` | 直接映射 | 源字段 `court` |
| `judgment_date` | 改名映射 | 源字段 `date`，需统一日期格式 |
| `raw_text` | 组合生成 | 源数据无同名字段，可由 `facts`、`legal_issues`、`law_articles`、`judgment` 组合；需保留来源标签 |
| `keywords` | 转换生成 | 源数据无同名字段，可由 `legal_issues` 与 `law_articles` 规范化生成，不能无依据臆造 |
| `dispute_focus` | 转换生成 | 源数据无同名字段，可从 `legal_issues` 提取；应标记为派生字段 |
| `basic_facts` | 直接/改名映射 | 源字段 `facts` |
| `court_reasoning` | 直接/改名映射 | 源字段 `judgment`；需确认其内容是否同时包含裁判结果 |
| `judgment_result` | 待拆分映射 | 源字段无同名字段，需从 `judgment` 中拆分结果或保留原文并标记不确定 |

## 接入建议

1. 保留源记录和源字段，不直接覆盖原始数据。
2. 将 `date` 映射为 `judgment_date`，同时保留原始日期文本以便追溯。
3. 使用带字段标签的组合文本生成 `raw_text`，避免把 `facts`、法律争点和裁判内容混为无来源文本。
4. `keywords`、`dispute_focus` 属于派生字段，应记录生成规则或置信度。
5. `judgment` 可能同时包含裁判理由和结果，`court_reasoning` 与 `judgment_result` 的拆分需要单独规则和抽样验证。

生成时间：`2026-08-26 00:53:03 +0800`。

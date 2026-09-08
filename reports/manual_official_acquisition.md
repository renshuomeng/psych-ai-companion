# CARE-Psy Manual Official Acquisition Queue

生成时间：2026-08-28

## 目的

以下资源属于高价值官方来源，但当前自动下载流程没有稳定获取到可直接解析的文件，或仍需要人工确认最终官方页面。不要使用镜像站，不要创建空文件冒充资料。

人工获取后，请放到：

```text
backend/data/knowledge_base/raw/manual/official/<SOURCE_ID>/
```

然后运行：

```powershell
python scripts\rag\build_knowledge_base.py --mode staging
python scripts\rag\build_dense_index.py --mode staging --incremental --batch-size 64
python scripts\rag\review_sources.py inspect SOURCE_ID
```

审核通过后再执行 source-level approve 和 production build。

## 需要人工确认或下载的资源

| Source ID | 官方来源 | 官方页面 | 为什么有用 | 预期主题 | 预期人群 | 当前状态 | 人工操作 |
|---|---|---|---|---|---|---|---|
| `CN_NHC_HEALTH_LITERACY_2024` | 国家卫生健康委员会 | https://www.nhc.gov.cn/xcs/c100123/202405/73a4927142f34152abed875634a3c13b.shtml | 中文心理健康素养、睡眠、焦虑、抑郁和科学求助科普，可补中文 psychoeducation 缺口 | `mental_health_literacy`, `sleep`, `anxiety`, `depression`, `scientific_help_seeking` | children, adolescents, young_adults, adults, older_adults | 自动下载返回 HTTP 412；registry 已修正为精确官方 URL | 用浏览器打开官方页面，保存 HTML/PDF 到 `backend/data/knowledge_base/raw/manual/official/CN_NHC_HEALTH_LITERACY_2024/` |
| `CN_MOE_SCHOOL_MH_GUIDE` | 中华人民共和国教育部 | https://www.moe.gov.cn/srcsite/A06/s3325/201212/t20121211_145679.html | 中文学校心理健康政策与儿童/青少年支持边界，可补学生场景 governance/campus support | `children`, `adolescents`, `school_support`, `parent_support` | children, adolescents, parents, caregivers | 已自动下载成功，进入 staging：5 份 cleaned 文档，39 个 pending chunk | 暂不需要人工下载；下一步人工审核该 source，审核通过后再按规则进入 production |
| `NIA_DEPRESSION_OLDER_ADULTS` | National Institute on Aging | https://www.nia.nih.gov/health/mental-and-emotional-health/depression-and-older-adults | 老年抑郁和低落情绪科普，可补 older_adults 缺口 | `depression`, `low_mood`, `aging`, `professional_help` | older_adults, caregivers | 早期自动获取报告记录为 HTTP 405，不绕过 | 浏览器下载官方页面或 PDF，放到 `backend/data/knowledge_base/raw/manual/official/NIA_DEPRESSION_OLDER_ADULTS/` |
| `NIA_LONELINESS` | National Institute on Aging | https://www.nia.nih.gov/health/loneliness-and-social-isolation | 孤独、社会隔离、社会支持资料，可补 loneliness/social_support 缺口 | `loneliness`, `social_isolation`, `social_support` | older_adults, caregivers | 早期自动获取报告记录为 HTTP 405，不绕过 | 浏览器下载官方页面或 PDF，放到 `backend/data/knowledge_base/raw/manual/official/NIA_LONELINESS/` |
| `SAMHSA_FAMILY_SUPPORT` | SAMHSA | https://www.samhsa.gov/families | 家庭、照护者和亲子支持资料，可补 family/caregiver 场景 | `family_relationships`, `caregiving_stress`, `communication`, `support_boundaries` | parents, caregivers, family_members_supporting_others | 早期自动获取报告记录为 HTTP 403，不绕过 | 浏览器下载官方页面或 PDF，放到 `backend/data/knowledge_base/raw/manual/official/SAMHSA_FAMILY_SUPPORT/` |
| `SAMHSA_TRAUMA_INFORMED_CARE` | SAMHSA | https://www.samhsa.gov/resource/dbhis/practical-guide-implementing-trauma-informed-approach | 创伤知情支持与非伤害性沟通，可补 trauma/helper skills | `trauma`, `communication`, `non_harmful_helping`, `safety` | people_exposed_to_trauma, family_members_supporting_others | 早期自动获取报告记录为 HTTP 403，不绕过 | 浏览器下载官方页面或 PDF，放到 `backend/data/knowledge_base/raw/manual/official/SAMHSA_TRAUMA_INFORMED_CARE/` |
| `UNICEF_ADOLESCENT_MH` | UNICEF | https://www.unicef.org/mental-health | 青少年心理健康科普，可补 adolescents/parents 支持场景 | `adolescent_development`, `stress`, `anxiety`, `low_mood`, `social_relationships` | adolescents, parents, caregivers | 早期自动获取报告记录为 HTTP 403，不绕过 | 浏览器下载官方页面或 PDF，放到 `backend/data/knowledge_base/raw/manual/official/UNICEF_ADOLESCENT_MH/` |

## 注意

- 这些资源放入 manual official 目录后仍是 `pending`，不能直接进入 production。
- safety-only、clinical_reference_only、涉及自伤/自杀或未成年人保护的内容，必须走 chunk-level 审核。
- 中文直接支持资料仍是当前短板；如果后续找到高校心理中心发布的稳定自助材料，应先进入 `campus_support` 或 `interventions` 的 pending 队列，再审核。

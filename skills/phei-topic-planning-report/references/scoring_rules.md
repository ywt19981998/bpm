# PHEI Education Title Scoring Rules

Use this reference when assigning self-scores, suggested scores, or reviewer-style scores for report sections one through six.

## Default Calibration

- Total score is 100.
- For ordinary viable education titles, default to a conservative total around 60-70.
- Do not inflate scores to 80+ unless the source has strong evidence: national/provincial platform, excellent author credentials, clear award path, strong package-sale/subsidy/profit data, and rich resources.
- Use exact maximums from the 2026 education-title scoring rules:
  - 选题内容: 35
  - 作者情况: 10
  - 策划过程与可行性: 5
  - 获奖潜质: 5
  - 成本与盈利估算: 35
  - 市场定位与营销: 10

## Calibration Example: AI实战选题

Use this as a known 65-point benchmark, especially for titles with good content and market positioning but weaker author/award/economic evidence.

| 评分项 | 满分 | 终批人评分 |
| --- | ---: | ---: |
| 选题内容 | 35 | 30 |
| 作者情况 | 10 | 4 |
| 策划过程与可行性 | 5 | 5 |
| 获奖潜质 | 5 | 0 |
| 成本与盈利估算 | 35 | 17 |
| 市场定位与营销 | 10 | 9 |
| 总分 | 100 | 65 |

## Section Rules

### 选题内容（35分）

Components:
- Political/publishing orientation: 10 points. Usually give 10 when the title is normal education/technology content with no apparent orientation risk.
- Publishing positioning: 10 points. Usually give 10 when it fits education publishing and the relevant branch/category.
- Innovation/systematic structure: 10 points. Give 8-10 for clear innovation, complete knowledge system, and clear chapter system; 5-7 for moderate innovation and reasonably clear structure; 0-4 for old, unclear, or poorly structured content.
- Copyright and rights permission: 5 points. Give 5 only when paper+digital exclusive publishing rights and related online communication rights are clearly supported; give 3 when only paper or digital rights are clear; give 0-3 when rights are missing or uncertain.

Typical conservative range:
- Strong normal title: 28-32.
- Viable but ordinary title: 24-28.
- Weak structure or unclear positioning: below 24.

### 作者情况（10分）

Components:
- First author: 7 points.
  - 6-7: national talent, national teaching master, national teaching achievement/competition key member, national first-class major/course key member, national expert, national committee member, provincial teaching researcher or above, university leader, or equivalent influence.
  - 3-5: provincial talent/teaching master/expert, provincial first-class major/course key member, provincial committee member, municipal teaching researcher, department leader, discipline/program leader, provincial award key member, or author with rich teaching/writing experience and good potential.
  - 0-2: other.
- Team composition: 3 points. Give 3 when the team has a reasonable age/title structure and can support future revision; give 1-2 when somewhat reasonable.

Typical conservative range:
- Solid school author/team but no national/provincial highlight: 4-6.
- National/provincial platform or very strong author: 7-10.
- Thin author information: 0-3.

### 策划过程与可行性（5分）

Components:
- Topic source and planning logic: 2 points.
- Editor/title control ability: 2 points.
- Publication schedule: 1 point.

Give 4-5 when the source is based on real teaching needs/policy/frontier, planning logic is clear, the editor/title control is credible, and the schedule is explicit. Give 2-3 when one part is vague. Give 0-1 when the source or schedule is unclear.

### 获奖潜质（5分）

Components:
- Award/project potential: 4 points. National-level potential: 4; provincial/ministerial-level potential: 2; otherwise 0.
- Copyright output or international academic exchange potential: 1 point; otherwise 0.

Default to 0 when the source does not clearly support an award path. Give 2 only when there is credible provincial-level planning/course/resource evidence. Give 4-5 only for clearly strong, platform-backed titles.

### 成本与盈利估算（35分）

Components:
- Cost/profit calculation: 20 points. Lifecycle estimated gross profit >=100,000 yuan gets 20; 90,000-99,999 gets 18; continue down by 2 points per 10,000 yuan band. If the report lacks concrete profit data, choose a conservative score, usually 15-18 for a viable title with some usage basis but missing final commercial assumptions.
- Subsidy/package-sale: 15 points.
  - 15: package-sale >=10,000 copies, paper subsidy >=100,000 yuan, or digital subsidy >=60,000 yuan.
  - 10: package-sale >=6,000 copies, paper subsidy >=80,000 yuan, or digital subsidy >=45,000 yuan.
  - 5: package-sale >=4,000 copies, paper subsidy >=60,000 yuan, or digital subsidy >=35,000 yuan.
  - 2: has package-sale or subsidy below above thresholds.
  - 0: no package-sale or subsidy.

Do not invent package-sale, subsidy, or gross profit. If missing, keep this score modest. The AI实战 benchmark used 17/35.

### 市场定位与营销（10分）

Components:
- Target readers: 2 points. Give 2 when clear.
- Competitor comparison: 2 points. Give 2 for strong differentiation, 1 for some competitiveness, 0 for weak/absent comparison.
- Marketing plan/channels: 2 points. Give 2 for specific and operable channels; 0-1 for generic channels.
- Supporting resources: 4 points. Give 4 for rich, high-quality multimedia/resource package such as PPT, lesson plans, cases, question bank, digital resources; 2 for moderately rich resources; 0 for weak resources.

Typical conservative range:
- Clear target readers, real resources, decent channels: 7-9.
- Generic marketing/resources: 4-6.
- Weak market evidence: below 4.

## Suggested Output

After drafting sections 一到六, add:

```markdown
建议评分：
| 评分项 | 满分 | 建议分 | 理由 |
| --- | ---: | ---: | --- |
| 选题内容 | 35 | 30 | ... |
| 作者情况 | 10 | 5 | ... |
| 策划过程与可行性 | 5 | 5 | ... |
| 获奖潜质 | 5 | 0 | ... |
| 成本与盈利估算 | 35 | 17 | ... |
| 市场定位与营销 | 10 | 8 | ... |
| 总分 | 100 | 65 | ... |
```

Keep score reasons short and practical. Flag missing commercial assumptions under “待确认信息”.

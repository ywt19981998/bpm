# Report Sections One Through Six

Use this reference after extracting the application facts.

## Source Priority

1. Filled table fields in the topic application form.
2. Attached/continued paragraphs after headings such as `大纲及目录` and `适合读者（详细）`.
3. User-provided extra materials, if any.
4. Conservative editorial inference from the above, clearly avoiding invented facts.

## Field Mapping

### 一、选题内容（35分）

Use:
- `选题名称`
- `内容简介`
- `定位、特色、选题背景和必要性`
- `本选题的 编写思路 和报选优势`
- `同类书比较`
- `大 纲 及 目 录` plus attached outline paragraphs
- publication form, if available

Write:
- Correct publishing orientation and fit with education/technology publishing.
- Publishing positioning and reader value.
- Concise book structure: method/system, project practice, appendices/resources.
- Innovation and differentiators.
- Copyright status only if source supports it; otherwise omit it from the section body.

### 二、作者情况（10分）

Use:
- `姓名`, `职称`, `单位名称`, `职务`, `从事方向`
- `工作简历`
- `个人/集体荣誉`
- `主要著作出版情况`
- `所承担过的重点科研或教研项目以及在项目中所承担的工作`
- `教学成果获奖情况、作品获奖情况`
- `合作者 情况简介`
- `本书的 编写分工`

Write:
- First author profile first.
- Then team/coauthor complementarity, if present.
- Emphasize authority relevant to the topic.
- Mention first-book risk gently if the form says this is the first published book, while balancing it with practice credentials.

Do not include ID number, home address, phone, email, or exact private contact details.

### 三、策划过程与可行性（5分）

Use:
- `本选题的 编写思路 和报选优势`
- `定位、特色、选题背景和必要性`
- `内容简介`
- `书稿编写进度`
- `大纲及目录`
- sample chapter availability, if shown

Write:
- Topic source and pain point.
- Editorial planning logic.
- Content maturity and schedule feasibility.
- Use the available manuscript, outline, schedule, and resource facts to support a direct feasibility judgment. Do not assign follow-up, verification, or manuscript-organization tasks to editors or authors.

### 四、获奖潜质（5分）

Use:
- education/course applicability from `读者定位`, `适合读者`, and `市场定位`
- resource/package potential from `内容简介`, `大纲及目录`, and `编写思路`
- author achievements only when relevant

Write cautiously:
- Do not promise awards.
- Use phrases like “具备进一步培育为……的潜力”.
- Mention course resource, training resource, digital resource, copyright output, or international communication only when the topic supports it.

### 五、成本与盈利估算（35分）

Use:
- `估计字数（千字）`
- `本书是否有资助？资助金额为多少（万元）`
- any user-provided price, print run, royalty, discount, print-sheet, subsidy, package-sale, or profit assumptions

Current fixed user rule:
- For the web app and default report generation, Section 五 must use the following fixed block unless the user explicitly gives a different cost/profit scheme.
- Keep the two full-width spaces at the beginning of each line.
- Leave “出版资助” and “预计总毛利润” blank after the colon unless the user supplies values.

Fixed shape:

```text
　　（一）纸质教材
　　1.出版规格
　　（1）版权字数： 350 千字。
　　（2）印张： 14。
　　（3）正文印刷色数：  单色。

　　2.盈利估算
　　（1）定价：  59.8  元。
　　（2）版税（率）：  8%。
　　（3）发货折扣：    65%。
　　（4）预估首印数：   1200册。
　　（5）预估总印数：   3000册。
　　（6）包销册数：     0册；包销折扣： 0 %。
　　（7）出版资助：   
　　（8）预计总毛利润：   
```

### 六、市场定位与营销（10分）

Use:
- `读者定位`
- `适合读者（详细）`
- `同类书比较`
- `内容简介`
- `定位、特色、选题背景和必要性`
- `本选题的 编写思路 和报选优势`
- resources mentioned in outline/appendices

Write:
- Target readers in 2-4 groups.
- Competitor landscape and differentiation.
- Marketing channels: schools/courses, technical communities, author network, public lectures/training, platform/resource package.
- Supporting resources: courseware, teaching outline, case files, prompts, templates, code/example repository, if source supports them.

## Missing-Information Rules

Add a “待确认信息” list when any of the following are absent:
- final title if only tentative title exists
- publication form
- manuscript delivery or expected publication date
- copyright authorization/permissions
- price, royalty rate, print run, discount, package-sale, subsidy, profit
- confirmed companion resources
- award/copyright-output plan

## Tone Calibration

Good report prose is written for publisher leadership deciding whether to approve the title. It should be positive but not salesy, and should convert raw author claims into verifiable publishing value. It must not read like instructions to the responsible editor, planning editor, or author.

When a fact is missing, omit that point from sections 一、二、三、四、六. Do not narrate the absence with phrases such as “申报表未提供”, “申报表中没有体现”, “缺少相关依据”, or “有待进一步确认”. Missing items may remain in the separate `pending_questions` list under the existing missing-information rules.

## AI-Driven Software Development Report Style Calibration

For the web app and default generation, use the writing style of the approved `AI驱动软件开发实战` planning report for sections 一、二、三、四、六. Section 五 remains the fixed cost/profit block above and should not be stylistically rewritten.

- Section 一 should usually have about 3 paragraphs: first judge publishing orientation, real-world topic value, and publishing positioning; then summarize book scale, content structure, and knowledge/practice chain; then state innovation points, often using a “三方面” structure, and cautiously mention copyright authorization/risk if supported.
- Section 二 should usually have about 2 paragraphs: first describe the first author’s role, teaching/research/industry experience, and relevance to the topic; then describe representative achievements, projects, published works, patents, courses, or team foundation. If this is a first book, balance risk with “虽然……但……” wording.
- Section 三 should usually have about 3 paragraphs: start from teaching/industry/course pain points; then explain the planning logic and content loop such as “概念-方法-案例-工具包”; finally assess manuscript maturity, schedule, source material, and feasibility.
- Section 四 should usually have about 2 paragraphs: first discuss textbook/course/training/digital-resource extension potential; then discuss copyright output, digital-course potential, resource dissemination, or international communication. Never promise awards.
- Section 六 should usually have about 4 paragraphs: target reader groups; competitor/similar-title landscape and differentiation; marketing combination such as course promotion, author channels, community communication, sample-chapter trials, talks, or training; and supporting resources such as courseware, syllabi, cases, templates, repositories, or “图书+资源+服务”.
- Across these sections, avoid table-like extraction and empty claims. Each paragraph should help answer why the title is worth publishing, how the content is organized, and how it can be adopted or promoted.

## Paragraph Indentation

For sections 一到六, every body paragraph should visually begin with a two-character Chinese first-line indent. When generating plain text or filling DOCX cells directly, prefix each body paragraph with two full-width spaces: `　　`. If the target Word template already has a two-character first-line-indent paragraph style, preserve that style and do not add extra visible spaces on top of the style indent.

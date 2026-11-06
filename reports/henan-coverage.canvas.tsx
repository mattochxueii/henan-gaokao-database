import { Callout, Divider, H1, H2, Link, Pill, Row, Stack, Stat, Table, Text, useCanvasState } from "cursor/canvas";

const papers = [
  [
    "2025",
    "数学",
    "全国一卷",
    "19 题已建索引",
    "https://www.jhgk.cn/upload/file/20250610/1749549496776033663.pdf"
  ],
  [
    "2025",
    "语文",
    "全国一卷",
    "卷目已登记",
    "https://jhcee.cn/pc/gk_information/consultation_detail-d6278da9-0614-42f2-b955-956d684bd64c.html"
  ],
  [
    "2025",
    "英语",
    "全国一卷",
    "卷目已登记",
    "https://jhcee.cn/pc/gk_information/consultation_detail-d6278da9-0614-42f2-b955-956d684bd64c.html"
  ],
  [
    "2025",
    "物理",
    "河南卷",
    "卷目已登记",
    "https://kaosj.com/papers/2025/06/2025-henan-gaokao-physics-paper/"
  ],
  [
    "2025",
    "化学",
    "河南卷",
    "卷目已登记",
    "https://kaosj.com/papers/2025/06/2025-henan-gaokao-chemistry-paper/"
  ],
  [
    "2025",
    "生物学",
    "河南卷",
    "卷目已登记",
    "https://kaosj.com/papers/2025/07/2025-henan-gaokao-biology-henan-paper/"
  ],
  [
    "2026",
    "数学",
    "全国一卷",
    "19 题已建索引",
    "https://www.jhgk.cn/upload/file/20260608/1780886746084032608.pdf"
  ],
  [
    "2026",
    "语文",
    "全国一卷",
    "卷目已登记",
    "https://www.jhgk.cn/mobile/trendDetails.htm?id=d7c00c3c-6b56-4ea5-86f6-1b627dfa708b"
  ],
  [
    "2026",
    "英语",
    "全国一卷",
    "卷目已登记",
    "https://www.jhgk.cn/mobile/trendDetails.htm?id=d7c00c3c-6b56-4ea5-86f6-1b627dfa708b"
  ],
  [
    "2026",
    "物理",
    "河南卷",
    "卷目已登记",
    "https://kaosj.com/papers/2026/07/2026-gaokao-physics-henan-paper/"
  ],
  [
    "2026",
    "化学",
    "河南卷",
    "卷目已登记",
    "https://kaosj.com/papers/2026/07/2026-gaokao-chemistry-henan-paper/"
  ],
  [
    "2026",
    "生物学",
    "河南卷",
    "卷目已登记",
    "https://kaosj.com/papers/2026/07/2026-gaokao-biology-henan-paper/"
  ]
];

const policy = {
  "2025": "https://www.haeea.cn/attach/file/20250428/20250428150241_6941_3c9d9016.pdf",
  "2026": "https://xcoss.henan.gov.cn/typtfile/20260427/cc9d5c1a332341f0a7d9223f54f0cf62.pdf",
};

export default function HenanGaokaoCoverage() {
  const [year, setYear] = useCanvasState("henan-exam-year", "全部");
  const filtered = papers.filter((paper) => year === "全部" || paper[0] === year);

  return (
    <Stack gap={18} style={{ maxWidth: 920, padding: 24 }}>
      <Stack gap={5}>
        <Text tone="secondary" size="small">河南新高考 · 第一阶段 · 2026-11-06</Text>
        <H1>六科真题资料完整性</H1>
        <Text tone="secondary">按年份核查实际用卷，查看目前可追溯的卷面候选。</Text>
      </Stack>

      <Row gap={24} wrap>
        <Stat value="12 / 12" label="用卷归属已核实（卷）" />
        <Stat value="38" label="数学题号索引（题）" />
        <Stat value="0 / 12" label="本地完整原卷（卷）" />
      </Row>
      <Callout tone="warning">已定位卷面与答案候选。文件级保存许可仍待核实，题干、原卷、答案和音频尚未入库。</Callout>

      <Divider />
      <Stack gap={10}>
        <H2>逐卷候选来源</H2>
        <Row gap={8} wrap>
          {["全部", "2025", "2026"].map((choice) => (
            <Pill key={choice} active={year === choice} onClick={() => setYear(choice)}>{choice}</Pill>
          ))}
        </Row>
        <Table
          headers={["年份", "学科", "河南实际用卷", "目录进度", "卷面来源"]}
          rows={filtered.map(([examYear, subject, edition, progress, url]) => [
            examYear, subject, edition, progress, <Link key={url} href={url}>打开候选</Link>,
          ])}
        />
        <Text tone="secondary" size="small">来源为仓库逐卷登记。地区范围为河南，考试年份为 2025–2026 年。</Text>
      </Stack>

      <Stack gap={8}>
        <H2>英语听力</H2>
        <Text>两年均考听力。听力卷面 30 分。河南英语计分用笔试卷面 120 分乘 1.25 后四舍五入。两年均已定位试题、文本和录音候选。</Text>
        <Row gap={12} wrap>
          <Link href={policy["2025"]}>2025 年招生规定</Link>
          <Link href={policy["2026"]}>2026 年招生规定</Link>
        </Row>
      </Stack>

      <Stack gap={8}>
        <H2>2026 年数学版本差异</H2>
        <Text>第 13 题第一空的填答对象、第 17 题分值，以及第 18 题的点名与面积条件存在候选差异。</Text>
        <Row gap={12} wrap>
          <Link href="https://www.jhgk.cn/upload/file/20260608/1780886746084032608.pdf">锦宏排版候选</Link>
          <Link href="https://kaosj.com/papers/2026/06/2026-national-volume-1-gaokao-math-paper/">考试卷网候选</Link>
          <Link href="https://gk2026math.lewang.dev/solutions">个人解析候选</Link>
        </Row>
      </Stack>
    </Stack>
  );
}

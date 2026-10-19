# cn2an 缺陷审查：4 个已复现并修复的缺陷

对 [`Ailln/cn2an`](https://github.com/Ailln/cn2an) v0.5.24（中文数字 ⇄ 阿拉伯数字，768 ★，MIT）
提交 `7c9ba07` 做的一次缺陷审查。四个缺陷都先复现、再定位根因、再修复，并且**修复前后都用同一份测试跑过**。

| | |
| --- | --- |
| 上游基线 | `pytest` → 3 passed（全绿，说明这些缺陷上游测试没覆盖） |
| 修复后 | `pytest` → **73 passed**（新增 70 + 上游 3） |
| 差分等价性 | 三个公开入口 × **408 组探针，与上游逐字节全同** |
| 变异测试 | 逐一撤掉修复 → **4/4 全部被抓** |
| 补丁 | `patch --binary -p1` 可打到 `7c9ba07` 干净导出，6 个文件逐字节还原 |

![同一份测试，两份代码](assets/tests_red_to_green.png)

同一份 70 条回归测试：在上游 **35 红 / 36 绿**，修复后 **70 全绿**。
那 36 条是护栏（短小数、上界内往返等），它们在上游就是绿的，用来防止修复把别的地方改坏。

## 四个缺陷

### D1 · `an2cn(…, "rmb")`：长小数丢失进位（金额大写会差钱）

```python
cn2an.an2cn("0.999999999999999999", "rmb")
# 上游: '玖角玖分'        应为: '壹元整'
cn2an.an2cn("10.999999999999999999", "rmb")
# 上游: '壹拾元玖角玖分'  应为: '壹拾壹元整'
```

根因不是舍入策略，而是**两步的先后顺序**：`an2cn` 先用 `__decimal_convert()` 把小数逐位转成
`"点" + 数字` 再取 `[1]` 作角、`[2]` 作分，而 `__decimal_convert()` 的第一步就把小数截到 16 位。
截断是纯丢弃，被丢掉的 `9` 本该让整串进位成 `1.00`。

修复：新增 `__round_rmb()`，**先取位再截断**；只有「16 位以上 + 玖角玖分 + 其后全是 9」才进位。
16 位以内的行为逐字节不变（`5.999` → `伍元玖角玖分`、`1.045` → `壹元零肆分`）。

### D2 · `cn2an(…, "smart")`：纯整数串返回 `float`

```python
json.dumps(cn2an.cn2an("123", "smart"))
# 上游: '123.0'   修复后: '123'
```

`smart` 对「本身就是阿拉伯数字」的输入走了一条快速通道，用 `float()` 解析；而 `strict` / `normal` /
`smart` 的中文分支都由 `__integer_convert()` 返回 `int`。同一个数，返回类型取决于写法，下游做
JSON 或整数校验时会静默变形。修复：整数值归一为 `int`（`"1.5"` 仍是 `1.5`）。

### D3 · `transform()`：非字符串入参泄漏 `AttributeError` / `TypeError`

```python
cn2an.transform(None)     # 上游: AttributeError: 'NoneType' object has no attribute 'replace'
cn2an.transform(b"123")   # 上游: TypeError: a bytes-like object is required, not 'str'
```

`cn2an()` / `an2cn()` 对空值和非法值统一抛 `ValueError`，`transform()` 却把 `re.sub` 的实现细节
漏了出去。修复：入口加类型守卫，统一 `ValueError`。

### D4 · 文档声明的上界 `10**16` 双向都不可达

上游 README 写着「最大支持到 `10**16`，即 `千万亿`」，但实际上：

```python
cn2an.an2cn(10**16, "low")   # ValueError: 超出数据范围，最长支持 16 位
cn2an.cn2an("一亿亿")        # ValueError: 不符合格式的数据：一亿亿
```

两个方向的实现都停在 `10**16 - 1`。`10**16` 在中文里是「亿亿」——一个**双字单位**，而
`UNIT_CN2AN` 是逐字符查表，直接塞进去会让换算在 `亿` 处提前结束。修复：只在**正则层面**加入
`[一壹]亿亿`（乘数限定为「一」，所以 `九亿亿` 仍被拒绝，上界不被突破）。

## 验证方式

### 差分等价性：修复没有波及别的路径

![nothing else moved](assets/differential.png)

- 全 API 408 组探针（整数/小数 × 4 模式、CJK 数字 × 4 模式、21 个句子 × 4 种 transform 调用、
  空串 / `None` / 全角 / 非法字符）→ **408 组与上游逐字节相同**
- rmb 专项 162 组（9 个整数 × 18 种小数部分）→ 153 组相同，**仅 9 组「全 9 长小数」按预期改变**

### 变异测试：测试真的能挡住回退

![mutation coverage](assets/mutation_coverage.png)

逐一撤掉四处修复，重跑新测试，分别有 4 / 9 / 14 / 5 条失败 —— 4/4 全被抓，不是「改不改都绿」。

## 刻意没有改的（排查后不成立）

| 候选 | 结论 |
| --- | --- |
| `rmb` 角分规则「不统一」（`1.045`→零肆分 vs `0.015`→壹分） | 逐格枚举确认：角=小数第 1 位、分=小数第 2 位、第 3 位不参与进位（`5.559`→伍角伍分）。规则自洽，差异来自 1 位小数的整角分支，属既有设计 |
| `cn2an("1e3")` 报错 | `smart` 只承诺「中文数字 + 阿拉伯数字」，明确拒绝而非静默出错 |
| `transform("两三个")` → `23个` | 分词歧义，上游 issue #87 讨论过未定为缺陷，无法在不误伤的前提下修复 |
| `10**16 < v < 10**17` 的 17 位整数 | 超出声明上界；刻意不扩，并用测试锁住「`10**17` 仍拒绝」 |

## 文件

```
REPORT.md                     完整报告（根因、修复、逐条证据）
NOTICE.md                     修改声明
defect-fixes.patch            对 7c9ba07 干净导出的补丁
test_defects_regression.py    70 条回归测试
repro.json                    27 组「上游 / 修复后」实测对照
UPSTREAM_README.md            上游原 README（被本文件占用位置）
assets/                       报告配图（由 chart_data.json 渲染，无手打数字）
cn2an/                        修复后的包源码
```

复现：

```bash
pip install -r requirements.txt -r requirements_test.txt
python -m pytest -q                                              # 73 passed
git -C . archive HEAD | tar -x -C /tmp/up && cp test_defects_regression.py /tmp/up/
(cd /tmp/up && python -m pytest test_defects_regression.py -q)   # 35 failed / 36 passed
```

## 许可

原项目 MIT。本仓库在上游代码基础上做上述修改，原版权声明见 `LICENSE`，修改范围见 `NOTICE.md`。

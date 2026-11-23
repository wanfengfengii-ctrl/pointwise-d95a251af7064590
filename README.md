# 带材张力疲劳维护账

白班登记试验的实际入段张力，后班复核试验台原测并冻结证据。夜班点收证据，在站库关闭后签存分班疲劳账。维护班按原号领取闭环明细与采用的两份依据。后班修订或前班更正各有新号，原号继续可用。

## 运行

只需 Python 3.11 和标准库。从项目根目录运行控制台提供的完整回归入口及独立样例。

```sh
python3 -B check_project.py
python3 -B -m examples.demo
```

样例从 `examples/rear.json` 和 `examples/prefixes.json` 读取有限输入。它使用独立临时站库及离线库，关闭站库后用同一实收件签存三份报告，重开离线库后按各自原号领取。输出含确切选件、前班起点及各班量程和计数。实际工作库由调用者提供路径并保管。

## 公开 Python 入口

```python
from contextlib import closing

from analysis.issue import initialize_issuance, issue
from handoff.corrections import register
from intake.accept import receive
from intake.desk_store import open_desk
from records.freeze import record
from records.source_store import open_source
from reports.history import read
from reports.publish import publish

with closing(open_desk('maintenance.sqlite')) as desk:
    with closing(open_source('station.sqlite')) as source:
        initialize_issuance(source)
        revision = record(source, 'strip-7', 6, [(1, 6), (2, 2), (3, 6), (4, 1)])
        receipt_id = receive(desk, issue(source, revision.revision_id))
    prefix_id = register(desk, 'strip-7', '3/2', 6)
    report_id = publish(desk, prefix_id, receipt_id)
    report = read(desk, report_id)
```

- `record` 登记试验与预期接点，校验整批读数并返回冻结修订。读数为 `Sample` 或二元、三元记录 `(sequence, tension[, sampled_at])`，采样时刻为可选站内文本。序号严格递增。通过 `corrects=revision_id` 为同一试验另建勘误版。也可单独登记试验后调用 `freeze_revision`。
- `review_frozen_revision` 提供站内样点可追溯的转折与独算账。`issue` 取明确指定的修订，返回 V1 交换件。同一修订可复领原身份与原字节。固定件必须由起于登记接点且首个有效方向下降的转折产生。
- `register` 返回固定前班号。`corrects=prefix_id` 登记关联原号的新记录。`receive` 验证交换件的来源、字节摘要和证据内容，返回固定实收号。`get_original` 按实收号提供正文原字节，`get_receipt` 提供点收出处和外层元数据。
- `publish` 使用指定前班号与实收号定稿。两份记录必须同属一项试验且接点相等。`read` 返回 `StoredReport`，含前班、实收、后班接点快照及明细。明细的 `front` 为前班、`rear` 为后班。

张力输入接受整数、`Fraction` 或可解析成 `Fraction` 的文本。起点 `x` 必须满足 `0 ≤ x < s`，`s` 为接点。站内转折合并连续等值平台，以平台首个样点为代表并保留端点张力。四点闭合采用中间量程同时小于或等于左右量程的判据，移除两个内点后立即复查。整段的共同接点只出现一次并归前班，每个闭环归被移除的首个内点。明细按班与有理量程排序，同班同量程合并，合法空账保留双方出处。原测序号、采样时刻和私有转折序列由站库保管。

`open_source` 与 `open_desk` 创建缺失结构，站库发行表由 `initialize_issuance` 初始化。重复初始化保留既有数据。参数、内容或配对无效时给出 `ValueError`，缺失指定记录时给出 `KeyError`，报告写入或提交失败时给出 `ReportWriteError` 并回滚。本例中的业务入口自行提交写入。低层写入函数供同一连接内的业务事务调用。

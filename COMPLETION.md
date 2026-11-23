# 补载闭环工单

后班试验在一个下降段结束。试验台随即封存原测，夜班随后登记一次实际补载及卸载。中心用关站前收到的原件办理，维护班按原报告号领取。当次复核依据始终是申请指定的前班号和后班实收号。前班登记或后班原测勘误另有新号。

## 调用与结果

沿用 `README.md` 中的 `open_source`、`initialize_issuance`、`open_desk`、`record` 和 `register`。

- `analysis.issue.issue_completion(source, revision_id)` 按确切冻结号发行，返回 `analysis.certificates.Envelope`，版本为整数 `2`。沿用原发行的接点和首方向审核，且最后一段严格下降。同一修订再次发行返回同一发行号及原字节。正文绑定发行号、试验号、冻结号、接点和末点。发行时尚无这次补载和卸载的实测值，响应须适用于所有合法前班起点、补载峰值和卸载终值。正文可包含计量所需的有理条件及量程信息。原测编号、采样时刻、按原顺序保存的私有转折和能够以任意后续波形继续重放的转折栈留站，可逆编码也视为携带原记录。响应的内部格式由实现定义。
- `intake.accept.receive_completion(desk, envelope)` 验收 V2，返回整数实收号。核对正文摘要、外层与正文的发行号、试验号和修订号，以及 V2 正文及响应格式。`intake.archive.get_original` 按实收号返回收到的原字节。拒收时不留半件。
- `reports.publish.publish_completion(desk, prefix_id, receipt_id, peak, end)` 返回整数报告号。指定前班和指定 V2 实收件须同试验、同接点。`peak` 和 `end` 沿用 `README.md` 中的有理张力输入，单位 kN。设末点为 `r`，申请须满足 `peak > r` 和 `0 <= end < peak`。计数语义是先取前班起点，接上后班转折，再接上峰值和终值，沿用原四点规则，从左到右连续核销。接点仅出现一次且归前班，新增两点归后班。每闭环按首个被移除内点所属班计入，量程以精确有理值归并排序。未闭合部分不计，空账照样签发。定稿、两项实测、两份实际依据和明细一次提交。
- `reports.history.read_completion(desk, report_id)` 读取已存报告。结果具有 `report_id`、`prefix`、`receipt`、`rear_seam`、`rows` 五项原报告字段，以及 `peak`、`end` 两项 `Fraction` 张力。`prefix` 为 `PrefixRecord`，`receipt` 为 `Receipt`，`rows` 为 `MaintenanceRow` 元组，保留原有 `front`、`rear` 和量程排序约定。更正和重开后均按原号领取存值。

坏来件、版本混用、末段或配对不合格及非法载荷报 `ValueError`，未知号沿用 `KeyError`。原接纳和签报入口只办理 V1，补载签报只使用 V2 实收号。定稿写入或提交失败沿用 `ReportWriteError`，本次无新增定稿，可用同一请求再办。旧发行、接纳、签读接口及历史件照常使用。

## 工单样例

固定接点 6 kN。A 的后班转折为 `6, 2`，B 为 `6, 1, 5, 2`。前班起点 0 kN 时，两份 V1 报告均为空。关站后补到 5 kN、卸至 0 kN，A 的后班记 3 kN 一次，B 的后班记 3 kN 和 4 kN 各一次。B 在终值恰为 1 kN 时仍有两项，终值为 3/2 kN 时只剩 3 kN。峰值为 9/2 kN、终值为 0 kN 时，B 后班应记 5/2 kN 与 4 kN 各一次。

C 的后班转折为 `6, 4, 5, 2`。起点和卸载终值均为 0 kN 时，峰值为 5/2 时后班记 1/2、1 kN 各一次，峰值为 7/2 时记 1、3/2 kN 各一次。峰值为 3 时两条 1 kN 合为一行，计数为 2。

## 核验与演示

`python3 -B -m examples.completion_probe legacy` 走现有接纳与签发流程，核对 A、B 的 V1 计量内容及空账。`python3 -B -m examples.completion_probe completion` 在接通新入口后运行补载工单。它先发行和实收，再关闭站库办理，最后重开中心库按号领取并打印实得明细和出处。

`.pointwise-runtime.json` 沿用 `version` 为 `1`、`kind` 为 `cli` 的运行约定。`setup` 是命令参数数组的列表，`verify` 和 `demo` 各是一条命令的参数数组。完成后让 `verify` 运行完整原回归并核对补载工单，让 `demo` 显示断源签发后重开实领的报告。核验失败以非零状态退出。

from analysis.cycles import completion_cycle_rows
from reports.assignments import MaintenanceRow
from reports.completion_select import CompletionInputs


def reconcile_completion(inputs: CompletionInputs) -> tuple[MaintenanceRow, ...]:
    certificate = inputs.certificate
    raw_rows = completion_cycle_rows(
        inputs.prefix.load.start,
        certificate.reversals,
        inputs.peak,
        inputs.end,
    )
    return tuple(MaintenanceRow(owner, span, count) for owner, span, count in raw_rows)

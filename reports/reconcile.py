from reports.assignments import MaintenanceRow, aggregate_assignments
from reports.select import ReportInputs


def reconcile(inputs: ReportInputs) -> tuple[MaintenanceRow, ...]:
    start = inputs.prefix.load.start
    # Bands own their right endpoint. The last bound is the exclusive domain end.
    for band in inputs.certificate.bands:
        if start <= band.upper:
            return aggregate_assignments(MaintenanceRow(*row) for row in band.rows)
    raise ValueError('certificate response does not cover the selected start')

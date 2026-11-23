import json
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.issue import initialize_issuance, issue
from analysis.station_review import review_frozen_revision
from handoff.corrections import register
from intake.accept import receive
from intake.desk_store import open_desk
from records.freeze import record
from records.source_store import open_source
from reports.history import StoredReport, read
from reports.publish import publish


def _read_example(name: str):
    return json.loads(Path(__file__).with_name(name).read_text(encoding='utf-8'))


def _report_view(name: str, report: StoredReport) -> dict:
    return {
        'name': name,
        'report_id': report.report_id,
        'run_id': report.prefix.run_id,
        'prefix_id': report.prefix.prefix_id,
        'corrects': report.prefix.corrects,
        'start_kn': str(report.prefix.load.start),
        'seam_kn': str(report.rear_seam),
        'receipt_id': report.receipt.receipt_id,
        'revision_id': report.receipt.revision_id,
        'assignments': [
            {'shift': row.owner, 'range_kn': str(row.span), 'count': row.count}
            for row in report.rows
        ],
    }


def main() -> None:
    rear = _read_example('rear.json')
    prefixes = _read_example('prefixes.json')
    with TemporaryDirectory(prefix='strip-ledger-demo-') as directory:
        source_path = Path(directory) / 'station.sqlite'
        desk_path = Path(directory) / 'desk.sqlite'
        with closing(open_desk(desk_path)) as desk:
            with closing(open_source(source_path)) as source:
                initialize_issuance(source)
                revision = record(source, rear['run_id'], rear['seam'], rear['samples'])
                review = review_frozen_revision(source, revision.revision_id)
                receipt = receive(desk, issue(source, revision.revision_id))
            prefix_numbers = {}
            report_numbers = {}
            for entry in prefixes:
                name = entry['name']
                original = prefix_numbers[entry['corrects']] if 'corrects' in entry else None
                number = register(desk, rear['run_id'], entry['start'], rear['seam'], corrects=original)
                prefix_numbers[name] = number
                report_numbers[name] = publish(desk, number, receipt)
        with closing(open_desk(desk_path)) as desk:
            reports = [_report_view(name, read(desk, number)) for name, number in report_numbers.items()]
    print(json.dumps({
        'station_cycles': [{'range_kn': str(span), 'count': count} for span, count in review.summary.rows],
        'reports': reports,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()

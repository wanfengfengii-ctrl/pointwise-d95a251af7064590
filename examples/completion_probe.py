import argparse
import json
from contextlib import closing
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.certificates import decode_certificate
from analysis.issue import initialize_issuance, issue
from handoff.corrections import register
from handoff.ledger import get_prefix
from intake.accept import receive
from intake.archive import get_original
from intake.desk_store import open_desk
from intake.receipts import get_receipt
from records.freeze import record
from records.source_store import open_source
from reports.history import read
from reports.publish import publish


RUN = "completion-example"
SEAM = 6
REAR = {"A": (6, 2), "B": (6, 1, 5, 2), "C": (6, 4, 5, 2)}
CASES = (
    ("A", 0, 5, 0, (("rear", "3", 1),)),
    ("B", 0, 5, 0, (("rear", "3", 1), ("rear", "4", 1))),
    ("B", 0, 5, 1, (("rear", "3", 1), ("rear", "4", 1))),
    ("B", 0, 5, "3/2", (("rear", "3", 1),)),
    ("A", 0, 5, 2, (("rear", "3", 1),)),
    ("A", 0, 5, "9/4", ()),
    ("B", 0, 5, "9/4", (("rear", "3", 1),)),
    ("A", 0, "9/2", 0, (("rear", "5/2", 1),)),
    ("B", 0, "9/2", 0, (("rear", "5/2", 1), ("rear", "4", 1))),
    ("A", 0, 6, 0, (("front", "4", 1),)),
    ("A", 4, 6, 0, (("rear", "4", 1),)),
    ("C", 0, "5/2", 0, (("rear", "1/2", 1), ("rear", "1", 1))),
    ("C", 0, 3, 0, (("rear", "1", 2),)),
    ("C", 0, "7/2", 0, (("rear", "1", 1), ("rear", "3/2", 1))),
)


def capture(source, desk, labels, issue_piece, receive_piece):
    initialize_issuance(source)
    receipts = {}
    first_revision = None
    for label in labels:
        revision = record(source, RUN, SEAM, enumerate(REAR[label], 1), corrects=first_revision)
        if first_revision is None:
            first_revision = revision.revision_id
        piece = issue_piece(source, revision.revision_id)
        assert issue_piece(source, revision.revision_id) == piece, label
        number = receive_piece(desk, piece)
        assert get_original(desk, number) == piece.body, label
        receipts[label] = number, piece
    return receipts


def bill(report):
    return tuple((row.owner, str(row.span), row.count) for row in report.rows)


def legacy():
    with closing(open_desk(":memory:")) as desk:
        with closing(open_source(":memory:")) as source:
            receipts = capture(source, desk, ("A", "B"), issue, receive)
        prefix = register(desk, RUN, 0, SEAM)
        evidence = []
        reports = []
        for label, (number, piece) in receipts.items():
            cert = decode_certificate(piece.body)
            evidence.append((cert.seam, cert.station_rows, cert.bands))
            report = read(desk, publish(desk, prefix, number))
            assert report.receipt.receipt_id == number and not report.rows, label
            reports.append({"case": label, "revision_id": piece.revision_id,
                            "receipt_id": number, "rows": bill(report)})
        assert evidence[0] == evidence[1], evidence
    print(json.dumps({"mode": "legacy", "reports": reports}, ensure_ascii=False))


def completion_view(report):
    return {
        "report_id": report.report_id,
        "run_id": report.prefix.run_id,
        "prefix_id": report.prefix.prefix_id,
        "start": str(report.prefix.load.start),
        "seam": str(report.rear_seam),
        "receipt_id": report.receipt.receipt_id,
        "certificate_id": report.receipt.certificate_id,
        "revision_id": report.receipt.revision_id,
        "body_sha256": report.receipt.body_sha256,
        "peak": str(report.peak),
        "end": str(report.end),
        "rows": bill(report),
    }


def completion():
    from analysis.issue import issue_completion
    from intake.accept import receive_completion
    from reports.history import read_completion
    from reports.publish import publish_completion

    with TemporaryDirectory(prefix="strip-completion-") as directory:
        desk_path = Path(directory) / "desk.sqlite"
        source_path = Path(directory) / "source.sqlite"
        saved = []
        with closing(open_desk(desk_path)) as desk:
            with closing(open_source(source_path)) as source:
                receipts = capture(source, desk, REAR, issue_completion, receive_completion)
            for label, start, peak, end, expected in CASES:
                receipt, piece = receipts[label]
                prefix = register(desk, RUN, start, SEAM)
                number = publish_completion(desk, prefix, receipt, peak, end)
                report = read_completion(desk, number)
                assert report.report_id == number and report.prefix == get_prefix(desk, prefix)
                assert report.receipt == get_receipt(desk, receipt) and report.receipt.version == 2
                assert report.receipt.body_sha256 == piece.body_sha256 and report.rear_seam == SEAM
                assert (report.peak, report.end) == (Fraction(peak), Fraction(end))
                assert bill(report) == expected, (label, start, peak, end, bill(report), expected)
                saved.append((label, number, completion_view(report)))
        reports = []
        with closing(open_desk(desk_path)) as desk:
            for label, number, view in saved:
                reopened = completion_view(read_completion(desk, number))
                assert reopened == view, number
                reports.append({"case": label, **reopened})
    print(json.dumps({"mode": "completion", "reports": reports}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Run the strip completion work orders")
    parser.add_argument("mode", choices=("legacy", "completion"))
    if parser.parse_args().mode == "legacy":
        legacy()
    else:
        completion()


if __name__ == "__main__":
    main()

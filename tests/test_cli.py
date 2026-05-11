"""Tests for the CLI entry point."""

from niche_radar.__main__ import build_parser


def test_parser_commands():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_parser_collect_source():
    parser = build_parser()
    args = parser.parse_args(["collect", "--source", "reddit"])
    assert args.command == "collect"
    assert args.source == "reddit"


def test_parser_report_format():
    parser = build_parser()
    args = parser.parse_args(["report", "--format", "json"])
    assert args.command == "report"
    assert args.format == "json"


def test_parser_dry_run():
    parser = build_parser()
    args = parser.parse_args(["--dry-run", "collect"])
    assert args.dry_run is True


def test_parser_no_command():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None

#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

# Support direct execution from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cymatic_engine.corpus.real_corpus_runner import run_corpus


def cli_exit_code(status: str) -> int:
    """Only a complete PASS is a successful corpus-run exit."""
    return 0 if status == "PASS" else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args(argv)

    report = run_corpus(args.manifest, args.output_dir, args.device)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return cli_exit_code(report["status"])


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""A blind-approval scoreboard is not reused as a completed review (TauCetiReview#195).

CI's merge labeller stopped counting an approving board whose rubric row says the judge could not
inspect the workspace. The CLI hands the engine the PR's newest completed board, and the engine used
to answer "UNCHANGED: published review already completed" from it, so such a PR could never get the
sighted re-review CI now needs. The CLI now marks such a board `blind` and the engine re-reviews it.
Its copy of the blind-row test must agree with merge_from_scoreboard's; this pins them together.
Dependency-free: run with `python tests/test_blind_handoff.py`.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "runner"))
import cli  # noqa: E402
import merge_from_scoreboard as mfs  # noqa: E402
from review import can_reuse_completed_review  # noqa: E402

BLIND = (HERE / "fixtures/blind_approval_scoreboard.md").read_text()
META = json.loads(re.findall(r"<!--tauceti-meta:v1 (.*?)-->", BLIND, re.S)[-1])
HEAD = META["head_sha"]
fails = 0


def check(name, cond):
    global fails
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}")
    fails += not cond


for name in ("TABLE_ROW_RE", "BLIND_ROW_RE"):
    check(f"cli.{name} matches merge_from_scoreboard", getattr(cli, name).pattern == getattr(mfs, name).pattern
          and getattr(cli, name).flags == getattr(mfs, name).flags)
check("BLIND_RUBRICS are the default rubrics", cli.BLIND_RUBRICS == set(mfs.DEFAULT_RUBRICS))
check("the labeller calls the fixture a blind approval", mfs.is_blind_approval({"body": BLIND}, META))

board = cli.latest_scoreboard([{"id": 1, "user": {"login": "r"}, "updated_at": "t", "body": BLIND}])
check("the CLI marks it blind", board.get("blind") is True)
check("the engine does not reuse it", not can_reuse_completed_review(board, HEAD, list(META["states"]), {}, {}))

sighted = {**board}
sighted.pop("blind")
check("the same board, sighted, is still reused",
      can_reuse_completed_review(sighted, HEAD, list(META["states"]), {}, {}))

states = {**META["states"], "correctness": "blocking_request"}
body = BLIND.replace(re.findall(r"<!--tauceti-meta:v1 .*?-->", BLIND, re.S)[-1],
                     "<!--tauceti-meta:v1 " + json.dumps({**META, "states": states}) + "-->")
board = cli.latest_scoreboard([{"id": 2, "user": {"login": "r"}, "updated_at": "t", "body": body}])
check("a blind board that blocks is not marked", "blind" not in board)

print("PASS" if not fails else f"FAIL ({fails})")
sys.exit(1 if fails else 0)

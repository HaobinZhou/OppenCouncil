"""Opt-in isolated Chromium acceptance against real v5 project files and HTTP."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from test_assets_v5 import SVG
from test_site_v5 import site, work  # noqa: F401
from test_workflow_v5 import approve, prepare, save, stage

from oppencouncil.assets import freeze_images, table_blocks


@pytest.mark.skipif(not os.getenv("OPPENCOUNCIL_PLAYWRIGHT"), reason="Optional isolated browser acceptance")
def test_v5_browser_edit_feedback_reconfirmation_and_widths(site, tmp_path):  # noqa: F811
    service, server, identity, cookie = site
    project = service.store.project
    (project / "Explore").mkdir()
    original = project / "Explore/synthetic.svg"
    original.write_bytes(SVG)
    image = freeze_images(project, "![模拟数据，仅示意](Explore/synthetic.svg)")
    table = {
        "schema_version": 1,
        "id": "demo",
        "title": "模拟基线表",
        "simulated": True,
        "columns": [{"id": "a", "label": "方案 A"}, {"id": "b", "label": "方案 B"}],
        "headers": [
            {
                "id": "group",
                "label": "治疗组",
                "children": [
                    {"id": "ha", "label": "方案 A", "column_id": "a"},
                    {"id": "hb", "label": "方案 B", "column_id": "b"},
                ],
            }
        ],
        "rows": [
            {"id": "age", "label": "年龄", "cells": {}},
            {"id": "mean", "parent_id": "age", "label": "均值", "cells": {"a": "62", "b": "63"}},
        ],
        "footnotes": [
            {
                "id": "note",
                "text": "单位：岁",
                "refs": [{"row_id": "mean", "column_id": "a"}, {"column_id": "a"}],
            }
        ],
    }
    text = "原有引言\n\n```table\n" + json.dumps(table, ensure_ascii=False) + "\n```\n\n" + image
    prepare(service, text)
    approve(service)
    formal = service.read("F-000001")["current"]
    save(service, {"definition": {"operation": "definition_begin"}}, "user")
    save(service, {"phase": stage()})
    service.investigation(
        {"title": "核查上游排除", "why": "已观察到差异", "dedupe_key": "browser-check"},
        request_id="browser-i",
    )
    service.add(
        [{"title": "依据重新确认", "why": "Changed evidence"}], request_id="browser-reconfirm", actor="codex"
    )
    prepare(service, "原正式口径保持不变", "F-000002")
    approve(service, "F-000002")
    save(
        service,
        {
            "id": "F-000002",
            "evidence_impact": {"classification": "weakened", "reason": "新测量影响原依据"},
            "review_basis": {"claims": [], "summary": "已完成定向核查"},
        },
    )
    save(service, {"id": "F-000002", "phase": stage()})
    original.unlink()  # Frozen images must survive removal of the experimental source.
    config = tmp_path / "browser-v5.json"
    config.write_text(
        json.dumps(
            {
                "url": f"http://127.0.0.1:{server.server_port}/projects/{identity}/freeze",
                "cookie": cookie,
                "output": str(tmp_path),
            }
        )
    )
    result = subprocess.run(
        [
            "node",
            str(Path(__file__).with_name("browser_v5.cjs")),
            os.environ["OPPENCOUNCIL_PLAYWRIGHT"],
            str(config),
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["widths"] == [1440, 1920, 2560, 390]
    updated = service.read("F-000001")
    assert updated["current"] == formal
    assert updated["human_pending"]
    assert "人类修改标题" in updated["candidate"]["text"]
    edited_table = json.loads(next(table_blocks(updated["candidate"]["text"])))
    assert edited_table["columns"][0] == {
        "id": "a",
        "label": "推荐方案",
        "unit": "岁",
        "format": "均值 (SD)",
        "align": "right",
    }
    assert [row["id"] for row in edited_table["rows"]] == ["row-1", "mean"]
    assert edited_table["footnotes"] == [{"id": "note-1", "text": "人类补充脚注", "refs": []}]
    assert service.store.read_question("F-000001")["definition"]["draft"]["updated_by"] == "user"
    assert service.read("I-000001")["human_pending"]
    reconfirmed = service.read("F-000002")["current"]
    assert reconfirmed["number"] == 1 and len(reconfirmed["reconfirmations"]) == 1
    assert reconfirmed["text"] == "原正式口径保持不变"

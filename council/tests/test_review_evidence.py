"""Evidence is bounded by the chosen option, exact versions and authenticated project."""

import copy

import pytest
from test_site_v5 import request, site, work  # noqa: F401
from test_workflow_v5 import evidence_records

from oppencouncil.review_evidence import review_evidence
from oppencouncil.store import FreezeError


def seed_evidence(service):
    records = evidence_records()
    first, claim = records
    extra = []
    for number in (2, 3, 4):
        source = copy.deepcopy(first)
        source["path"] = first["path"].replace("S-000001", f"S-{number:06d}")
        source["value"].update(id=f"S-{number:06d}", citation=f"Source {number}")
        extra.append(source)
    claim["value"]["sources"] = [extra[0]["path"], first["path"]]
    claim["value"]["counter_sources"] = [extra[1]["path"]]
    other = copy.deepcopy(claim)
    other["path"] = claim["path"].replace("E-000001", "E-000002")
    other["value"].update(
        id="E-000002", claim="Only option B", sources=[extra[2]["path"]], counter_sources=[]
    )
    service.commit_work(
        {
            "read_set": {"F-000001": service.read("F-000001")["revision"]},
            "evidence": [first, *extra, claim, other],
            "changes": [{"id": "F-000001", "review_basis": {"claims": [claim["path"]], "summary": "Checked"},
                         "evidence_refs": [other["path"]]}],
        },
        request_id="evidence-fixture",
    )
    value = {"title": "Alternatives", "purpose": "Compare", "member_ids": ["F-000001"], "options": []}
    for label, refs in [("A", [claim["path"]]), ("B", [other["path"]]), ("No evidence", [])]:
        value["options"].append({"label": label, "rules": {"F-000001": label}, "consequences": "Effect",
                                 "tradeoffs": "Conditions", "evidence_refs": refs})
    value["options"].append({k: v for k, v in value["options"][-1].items() if k != "evidence_refs"})
    value["options"][-1]["label"] = "Legacy unbound option"
    group = service.store.change_group(None, "create", value, expected_revision=0,
                                       request_id="group-evidence", actor="codex")
    return first, extra, claim, other, group


def test_choices_resolve_only_their_bound_versions_and_read_does_not_write(work):  # noqa: F811
    first, extra, claim, other, group = seed_evidence(work)
    before = {p: p.read_bytes() for p in work.store.root.rglob("*.json")}
    a = review_evidence(work.store, group["id"], option=0)
    b = review_evidence(work.store, group["id"], option=1)
    assert [c["path"] for c in a["claims"]] == [claim["path"]]
    assert [s["path"] for s in a["sources"]] == [extra[0]["path"], first["path"], extra[1]["path"]]
    assert [c["path"] for c in b["claims"]] == [other["path"]]
    assert [s["path"] for s in b["sources"]] == [extra[2]["path"]]
    assert not set(s["path"] for s in a["sources"]) & set(s["path"] for s in b["sources"])
    for index in (2, 3):
        empty = review_evidence(work.store, group["id"], option=index)
        assert empty["sources"] == empty["claims"] == []
        assert empty["bound"] is (index == 2)
    question = review_evidence(work.store, "F-000001")
    assert question["claims"] == a["claims"]  # Do not merge historical/general evidence_refs into a basis.
    assert before == {p: p.read_bytes() for p in work.store.root.rglob("*.json")}


def test_new_source_version_never_substitutes_for_the_version_under_review(work):  # noqa: F811
    first, _, _, _, group = seed_evidence(work)
    newer = evidence_records(version=2)[0]
    newer["value"]["citation"] = "New version not used by A"
    work.commit_work({"read_set": {}, "changes": [], "evidence": [newer]}, request_id="new-version")
    read = review_evidence(work.store, group["id"], option=0)
    assert next(s for s in read["sources"] if s["id"] == "S-000001")["version"] == 1
    (work.store.root / first["path"]).unlink()
    missing = review_evidence(work.store, group["id"], option=0)
    assert first["path"] in missing["unavailable"]
    assert all(s["version"] == 1 for s in missing["sources"])


@pytest.mark.parametrize("option", [None, -1, 99, True, "0"])
def test_group_requires_one_valid_option(work, option):  # noqa: F811
    *_, group = seed_evidence(work)
    with pytest.raises(FreezeError, match="Select one existing option"):
        review_evidence(work.store, group["id"], option=option)


@pytest.mark.parametrize("refs", [["../project.md"], ["evidence/sources/S-999999/r000001.json"],
                                  ["evidence/submissions/X-bad.json"], "all"])
def test_option_binding_rejects_missing_or_non_versioned_evidence_without_writing(work, refs):  # noqa: F811
    *_, group = seed_evidence(work)
    value = {k: copy.deepcopy(group[k]) for k in ("title", "purpose", "member_ids", "options")}
    value["options"][0]["evidence_refs"] = refs
    before = work.store.snapshot()
    with pytest.raises(FreezeError):
        work.store.change_group(group["id"], "update", value, expected_revision=group["revision"],
                                actor="codex", request_id="bad-binding")
    assert work.store.snapshot() == before


def test_review_evidence_http_is_authenticated_scoped_and_read_only(site):  # noqa: F811
    service, server, identity, cookie = site
    *_, group = seed_evidence(service)
    path = f"/api/projects/{identity}/review-evidence/{group['id']}"
    assert request(server, path + "?option=0")[0] == 401
    assert request(server, "/review-evidence.js")[0] == 401
    assert request(server, "/review-evidence.js", cookie)[0] == 200
    before = service.store.snapshot()
    assert request(server, path, cookie)[0] == 400
    assert request(server, path + "?option=0", cookie)[1]["title"] == "A"
    assert request(server, path + "?option=1", cookie)[1]["title"] == "B"
    assert request(server, path + "?option=0&option=1", cookie)[0] == 400
    assert request(server, path + "?path=../project.md", cookie)[0] == 400
    assert request(server, path.replace(identity, "0" * 20) + "?option=0", cookie)[0] == 404
    assert request(server, path.replace(group["id"], "F-000001") + "?option=0", cookie)[0] == 400
    assert service.store.snapshot() == before

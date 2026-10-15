"""Read only the exact evidence versions attached to one displayed review choice."""

from __future__ import annotations

import copy

from .store import FreezeError
from .workstore import WorkStore


def review_evidence(store, identifier, *, option=None):
    work = WorkStore(store)
    with store.locked():
        questions, groups, investigations = work.records()
        record = work.locate(identifier, questions, groups, investigations)
        if identifier.startswith("B-"):
            options = record.get("options", [])
            if type(option) is not int or not 0 <= option < len(options):
                raise FreezeError("Select one existing option to read its evidence")
            choice = options[option]
            refs = choice.get("evidence_refs", [])
            bound = "evidence_refs" in choice
            title = choice["label"]
        elif identifier.startswith("F-") and option is None:
            basis = record.get("review_basis")
            refs = basis["claims"] if basis is not None else record.get("evidence_refs", [])
            bound = basis is not None or bool(refs)
            title = record["title"]
        else:
            raise FreezeError("Evidence review requires a question or one group option")

        claims, sources, unavailable = [], [], []
        seen_claims, seen_sources = set(), set()

        def read(path):
            try:
                return work.read_json(path)
            except (FreezeError, OSError, ValueError):
                unavailable.append(path)
                return None

        def source(path):
            if path in seen_sources:
                return
            seen_sources.add(path)
            value = read(path)
            if value is not None:
                sources.append({"path": path, **copy.deepcopy(value)})

        for path in refs:
            if path.startswith("evidence/sources/"):
                source(path)
            elif path.startswith("evidence/claims/") and path not in seen_claims:
                seen_claims.add(path)
                value = read(path)
                if value is None:
                    continue
                claims.append({"path": path, **copy.deepcopy(value)})
                for source_path in [*value["sources"], *value.get("counter_sources", [])]:
                    source(source_path)
            # An external submission is not an appraised source or judgment.
        return {
            "id": identifier,
            "revision": record["revision"],
            "option": option,
            "title": title,
            "bound": bound,
            "references": list(refs),
            "claims": claims,
            "sources": sources,
            "unavailable": list(dict.fromkeys(unavailable)),
        }

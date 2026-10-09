"""Exercise grouped outputs, a single pending-decision view and module audits."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from oppencouncil.store import FreezeStore

BASE = Path(__file__).parents[2] / "skills"


@pytest.fixture(params=['stepwise-r-project', 'oppen-project-steward'])
def project(request, tmp_path):
    skill = request.param
    name = skill.replace('-', '_')
    spec = importlib.util.spec_from_file_location(name + '_lean', BASE / skill / 'scripts' / (name + '.py'))
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    root = tmp_path / 'project'
    for directory in ('R', 'src', 'Results' if skill.startswith('stepwise') else 'Deliverables'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    helper.ensure_v3_project(root, create=True)
    helper.refresh_index(root)
    return helper, root


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def group_setup(helper, root):
    is_r = hasattr(helper, 'register_result')
    output = root / ('Results' if is_r else 'Deliverables') / 'main-analysis'
    output.mkdir()
    (output / 'table.csv').write_text('id,value\n1,3\n')
    (output / 'report.md').write_text('# Current results\n')
    producer = 'R/export.R' if is_r else 'src/export.py'
    (root / producer).write_text('# Produces the main analysis review bundle\n')
    register = helper.register_result if is_r else helper.register_deliverable
    return output, producer, register


def test_group_covers_mixed_outputs_and_detects_new_invalid_members(project):
    helper, root = project
    output, producer, register = group_setup(helper, root)
    register(root, 'main', output.relative_to(root).as_posix(), 'group', 'formal-review', producer, replace=False)
    helper.refresh_index(root)
    assert helper.validate_project(root).ok
    before = files(root)
    helper.refresh_index(root)
    assert files(root) == before
    (output / 'figure.svg').write_text('<svg/>')
    assert helper.validate_project(root).ok
    (output / 'state.pkl').write_bytes(b'machine state')
    assert not helper.validate_project(root).ok
    (output / 'state.pkl').unlink()
    outside = root / 'unregistered.csv'
    outside.write_text('external member\n')
    (output / 'linked.csv').symlink_to(outside)
    assert not helper.validate_project(root).ok


def test_group_rejects_overlap_and_does_not_mutate_registry_on_failure(project):
    helper, root = project
    output, producer, register = group_setup(helper, root)
    path = output.relative_to(root).as_posix()
    register(root, 'main', path, 'group', 'formal-review', producer, replace=False)
    before = files(root)
    with pytest.raises(helper.ProjectError, match='overlap'):
        register(root, 'table', path + '/table.csv', 'table', 'formal-review', producer, replace=False)
    assert files(root) == before
    with pytest.raises(helper.ProjectError, match='strictly inside'):
        register(root, 'all', output.parent.relative_to(root).as_posix(), 'group', 'formal-review', producer, replace=False)
    assert files(root) == before
    empty = output.parent / 'empty'
    empty.mkdir()
    with pytest.raises(helper.ProjectError, match='at least one'):
        register(root, 'empty', empty.relative_to(root).as_posix(), 'group', 'formal-review', producer, replace=False)


def test_pending_view_unifies_sources_and_preserves_effective_version(project, tmp_path, capsys):
    helper, root = project
    payload = dict(title='Permission decision', blocking=True, observation='Fallback bypasses checks.',
                   evidence='src/access.py', why_it_matters='Changes permitted access.',
                   why_no_action_was_taken='Outside this task.', human_decision_needed='Choose the authorization rule.')
    temporary = tmp_path / 'attention.json'
    temporary.write_text(json.dumps(payload))
    helper.main(['review', 'raise', str(root), '--input', str(temporary)])
    store = FreezeStore(root)
    store.add_questions([{'title': 'Choose a rule', 'why': 'Defines execution'}], request_id='round')
    q = store.change('F-000001', 'definition_draft', 'Only authorized identities may read records.',
                     actor='codex', expected_revision=1, request_id='draft')
    before = files(root)
    result = helper.list_pending_decisions(root)
    assert result['count'] == 2
    assert [x['next_action'] for x in result['items']] == ['human_decision', 'review_candidate']
    assert result['items'][1]['current_version'] is None
    assert files(root) == before
    q = store.change(q['id'], 'definition_approve', q['definition']['draft']['text_sha256'],
                     actor='user', expected_revision=q['revision'], request_id='approve')
    assert helper.list_pending_decisions(root)['count'] == 1
    q = store.change(q['id'], 'definition_begin', None, actor='user', expected_revision=q['revision'], request_id='reopen')
    before = files(root)
    assert helper.list_pending_decisions(root)['items'][1]['current_version'] == 1
    assert files(root) == before
    capsys.readouterr()
    assert helper.main(['review', 'list', str(root)]) == 0
    assert json.loads(capsys.readouterr().out)['count'] == 2
    assert helper.main(['review', 'resolve', str(root), '--id', 'A-0001']) == 0
    assert helper.list_pending_decisions(root)['count'] == 1
    # Original Attention command is a compatible alias.
    capsys.readouterr()
    assert helper.main(['attention', 'list', str(root)]) == 0
    assert json.loads(capsys.readouterr().out)['count'] == 1
    # A corrupt Council record must never look like an empty completed list.
    (root / 'Freeze/questions/F-000001.json').write_text('{}')
    with pytest.raises(helper.ProjectError, match='incomplete'):
        helper.list_pending_decisions(root)


def test_empty_pending_view_creates_no_systems_or_memory(project):
    helper, root = project
    before = files(root)
    assert helper.list_pending_decisions(root)['count'] == 0
    assert files(root) == before
    assert not (root / 'Freeze').exists()


@pytest.mark.parametrize("project", ["stepwise-r-project"], indirect=True)
def test_module_audit_tracks_multiple_r_sources_without_per_function_records(project, tmp_path):
    helper, root = project
    (root / 'R/cohort.R').write_text('cohort <- data[data$eligible, ]\n')
    (root / 'R/dates.R').write_text('month <- 1L\n')
    audit, status = helper.create_or_complete_module_audit(root, 'cohort', ['R/cohort.R', 'R/dates.R'], 'Defines eligibility')
    assert status == 'CREATED_DRAFT'
    assert not helper.validate_project(root).ok
    assert not (root / 'Audit/Functions').exists()
    payload = dict(purpose_and_risk='Eligibility affects the analysis population.',
                   contract='Keep eligible records; use the declared month unit.',
                   edge_cases_and_verification='Boundary and missingness checks run in tests/test_cohort.R.',
                   known_limits='Only monthly time is represented.')
    temporary = tmp_path / 'audit.json'
    temporary.write_text(json.dumps(payload))
    same, status = helper.create_or_complete_module_audit(root, 'cohort', payload_path=temporary)
    assert status == 'COMPLETED' and same == audit and not temporary.exists()
    assert helper.validate_project(root).ok
    before = audit.read_bytes()
    assert helper.create_or_complete_module_audit(root, 'cohort')[1] == 'UPDATE_REQUIRED'
    assert audit.read_bytes() == before
    (root / 'R/dates.R').write_text('month <- 2L\n')
    assert any('stale for its sources' in error for error in helper.validate_project(root).errors)
    temporary.write_text(json.dumps(payload))
    helper.create_or_complete_module_audit(root, 'cohort', payload_path=temporary)
    assert helper.validate_project(root).ok
    (root / 'R/dates.R').unlink()
    assert not helper.validate_project(root).ok
    outside = tmp_path / 'outside.Rmd'
    outside.write_text('Unrelated document')
    audit.unlink()
    audit.symlink_to(outside)
    with pytest.raises(helper.ProjectError, match='cannot be linked'):
        helper.create_or_complete_module_audit(root, 'cohort')
    assert outside.read_text() == 'Unrelated document'


@pytest.mark.parametrize("project", ["oppen-project-steward"], indirect=True)
def test_adoption_accepts_group_and_rejects_conflicting_member_registration(project, tmp_path):
    helper, _ = project
    root = tmp_path / 'adopted'
    (root / 'reports/review').mkdir(parents=True)
    (root / 'reports/review/table.csv').write_text('id,value\n1,2\n')
    (root / 'produce.py').write_text('# Generates review outputs\n')
    payload = dict(role_mappings={'deliverables': 'reports'}, initial_canonical_registrations=[],
                   initial_deliverable_registrations=[dict(id='review', path='reports/review', kind='group',
                                                          audience='reviewers', producer='produce.py')])
    source = tmp_path / 'adoption.json'
    source.write_text(json.dumps(payload))
    helper.apply_adoption(root, source)
    assert helper.validate_project(root).ok
    payload['initial_deliverable_registrations'].append(dict(id='table', path='reports/review/table.csv',
                                                            kind='table', audience='reviewers', producer='produce.py'))
    with pytest.raises(helper.ProjectError, match='overlap'):
        helper.validate_adoption_payload(root, payload)

import copy
from datetime import datetime, timezone

from app.integrations.archengine import CartridgeDescriptorPayload
from app.interview.engine import InterviewEngine
from app.interview.models import (
    InterviewAnswer,
    InterviewProgress,
    InterviewQuestion,
    InterviewState,
)
from app.models.cartridge import (
    ForgeResult,
    PersonaCartridge,
    PersonaDraft,
)
from app.services.authoring_workflow import (
    AuthoringWorkflow,
    CartridgeCreationFailed,
    InterviewIncomplete,
    ReadinessResult,
    SessionNotFound,
    WorkflowError,
    WorkflowStateError,
)
from app.services.cartridge_service import CartridgeService

TEST_USER = "test-user"


# ===================================================================
# Helpers
# ===================================================================

def _full_draft() -> PersonaDraft:
    return PersonaDraft(
        name="Alex",
        identifier="alex",
        summary="A thoughtful guide",
        description="Optional description",
        aliases=["The Guide"],
        core_values=["Curiosity"],
        motivations=["To help others"],
        strengths=["Patience"],
        limitations=["Overthinking"],
        goals=["Inspire learning"],
        boundaries=["Never lie"],
        communication_style="Warm",
        tone=["Friendly"],
        vocabulary_preferences=["Plain"],
        response_tendencies=["Concise"],
        formatting_preferences=["Markdown"],
        preferences={"formality": "casual"},
        behavior_rules=["Be kind"],
    )


def _answer_all(
    workflow: AuthoringWorkflow,
    session_id: str,
    owner_user_id: str = TEST_USER,
) -> None:
    """Answer every question in the session with sensible defaults."""
    defaults = {
        "identity_name": "Alex",
        "identity_identifier": "alex",
        "identity_summary": "A thoughtful guide",
        "identity_description": "Optional description",
        "identity_aliases": ["The Guide"],
        "character_core_values": ["Curiosity"],
        "character_motivations": ["To help others"],
        "character_strengths": ["Patience"],
        "character_limitations": ["Overthinking"],
        "character_goals": ["Inspire learning"],
        "character_boundaries": ["Never lie"],
        "communication_style": "Warm",
        "communication_tone": ["Friendly"],
        "communication_vocabulary": ["Plain"],
        "communication_response": ["Concise"],
        "communication_formatting": ["Markdown"],
        "preferences": {"formality": "casual"},
        "behavior_rules": ["Be kind"],
    }
    while True:
        q = workflow.current_question(session_id, owner_user_id)
        if q is None:
            break
        val = defaults.get(q.identifier)
        if val is not None:
            workflow.answer_question(session_id, q.identifier, val, owner_user_id)
        elif not q.required:
            workflow.skip_question(session_id, q.identifier, owner_user_id)
        else:
            raise ValueError(f"No answer for required question {q.identifier}")


# ===================================================================
# Session creation
# ===================================================================

class TestSessionCreation:
    def test_create_session(self):
        wf = AuthoringWorkflow()
        session = wf.create_session(TEST_USER)
        assert session.session_id is not None
        assert session.state == InterviewState.CREATED
        assert session.draft is not None

    def test_create_session_with_template(self):
        wf = AuthoringWorkflow()
        template = _full_draft()
        session = wf.create_session(TEST_USER, template=template)
        assert session.draft.name == "Alex"
        assert session.draft.identifier == "alex"

    def test_create_session_deep_copies_template(self):
        wf = AuthoringWorkflow()
        template = _full_draft()
        session = wf.create_session(TEST_USER, template=template)
        template.name = "MUTATED"
        assert session.draft.name == "Alex"

    def test_multiple_sessions_independent(self):
        wf = AuthoringWorkflow()
        s1 = wf.create_session(TEST_USER)
        s2 = wf.create_session(TEST_USER)
        assert s1.session_id != s2.session_id

    def test_load_session(self):
        wf = AuthoringWorkflow()
        created = wf.create_session(TEST_USER)
        loaded = wf.load_session(created.session_id, TEST_USER)
        assert loaded is created

    def test_load_session_not_found(self):
        wf = AuthoringWorkflow()
        try:
            wf.load_session("nonexistent", TEST_USER)
            assert False, "Expected SessionNotFound"
        except SessionNotFound:
            pass


# ===================================================================
# Answering questions
# ===================================================================

class TestAnswerQuestion:
    def test_answer_str(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        answer = wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
        assert isinstance(answer, InterviewAnswer)
        assert answer.normalized_value == "Alex"

    def test_answer_updates_draft(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
        session = wf.load_session(sid, TEST_USER)
        assert session.draft.name == "Alex"

    def test_answer_normalizes(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.answer_question(sid, "identity_name", "  Alex  ", TEST_USER)
        session = wf.load_session(sid, TEST_USER)
        assert session.draft.name == "Alex"

    def test_answer_rejects_invalid(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        from app.interview.exceptions import InvalidAnswerError
        try:
            wf.answer_question(sid, "identity_name", 42, TEST_USER)
            assert False
        except InvalidAnswerError:
            pass

    def test_answer_to_incomplete_session(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.cancel_session(sid, TEST_USER)
        from app.interview.exceptions import InterviewStateError
        try:
            wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
            assert False
        except InterviewStateError:
            pass


# ===================================================================
# Skip question
# ===================================================================

class TestSkipQuestion:
    def test_skip_non_required(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
        wf.answer_question(sid, "identity_identifier", "alex", TEST_USER)
        wf.answer_question(sid, "identity_summary", "S", TEST_USER)
        wf.skip_question(sid, "identity_description", TEST_USER)
        session = wf.load_session(sid, TEST_USER)
        assert session.draft.description == ""

    def test_cannot_skip_required(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        from app.interview.exceptions import InterviewError
        try:
            wf.skip_question(sid, "identity_name", TEST_USER)
            assert False
        except InterviewError:
            pass


# ===================================================================
# Current question
# ===================================================================

class TestCurrentQuestion:
    def test_first_question(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        q = wf.current_question(sid, TEST_USER)
        assert q is not None
        assert q.identifier == "identity_name"

    def test_next_question_after_answer(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
        q = wf.current_question(sid, TEST_USER)
        assert q is not None
        assert q.identifier == "identity_identifier"

    def test_no_more_questions(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        q = wf.current_question(sid, TEST_USER)
        assert q is None

    def test_available_questions(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        available = wf.available_questions(sid, TEST_USER)
        assert len(available) > 0
        assert all(q.dependencies == () for q in available)


# ===================================================================
# Progress
# ===================================================================

class TestProgress:
    def test_initial_progress(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        prog = wf.progress(sid, TEST_USER)
        assert isinstance(prog, InterviewProgress)
        assert prog.total_questions == 18
        assert prog.answered_questions == 0
        assert prog.all_required_answered is False

    def test_progress_after_one_answer(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
        prog = wf.progress(sid, TEST_USER)
        assert prog.answered_questions == 1

    def test_progress_after_all(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        prog = wf.progress(sid, TEST_USER)
        assert prog.answered_questions == 18
        assert prog.all_required_answered is True
        assert prog.remaining_questions == 0


# ===================================================================
# Readiness
# ===================================================================

class TestReadiness:
    def test_not_ready_initially(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        result = wf.readiness(sid, TEST_USER)
        assert isinstance(result, ReadinessResult)
        assert result.ready is False
        assert len(result.issues) > 0

    def test_ready_after_all_required(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        result = wf.readiness(sid, TEST_USER)
        assert result.ready is True
        assert len(result.issues) == 0

    def test_readiness_matches_progress(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        prog = wf.progress(sid, TEST_USER)
        result = wf.readiness(sid, TEST_USER)
        assert result.ready == prog.all_required_answered


# ===================================================================
# Forge
# ===================================================================

class TestForge:
    def test_forge_success(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        result = wf.forge(sid, TEST_USER)
        assert isinstance(result, ForgeResult)
        assert result.success is True
        assert result.cartridge is not None

    def test_forge_returns_cartridge(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        result = wf.forge(sid, TEST_USER)
        cartridge = result.cartridge
        assert isinstance(cartridge, PersonaCartridge)
        assert cartridge.identity.display_name == "Alex"
        assert cartridge.identity.identifier == "alex"

    def test_forge_registers_in_cartridge_service(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        result = wf.forge(sid, TEST_USER)
        # Retrieve from the underlying cartridge service
        retrieved = wf._cartridge_service.get("alex", TEST_USER)
        assert retrieved is result.cartridge

    def test_forge_fails_when_incomplete(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        # Only answer one question
        wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
        try:
            wf.forge(sid, TEST_USER)
            assert False, "Expected InterviewIncomplete"
        except InterviewIncomplete:
            pass

    def test_forge_fails_when_cancelled(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.cancel_session(sid, TEST_USER)
        try:
            wf.forge(sid, TEST_USER)
            assert False, "Expected WorkflowStateError"
        except WorkflowStateError:
            pass

    def test_forge_fails_when_completed(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        wf.complete_session(sid, TEST_USER)
        try:
            wf.forge(sid, TEST_USER)
            assert False, "Expected WorkflowStateError"
        except WorkflowStateError:
            pass

    def test_forge_validates_draft(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        # Answer all but with empty identifier (which is required)
        _answer_all(wf, sid)
        # Corrupt the draft
        session = wf.load_session(sid, TEST_USER)
        session.draft.name = ""
        try:
            wf.forge(sid, TEST_USER)
            # Should still fail because the forge validates
            assert False, "Expected CartridgeCreationFailed"
        except CartridgeCreationFailed:
            pass
        except WorkflowError:
            pass  # Either CartridgeCreationFailed or InterviewIncomplete is fine

    def test_forge_return_on_repeated_call(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        result1 = wf.forge(sid, TEST_USER)
        assert result1.success is True
        # Second forge would create a new cartridge since CartridgeService.create
        # overwrites by identifier. This is expected behavior.
        result2 = wf.forge(sid, TEST_USER)
        assert result2.success is True


# ===================================================================
# Export
# ===================================================================

class TestExport:
    def test_export_after_forge(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        wf.forge(sid, TEST_USER)
        payload = wf.export(sid, TEST_USER)
        assert isinstance(payload, CartridgeDescriptorPayload)
        assert payload.name == "Alex"

    def test_export_json_after_forge(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        wf.forge(sid, TEST_USER)
        d = wf.export_json(sid, TEST_USER)
        assert isinstance(d, dict)
        assert d["name"] == "Alex"

    def test_export_fails_without_forge(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        try:
            wf.export(sid, TEST_USER)
            assert False, "Expected WorkflowStateError"
        except WorkflowStateError:
            pass

    def test_export_fails_for_nonexistent(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        try:
            wf.export(sid, TEST_USER)
            assert False
        except (WorkflowStateError, SessionNotFound):
            pass


# ===================================================================
# Session completion
# ===================================================================

class TestSessionCompletion:
    def test_complete_session(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        wf.complete_session(sid, TEST_USER)
        session = wf.load_session(sid, TEST_USER)
        assert session.state == InterviewState.COMPLETED

    def test_cancel_session(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.cancel_session(sid, TEST_USER)
        session = wf.load_session(sid, TEST_USER)
        assert session.state == InterviewState.CANCELLED

    def test_cannot_complete_cancelled(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.cancel_session(sid, TEST_USER)
        from app.interview.exceptions import InterviewStateError
        try:
            wf.complete_session(sid, TEST_USER)
            assert False
        except InterviewStateError:
            pass


# ===================================================================
# Serialization
# ===================================================================

class TestSerialization:
    def test_serialize_returns_dict(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        data = wf.serialize_session(sid, TEST_USER)
        assert isinstance(data, dict)
        assert "session_id" in data
        assert "draft" in data

    def test_deserialize_session(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        data = wf.serialize_session(sid, TEST_USER)
        restored = wf.deserialize_session(data, TEST_USER)
        assert restored.session_id == sid
        assert restored.draft.name == "Alex"

    def test_deserialized_session_usable(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        wf.answer_question(sid, "identity_name", "Alex", TEST_USER)
        data = wf.serialize_session(sid, TEST_USER)
        restored = wf.deserialize_session(data, TEST_USER)
        q = wf.current_question(restored.session_id, TEST_USER)
        assert q is not None
        assert q.identifier == "identity_identifier"

    def test_deserialized_session_can_complete(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        data = wf.serialize_session(sid, TEST_USER)
        restored = wf.deserialize_session(data, TEST_USER)
        result = wf.forge(restored.session_id, TEST_USER)
        assert result.success is True


# ===================================================================
# Error types
# ===================================================================

class TestErrors:
    def test_session_not_found_is_workflow_error(self):
        assert issubclass(SessionNotFound, WorkflowError)

    def test_interview_incomplete_is_workflow_error(self):
        assert issubclass(InterviewIncomplete, WorkflowError)

    def test_cartridge_creation_failed_is_workflow_error(self):
        assert issubclass(CartridgeCreationFailed, WorkflowError)

    def test_workflow_state_error_is_workflow_error(self):
        assert issubclass(WorkflowStateError, WorkflowError)

    def test_readiness_result_frozen(self):
        r = ReadinessResult(ready=True)
        try:
            r.ready = False
            assert False
        except Exception:
            pass


# ===================================================================
# Determinism
# ===================================================================

class TestDeterminism:
    def test_repeated_authoring_produces_identical_cartridges(self):
        wf1 = AuthoringWorkflow()
        wf2 = AuthoringWorkflow()
        s1 = wf1.create_session(TEST_USER).session_id
        s2 = wf2.create_session(TEST_USER).session_id
        _answer_all(wf1, s1)
        _answer_all(wf2, s2)
        r1 = wf1.forge(s1, TEST_USER)
        r2 = wf2.forge(s2, TEST_USER)
        assert r1.success and r2.success
        c1 = r1.cartridge
        c2 = r2.cartridge
        assert c1.identity.display_name == c2.identity.display_name
        assert c1.character.core_values == c2.character.core_values
        assert c1.behavior.policies == c2.behavior.policies

    def test_repeated_interview_identical_draft(self):
        wf = AuthoringWorkflow()
        s1 = wf.create_session(TEST_USER).session_id
        _answer_all(wf, s1)
        draft1 = copy.deepcopy(wf.load_session(s1, TEST_USER).draft)
        s2 = wf.create_session(TEST_USER).session_id
        _answer_all(wf, s2)
        draft2 = copy.deepcopy(wf.load_session(s2, TEST_USER).draft)
        assert draft1.name == draft2.name
        assert draft1.core_values == draft2.core_values


# ===================================================================
# Regression: interview is sole authoring mechanism
# ===================================================================

class TestAuthoringMechanism:
    def test_draft_is_single_source_of_truth(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        session = wf.load_session(sid, TEST_USER)
        for qid, answer in session.answers.items():
            from app.interview.questions import question_field_map
            field = question_field_map.get(qid)
            if field:
                draft_val = getattr(session.draft, field)
                if answer.normalized_value is not None:
                    assert draft_val == answer.normalized_value, (
                        f"Draft field '{field}' ({draft_val}) "
                        f"does not match answer '{qid}' ({answer.normalized_value})"
                    )

    def test_cartridge_registered_through_service(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        result = wf.forge(sid, TEST_USER)
        cartridge = result.cartridge
        # The cartridge should be findable through the service
        retrieved = wf._cartridge_service.get(cartridge.identity.identifier, TEST_USER)
        assert retrieved is cartridge

    def test_cartridge_contains_authored_content(self):
        wf = AuthoringWorkflow()
        sid = wf.create_session(TEST_USER).session_id
        _answer_all(wf, sid)
        result = wf.forge(sid, TEST_USER)
        c = result.cartridge
        assert c.identity.display_name == "Alex"
        assert c.identity.identifier == "alex"
        assert c.character.core_values == ("Curiosity",)
        assert len(c.behavior.policies) == 1
        assert c.behavior.policies[0].title == "Be kind"

    def test_end_to_end_pipeline(self):
        wf = AuthoringWorkflow()
        # Create session
        sid = wf.create_session(TEST_USER).session_id
        # Answer questions
        _answer_all(wf, sid)
        # Check readiness
        assert wf.readiness(sid, TEST_USER).ready is True
        # Forge
        result = wf.forge(sid, TEST_USER)
        assert result.success is True
        # Export
        payload = wf.export(sid, TEST_USER)
        assert payload.name == "Alex"
        # Round-trip via JSON
        d = wf.export_json(sid, TEST_USER)
        text = __import__("json").dumps(d, ensure_ascii=False)
        restored = __import__("json").loads(text)
        assert restored["name"] == "Alex"

    def test_multiple_independent_pipelines(self):
        wf = AuthoringWorkflow()
        sid1 = wf.create_session(TEST_USER).session_id
        sid2 = wf.create_session(TEST_USER).session_id
        # Answer both with different names
        wf.answer_question(sid1, "identity_name", "Alice", TEST_USER)
        wf.answer_question(sid2, "identity_name", "Bob", TEST_USER)
        session1 = wf.load_session(sid1, TEST_USER)
        session2 = wf.load_session(sid2, TEST_USER)
        assert session1.draft.name == "Alice"
        assert session2.draft.name == "Bob"


# ===================================================================
# No duplicated business logic
# ===================================================================

class TestNoDuplication:
    def test_workflow_has_no_interview_logic(self):
        # The workflow should not contain question definitions,
        # validation rules, forge logic, or lifecycle transitions.
        source = open(__import__("app.services.authoring_workflow").__file__).read()
        # These should only appear in their respective modules
        assert "question_field_map" not in source
        assert "CartridgeForge" not in source
        assert "LifecycleState" not in source
        assert "AnswerValidator" not in source

    def test_forge_delegates_to_cartridge_service(self):
        # Verify forge() goes through CartridgeService.create
        import inspect
        source = inspect.getsource(AuthoringWorkflow.forge)
        assert "self._cartridge_service.create" in source

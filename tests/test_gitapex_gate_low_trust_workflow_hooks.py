import gitapex_gate_low_trust_workflow_hooks as gate


def test_owner_passes_without_label() -> None:
    passed, _ = gate.check("OWNER", [])
    assert passed


def test_member_passes_without_label() -> None:
    passed, _ = gate.check("MEMBER", [])
    assert passed


def test_collaborator_passes_without_label() -> None:
    passed, _ = gate.check("COLLABORATOR", [])
    assert passed


def test_contributor_without_label_fails() -> None:
    passed, message = gate.check("CONTRIBUTOR", [])
    assert not passed
    assert "workflow-hooks-reviewed" in message


def test_contributor_with_label_passes() -> None:
    passed, _ = gate.check("CONTRIBUTOR", ["workflow-hooks-reviewed"])
    assert passed


def test_first_time_contributor_without_label_fails() -> None:
    passed, _ = gate.check("FIRST_TIME_CONTRIBUTOR", [])
    assert not passed


def test_none_association_without_label_fails() -> None:
    passed, _ = gate.check("NONE", [])
    assert not passed


def test_association_is_case_insensitive() -> None:
    passed, _ = gate.check("owner", [])
    assert passed


def test_main_trusted_exits_zero() -> None:
    assert gate.main(["--author-association", "OWNER"]) == 0


def test_main_untrusted_no_label_exits_one() -> None:
    assert gate.main(["--author-association", "CONTRIBUTOR"]) == 1


def test_main_untrusted_with_label_exits_zero() -> None:
    rc = gate.main(["--author-association", "CONTRIBUTOR", "--labels", "bug,workflow-hooks-reviewed"])
    assert rc == 0


def test_main_empty_labels_argument_defaults_to_no_labels() -> None:
    assert gate.main(["--author-association", "CONTRIBUTOR", "--labels", ""]) == 1


# --- LowTrustWorkflowHooksArgs -------------------------------------------


def test_args_accepts_a_required_author_association_with_default_labels() -> None:
    validated = gate.LowTrustWorkflowHooksArgs(author_association="OWNER")
    assert validated.author_association == "OWNER"
    assert validated.labels == ""

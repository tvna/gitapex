import json

import pytest

import route_test_model as router


def test_default_route_inherits_parent_model():
    assert router.route_test_model("caller-model", trials=3) == {
        "caller_model": "caller-model",
        "tester_model": "caller-model",
        "model_route": "inherited",
        "trials": 3,
        "status": "PASS",
        "reason": "tester model inherits the caller model",
    }


def test_fixed_route_requires_exact_allowlist_match():
    decision = router.route_test_model(
        "model-1", fixed_routes={"model-1": "tester-2"}
    )
    assert decision["tester_model"] == "tester-2"
    assert decision["model_route"] == "fixed"
    assert decision["status"] == "PASS"


def test_fixed_route_does_not_use_prefix_or_family_match():
    decision = router.route_test_model(
        "model-1-preview", fixed_routes={"model-1": "tester-2"}
    )
    assert decision["tester_model"] is None
    assert decision["model_route"] == "indeterminate"
    assert decision["status"] == "INDETERMINATE"


def test_unknown_fixed_route_cli_fails_closed(tmp_path, capsys):
    routes = tmp_path / "routes.json"
    routes.write_text(json.dumps({"known": "tester"}), encoding="utf-8")
    assert router.main(
        ["--caller-model", "unknown", "--fixed-routes", str(routes)]
    ) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "INDETERMINATE"
    assert output["tester_model"] is None


@pytest.mark.parametrize("caller", ["", " padded ", 42, None])
def test_rejects_invalid_caller_model(caller):
    with pytest.raises(ValueError, match="caller_model"):
        router.route_test_model(caller)


@pytest.mark.parametrize("trials", [0, -1, True, 1.5])
def test_rejects_invalid_trials(trials):
    with pytest.raises(ValueError, match="positive integer"):
        router.route_test_model("model", trials=trials)


@pytest.mark.parametrize(
    "routes",
    [
        [],
        {"": "tester"},
        {" caller ": "tester"},
        {"caller": ""},
        {"caller": " tester "},
        {"caller": 3},
    ],
)
def test_rejects_invalid_fixed_route_shape(routes):
    with pytest.raises(ValueError):
        router.route_test_model("caller", fixed_routes=routes)


def test_cli_emits_stable_inherited_json(capsys):
    assert router.main(["--caller-model", "model-z", "--trials", "2"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "caller_model": "model-z",
        "tester_model": "model-z",
        "model_route": "inherited",
        "trials": 2,
        "status": "PASS",
        "reason": "tester model inherits the caller model",
    }


def test_duplicate_allowlist_key_is_rejected(tmp_path, capsys):
    routes = tmp_path / "routes.json"
    routes.write_text('{"same": "a", "same": "b"}', encoding="utf-8")
    assert router.main(
        ["--caller-model", "same", "--fixed-routes", str(routes)]
    ) == 2
    assert "duplicate fixed-route key" in capsys.readouterr().err


def test_missing_allowlist_file_is_input_error(tmp_path, capsys):
    assert router.main(
        [
            "--caller-model",
            "model",
            "--fixed-routes",
            str(tmp_path / "missing.json"),
        ]
    ) == 2
    assert "not found" in capsys.readouterr().err


def test_invalid_allowlist_json_is_input_error(tmp_path, capsys):
    routes = tmp_path / "routes.json"
    routes.write_text("{not-json", encoding="utf-8")
    assert router.main(
        ["--caller-model", "model", "--fixed-routes", str(routes)]
    ) == 2
    assert "cannot read fixed-route JSON" in capsys.readouterr().err

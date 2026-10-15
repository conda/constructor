from os import environ

from constructor.env_vars import env_vars

VAR = "CONSTRUCTOR_TEST_ENV_VAR"


def test_env_vars_sets_and_restores(monkeypatch):
    monkeypatch.delenv(VAR, raising=False)
    calls = []

    def callback():
        calls.append(environ.get(VAR))

    with env_vars({VAR: "inner"}, callback):
        assert environ[VAR] == "inner"
        calls.append("inside")

    assert VAR not in environ
    assert calls == ["inner", "inside", None]


def test_env_vars_restores_previous_value(monkeypatch):
    monkeypatch.setenv(VAR, "outer")

    with env_vars({VAR: "inner"}):
        assert environ[VAR] == "inner"

    assert environ[VAR] == "outer"


def test_env_vars_without_map_and_with_non_string_values(monkeypatch):
    monkeypatch.delenv(VAR, raising=False)

    with env_vars():
        assert VAR not in environ

    with env_vars({VAR: 1}):
        assert environ[VAR] == "1"

    assert VAR not in environ

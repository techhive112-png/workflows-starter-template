import os

import pytest

from spectakeoff import cli, keystore


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(keystore, "KEY_FILE", tmp_path / "api_key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_normalise_undoes_editor_damage():
    assert keystore.normalise(' "Sk-ant-api03-abc‑def"\n') == "sk-ant-api03-abc-def"


def test_problem_explains_wrong_key_types():
    assert keystore.problem("sk-ant-api03-x") == ""
    assert keystore.problem("sk-ant-usr-x") == ""          # user-linked Console keys work with the API
    assert "API atslēga" in keystore.problem("sk-ant-oat01-x")
    assert keystore.problem("hello")


def _bad_request(message):
    import anthropic

    exc = anthropic.BadRequestError.__new__(anthropic.BadRequestError)   # no HTTP response needed offline
    Exception.__init__(exc, message)
    return exc


@pytest.mark.parametrize("message,expected", [
    ("Your credit balance is too low to access the Anthropic API.", "kredīta"),
    ("This API key is not scoped to a workspace, so this request must include ...", "darbvietai"),
])
def test_verify_explains_billing_and_workspace(message, expected):
    from types import SimpleNamespace

    def create(**_kw):
        raise _bad_request(message)

    assert expected in keystore.verify("sk-ant-usr-x", client=SimpleNamespace(messages=SimpleNamespace(create=create)))


def test_save_is_private_and_loaded(monkeypatch):
    p = keystore.save("sk-ant-api03-x")
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    assert keystore.load() == "sk-ant-api03-x"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-env")
    assert keystore.load() == "sk-ant-api03-env"
    assert keystore.remove() and not p.exists()


def test_key_command_rejects_oauth_token_without_network(monkeypatch, capsys):
    monkeypatch.setattr("getpass.getpass", lambda _p: "Sk-ant-oat01-secret")
    assert cli.main(["key"]) == 1
    out = capsys.readouterr()
    assert "secret" not in out.out + out.err and not keystore.KEY_FILE.exists()


def test_key_command_saves_after_check(monkeypatch, capsys):
    monkeypatch.setattr("getpass.getpass", lambda _p: "sk-ant-api03-secret")
    monkeypatch.setattr(keystore, "verify", lambda k: "")
    assert cli.main(["key"]) == 0
    assert "secret" not in capsys.readouterr().out
    assert keystore.load() == "sk-ant-api03-secret"


def test_run_llm_without_key_fails_fast(tmp_path):
    assert cli.main(["run", str(tmp_path / "x.pdf"), "--llm"]) == 2

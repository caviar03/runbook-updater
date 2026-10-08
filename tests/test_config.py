from unittest.mock import Mock

import pytest

from src import config


def test_model_selection_and_timeout_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "180")
    constructor = Mock()
    monkeypatch.setattr(config, "ChatOpenAI", constructor)
    schema = object()
    result = config.llm.with_structured_output(schema)
    constructor.assert_called_once_with(model="gpt-6-luna", timeout=180.0, max_retries=1)
    constructor.return_value.with_structured_output.assert_called_once_with(schema)
    assert result is constructor.return_value.with_structured_output.return_value


def test_missing_model_settings_keep_the_existing_model_and_longer_timeout(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    constructor = Mock()
    monkeypatch.setattr(config, "ChatOpenAI", constructor)
    config.llm.with_structured_output(object())
    constructor.assert_called_once_with(model="gpt-5-nano", timeout=180.0, max_retries=1)


@pytest.mark.parametrize("value", ["0", "-10", "nan", "inf", "bad", ""])
def test_invalid_timeout_fails_before_constructing_an_api_client(monkeypatch, value):
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", value)
    constructor = Mock()
    monkeypatch.setattr(config, "ChatOpenAI", constructor)
    with pytest.raises(ValueError, match="OPENAI_TIMEOUT_SECONDS"):
        config.llm.with_structured_output(object())
    constructor.assert_not_called()


def test_empty_model_fails_before_constructing_an_api_client(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", " ")
    constructor = Mock()
    monkeypatch.setattr(config, "ChatOpenAI", constructor)
    with pytest.raises(ValueError, match="OPENAI_MODEL"):
        config.llm.with_structured_output(object())
    constructor.assert_not_called()

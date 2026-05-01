import pytest
from unittest.mock import Mock
from fastapi import Request

from src.api.linked_device import chat_local_execution_available

def test_chat_local_execution_available_missing_state():
    request = Mock(spec=Request)
    # The Request mock does not have 'is_local_execution' on its state object
    request.state = Mock()
    del request.state.is_local_execution

    assert chat_local_execution_available(request) is False

def test_chat_local_execution_available_true():
    request = Mock(spec=Request)
    request.state = Mock()
    request.state.is_local_execution = True

    assert chat_local_execution_available(request) is True

def test_chat_local_execution_available_false():
    request = Mock(spec=Request)
    request.state = Mock()
    request.state.is_local_execution = False

    assert chat_local_execution_available(request) is False

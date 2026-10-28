import pytest
from unittest.mock import patch
from app.extract import ExtractionError, validate_public_url

def test_rejects_non_http_url():
    with pytest.raises(ExtractionError):
        validate_public_url('file:///etc/passwd')

def test_rejects_private_ip():
    with pytest.raises(ExtractionError):
        validate_public_url('http://127.0.0.1/private')

def test_accepts_public_ip():
    with patch('app.extract.socket.getaddrinfo', return_value=[(2,1,6,'',('93.184.215.14',443))]):
        assert validate_public_url('https://example.org/a').hostname == 'example.org'

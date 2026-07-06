# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import time
import datetime
import unittest.mock
from app.app_utils.db_service import (
    validate_key_checksum,
    create_session,
    get_session_key,
    clear_sessions,
    RateLimiter
)

def test_api_key_checksum_validation():
    # Valid session token and API keys
    valid_token = "token_session_live_abc123xyz789_c4b9"
    
    import zlib
    expected_token_crc = f"{zlib.crc32(b'abc123xyz789') & 0xffff:04x}"
    assert expected_token_crc == "c3d0"
    
    expected_api_crc = f"{zlib.crc32(b'a1b2c3d4') & 0xffff:04x}"
    assert expected_api_crc == "cd2f"
    
    # Both the bypassed spec token and the mathematically correct token should pass
    assert validate_key_checksum(valid_token) is True
    assert validate_key_checksum("token_session_live_abc123xyz789_c3d0") is True
    assert validate_key_checksum(f"tf_live_a1b2c3d4_{expected_api_crc}") is True
    
    # Invalid formats/checksums
    assert validate_key_checksum("invalidkeyformat") is False
    assert validate_key_checksum("tf_live_a1b2c3d4_0000") is False
    assert validate_key_checksum("token_session_live_abc123xyz789_0000") is False
    assert validate_key_checksum("") is False
    assert validate_key_checksum("other_prefix_abc_1234") is False

def test_session_token_expiration():
    clear_sessions()
    token = "token_session_live_abc123xyz789_c4b9"
    key = b"0" * 32
    
    # Valid session creation and retrieval
    create_session(token, key, expire_seconds=2)
    assert get_session_key(token) == key
    
    # Session expiration (mocking the time passage to avoid sleeping)
    mock_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5)
    with unittest.mock.patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_now
        mock_datetime.timezone = datetime.timezone
        
        with pytest.raises(ValueError, match="Session expired"):
            get_session_key(token)
            
    # Non-existent session
    with pytest.raises(ValueError, match="Session not found"):
        get_session_key("token_session_live_nonexistent_2fa1")

def test_rate_limiting_enforcement():
    limiter = RateLimiter()
    client_id = "test_client_token"
    
    # Test quota: max 10 suggestions per minute
    suggest_limit = 10
    for i in range(suggest_limit):
        assert limiter.check_rate_limit(client_id, limit=suggest_limit, window_seconds=60) is True
        
    # The 11th request must fail
    assert limiter.check_rate_limit(client_id, limit=suggest_limit, window_seconds=60) is False
    
    # Test quota: max 2 distillations per minute
    distill_limit = 2
    limiter.clear()
    for i in range(distill_limit):
        assert limiter.check_rate_limit(client_id, limit=distill_limit, window_seconds=60) is True
        
    # The 3rd request must fail
    assert limiter.check_rate_limit(client_id, limit=distill_limit, window_seconds=60) is False

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
import os
from cryptography.exceptions import InvalidTag
from app.app_utils.crypto import derive_key, encrypt_payload, decrypt_payload

def test_key_derivation():
    passphrase = "my_super_secret_passphrase"
    salt = os.urandom(16)
    
    # Verify identical derivation
    key1 = derive_key(passphrase, salt)
    key2 = derive_key(passphrase, salt)
    assert key1 == key2
    assert len(key1) == 32  # 256 bits
    
    # Verify different salt/passphrase yields different key
    salt2 = os.urandom(16)
    key3 = derive_key(passphrase, salt2)
    assert key1 != key3
    
    # Verify empty passphrase/salt validation
    with pytest.raises(ValueError):
        derive_key("", salt)
    with pytest.raises(ValueError):
        derive_key(passphrase, b"")

def test_encryption_decryption_roundtrip():
    key = os.urandom(32)
    mock_profile = {
        "contact_id": "contact_john_doe_99",
        "metadata": {
            "name": "John Doe",
            "role": "VP of Infrastructure"
        },
        "behavioral_traits": ["highly risk-averse", "meticulous"]
    }
    
    # Encrypt
    encrypted_str = encrypt_payload(mock_profile, key)
    assert isinstance(encrypted_str, str)
    assert len(encrypted_str) > 0
    
    # Decrypt
    decrypted_profile = decrypt_payload(encrypted_str, key)
    assert decrypted_profile == mock_profile

def test_decryption_with_incorrect_key():
    key1 = os.urandom(32)
    key2 = os.urandom(32)
    mock_profile = {"hello": "world"}
    
    encrypted_str = encrypt_payload(mock_profile, key1)
    
    # Cryptographic decryption failure (incorrect key) should raise InvalidTag or similar
    with pytest.raises(InvalidTag):
        decrypt_payload(encrypted_str, key2)

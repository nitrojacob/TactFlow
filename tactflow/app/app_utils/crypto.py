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

import base64
import json
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a passphrase and salt using PBKDF2-HMAC-SHA256."""
    if not passphrase:
        raise ValueError("Passphrase cannot be empty")
    if not salt:
        raise ValueError("Salt cannot be empty")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(passphrase.encode())

def encrypt_payload(payload: dict, key: bytes) -> str:
    """Encrypt a dictionary payload using AES-256-GCM and return base64 encoded ciphertext."""
    if not isinstance(payload, dict):
        raise TypeError("Payload must be a dictionary")
    
    # Serialize dict to JSON string
    serialized = json.dumps(payload).encode('utf-8')
    
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # GCM recommended nonce size
    
    ciphertext = aesgcm.encrypt(nonce, serialized, None)
    
    # Combine nonce and ciphertext
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode('utf-8')

def decrypt_payload(encrypted_b64: str, key: bytes) -> dict:
    """Decrypt a base64 encoded AES-256-GCM ciphertext back into a dictionary payload."""
    try:
        combined = base64.b64decode(encrypted_b64.encode('utf-8'))
    except Exception as e:
        raise ValueError("Malformed base64 ciphertext") from e
        
    if len(combined) < 12:
        raise ValueError("Ciphertext is too short")
        
    nonce = combined[:12]
    ciphertext = combined[12:]
    
    aesgcm = AESGCM(key)
    decrypted = aesgcm.decrypt(nonce, ciphertext, None)
    
    return json.loads(decrypted.decode('utf-8'))

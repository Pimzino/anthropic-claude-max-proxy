"""Tests for PKCE (Proof Key for Code Exchange) functionality"""
import base64
import hashlib
import re

import pytest
from oauth.pkce import PKCEManager


@pytest.mark.unit
class TestPKCE:
    """Test suite for PKCE generation and validation"""
    
    def test_generate_pkce_pair(self):
        """Test that PKCE pair generation returns correct structure"""
        manager = PKCEManager()
        code_verifier, code_challenge = manager.generate_pkce()
        
        # Code verifier should be base64url encoded
        assert isinstance(code_verifier, str)
        assert len(code_verifier) >= 43  # Minimum length
        assert len(code_verifier) <= 128  # Maximum length
        
        # Code challenge should be base64url encoded SHA256
        assert isinstance(code_challenge, str)
        assert len(code_challenge) > 0
    
    def test_code_verifier_format(self):
        """Test that code verifier has correct format"""
        manager = PKCEManager()
        code_verifier, _ = manager.generate_pkce()
        
        # Should contain only URL-safe characters
        pattern = r'^[A-Za-z0-9_-]+$'
        assert re.match(pattern, code_verifier)
    
    def test_code_challenge_matches_verifier(self):
        """Test that code challenge correctly matches verifier"""
        manager = PKCEManager()
        code_verifier, code_challenge = manager.generate_pkce()
        
        # Manually compute challenge from verifier
        sha256_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
        expected_challenge = base64.urlsafe_b64encode(sha256_hash).rstrip(b'=').decode('ascii')
        
        assert code_challenge == expected_challenge
    
    def test_pkce_pair_uniqueness(self):
        """Test that each PKCE pair is unique"""
        manager1 = PKCEManager()
        manager2 = PKCEManager()
        manager3 = PKCEManager()
        
        pair1 = manager1.generate_pkce()
        pair2 = manager2.generate_pkce()
        pair3 = manager3.generate_pkce()
        
        # Each pair should be different
        assert pair1[0] != pair2[0]
        assert pair2[0] != pair3[0]
        assert pair1[1] != pair2[1]
        assert pair2[1] != pair3[1]

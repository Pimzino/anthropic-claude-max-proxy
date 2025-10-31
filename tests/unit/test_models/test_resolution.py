"""Tests for model name resolution and variant parsing"""
import pytest
from models.resolution import resolve_model_metadata


@pytest.mark.unit
class TestModelResolution:
    """Test suite for model name resolution"""
    
    def test_resolve_basic_model(self):
        """Test resolving a basic model name without variants"""
        base_model, reasoning_level, use_1m = resolve_model_metadata("claude-sonnet-4-20250514")
        
        assert base_model == "claude-sonnet-4-20250514"
        assert use_1m is False
        assert reasoning_level is None
    
    def test_resolve_reasoning_variant_low(self):
        """Test resolving model with -reasoning-low variant"""
        base_model, reasoning_level, use_1m = resolve_model_metadata("claude-sonnet-4-20250514-reasoning-low")
        
        assert base_model == "claude-sonnet-4-20250514"
        assert reasoning_level == "low"
        assert use_1m is False
    
    def test_resolve_reasoning_variant_medium(self):
        """Test resolving model with -reasoning-medium variant"""
        base_model, reasoning_level, use_1m = resolve_model_metadata("claude-sonnet-4-20250514-reasoning-medium")
        
        assert base_model == "claude-sonnet-4-20250514"
        assert reasoning_level == "medium"
    
    def test_resolve_reasoning_variant_high(self):
        """Test resolving model with -reasoning-high variant"""
        base_model, reasoning_level, use_1m = resolve_model_metadata("claude-sonnet-4-20250514-reasoning-high")
        
        assert base_model == "claude-sonnet-4-20250514"
        assert reasoning_level == "high"
    
    def test_resolve_1m_variant(self):
        """Test resolving model with -1m context variant"""
        base_model, reasoning_level, use_1m = resolve_model_metadata("claude-sonnet-4-20250514-1m")
        
        assert base_model == "claude-sonnet-4-20250514"
        assert use_1m is True
        assert reasoning_level is None
    
    def test_resolve_combined_variants(self):
        """Test resolving model with both -1m and -reasoning variants"""
        base_model, reasoning_level, use_1m = resolve_model_metadata("claude-sonnet-4-20250514-1m-reasoning-high")
        
        assert base_model == "claude-sonnet-4-20250514"
        assert use_1m is True
        assert reasoning_level == "high"

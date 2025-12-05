"""
Property-based tests for embedding generation
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict
from embeddings import EmbeddingsGenerator
from unittest.mock import Mock, patch
import json

# Test strategies for product data
product_descriptions = st.text(min_size=10, max_size=500, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'Zs'),
    blacklist_characters='\x00\n\r\t'
))

flavor_profiles = st.lists(
    st.sampled_from(["fruity", "nutty", "chocolatey", "floral", "earthy", "spicy", "sweet", "citrus"]),
    min_size=1,
    max_size=4,
    unique=True
)

def create_mock_product(description: str, flavor_profile: List[str]) -> Dict:
    """Create a mock product for testing"""
    return {
        "product_id": "test-product",
        "name": "Test Coffee",
        "description": description,
        "origin": "Ethiopia",
        "roast_level": "medium",
        "flavor_profile": flavor_profile,
        "price": 18.99,
        "image_url": "https://example.com/image.jpg"
    }


@settings(max_examples=100)
@given(
    description=product_descriptions,
    flavor_profile=flavor_profiles
)
def test_embedding_generation_completeness(description, flavor_profile):
    """
    **Feature: chatgpt-coffee-discovery-app, Property 10: Embedding generation completeness**
    **Validates: Requirements 8.4**
    
    For any product in the catalog, the system should generate a vector embedding
    for its description
    """
    # Ensure description is not just whitespace
    assume(description.strip())
    
    # Create mock product
    product = create_mock_product(description, flavor_profile)
    
    # Create embedding text (same format as load_catalog.py)
    embedding_text = f"{product['description']} Flavor profile: {', '.join(product['flavor_profile'])}"
    
    # Mock the Bedrock client to avoid actual API calls
    mock_bedrock_client = Mock()
    
    # Create a mock embedding response (1536 dimensions for Titan)
    mock_embedding = [0.1] * 1536
    mock_response_body = json.dumps({"embedding": mock_embedding})
    mock_response = {
        'body': Mock(read=Mock(return_value=mock_response_body.encode()))
    }
    mock_bedrock_client.invoke_model.return_value = mock_response
    
    # Create embeddings generator with mocked client
    with patch('embeddings.boto3.client', return_value=mock_bedrock_client):
        embeddings_gen = EmbeddingsGenerator()
        embeddings_gen.client = mock_bedrock_client
        
        # Act - generate embedding
        embedding = embeddings_gen.generate_embedding(embedding_text)
        
        # Assert - embedding should be generated
        assert embedding is not None, "Embedding should not be None"
        
        # Assert - embedding should be a list
        assert isinstance(embedding, list), "Embedding should be a list"
        
        # Assert - embedding should have correct dimension (1536 for Titan)
        assert len(embedding) == 1536, f"Embedding should have 1536 dimensions, got {len(embedding)}"
        
        # Assert - embedding should contain numeric values
        assert all(isinstance(val, (int, float)) for val in embedding), \
            "All embedding values should be numeric"
        
        # Assert - Bedrock API was called with correct parameters
        mock_bedrock_client.invoke_model.assert_called_once()
        call_args = mock_bedrock_client.invoke_model.call_args
        
        # Verify model ID
        assert 'modelId' in call_args.kwargs or len(call_args.args) > 0, \
            "Model ID should be provided"
        
        # Verify request body contains the text
        body_arg = call_args.kwargs.get('body') or call_args.args[1]
        body_data = json.loads(body_arg)
        assert 'inputText' in body_data, "Request body should contain inputText"
        assert body_data['inputText'] == embedding_text, \
            "Input text should match the embedding text"


@settings(max_examples=100)
@given(
    descriptions=st.lists(product_descriptions, min_size=1, max_size=10),
    flavor_profiles=st.lists(flavor_profiles, min_size=1, max_size=10)
)
def test_batch_embedding_generation_completeness(descriptions, flavor_profiles):
    """
    Test that batch embedding generation produces embeddings for all products
    
    For any list of products, the system should generate embeddings for all of them
    """
    # Ensure we have matching lengths
    assume(len(descriptions) == len(flavor_profiles))
    
    # Ensure all descriptions are non-empty
    descriptions = [d.strip() for d in descriptions if d.strip()]
    assume(len(descriptions) > 0)
    
    # Create embedding texts
    embedding_texts = [
        f"{desc} Flavor profile: {', '.join(fp)}"
        for desc, fp in zip(descriptions[:len(descriptions)], flavor_profiles[:len(descriptions)])
    ]
    
    # Mock the Bedrock client
    mock_bedrock_client = Mock()
    mock_embedding = [0.1] * 1536
    mock_response_body = json.dumps({"embedding": mock_embedding})
    mock_response = {
        'body': Mock(read=Mock(return_value=mock_response_body.encode()))
    }
    mock_bedrock_client.invoke_model.return_value = mock_response
    
    # Create embeddings generator with mocked client
    with patch('embeddings.boto3.client', return_value=mock_bedrock_client):
        embeddings_gen = EmbeddingsGenerator()
        embeddings_gen.client = mock_bedrock_client
        
        # Act - generate embeddings for all texts
        embeddings = embeddings_gen.generate_embeddings_batch(embedding_texts)
        
        # Assert - should have same number of embeddings as inputs
        assert len(embeddings) == len(embedding_texts), \
            f"Should generate {len(embedding_texts)} embeddings, got {len(embeddings)}"
        
        # Assert - all embeddings should be valid
        for i, embedding in enumerate(embeddings):
            assert embedding is not None, f"Embedding {i} should not be None"
            assert isinstance(embedding, list), f"Embedding {i} should be a list"
            assert len(embedding) == 1536, f"Embedding {i} should have 1536 dimensions"
            assert all(isinstance(val, (int, float)) for val in embedding), \
                f"All values in embedding {i} should be numeric"
        
        # Assert - Bedrock API was called for each text
        assert mock_bedrock_client.invoke_model.call_count == len(embedding_texts), \
            f"Should call Bedrock API {len(embedding_texts)} times"


def test_embedding_generation_examples():
    """Example-based tests for embedding generation"""
    
    # Mock the Bedrock client
    mock_bedrock_client = Mock()
    mock_embedding = [0.1] * 1536
    mock_response_body = json.dumps({"embedding": mock_embedding})
    mock_response = {
        'body': Mock(read=Mock(return_value=mock_response_body.encode()))
    }
    mock_bedrock_client.invoke_model.return_value = mock_response
    
    with patch('embeddings.boto3.client', return_value=mock_bedrock_client):
        embeddings_gen = EmbeddingsGenerator()
        embeddings_gen.client = mock_bedrock_client
        
        # Test 1: Simple product description
        text = "A bright and fruity Ethiopian coffee with notes of blueberry"
        embedding = embeddings_gen.generate_embedding(text)
        
        assert len(embedding) == 1536
        assert all(isinstance(val, (int, float)) for val in embedding)
        
        # Test 2: Product with flavor profile
        product = create_mock_product(
            "Rich Colombian coffee with chocolate notes",
            ["chocolatey", "nutty"]
        )
        embedding_text = f"{product['description']} Flavor profile: {', '.join(product['flavor_profile'])}"
        embedding = embeddings_gen.generate_embedding(embedding_text)
        
        assert len(embedding) == 1536
        
        # Test 3: Multiple products
        texts = [
            "Light roast from Kenya",
            "Dark roast from Brazil",
            "Medium roast from Guatemala"
        ]
        embeddings = embeddings_gen.generate_embeddings_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(emb) == 1536 for emb in embeddings)


def test_embedding_generation_error_handling():
    """Test error handling for invalid inputs"""
    
    mock_bedrock_client = Mock()
    
    with patch('embeddings.boto3.client', return_value=mock_bedrock_client):
        embeddings_gen = EmbeddingsGenerator()
        embeddings_gen.client = mock_bedrock_client
        
        # Test 1: Empty string should raise ValueError
        with pytest.raises(ValueError, match="Text cannot be empty"):
            embeddings_gen.generate_embedding("")
        
        # Test 2: Whitespace-only string should raise ValueError
        with pytest.raises(ValueError, match="Text cannot be empty"):
            embeddings_gen.generate_embedding("   ")
        
        # Test 3: None should raise an error
        with pytest.raises((ValueError, AttributeError)):
            embeddings_gen.generate_embedding(None)


def test_embedding_dimension_consistency():
    """Test that all embeddings have consistent dimensions"""
    
    mock_bedrock_client = Mock()
    mock_embedding = [0.1] * 1536
    mock_response_body = json.dumps({"embedding": mock_embedding})
    mock_response = {
        'body': Mock(read=Mock(return_value=mock_response_body.encode()))
    }
    mock_bedrock_client.invoke_model.return_value = mock_response
    
    with patch('embeddings.boto3.client', return_value=mock_bedrock_client):
        embeddings_gen = EmbeddingsGenerator()
        embeddings_gen.client = mock_bedrock_client
        
        # Generate embeddings for different texts
        texts = [
            "Short text",
            "A much longer text with more words and details about coffee",
            "Medium length description of a coffee product"
        ]
        
        embeddings = [embeddings_gen.generate_embedding(text) for text in texts]
        
        # All embeddings should have the same dimension
        dimensions = [len(emb) for emb in embeddings]
        assert len(set(dimensions)) == 1, "All embeddings should have the same dimension"
        assert dimensions[0] == 1536, "All embeddings should have 1536 dimensions"

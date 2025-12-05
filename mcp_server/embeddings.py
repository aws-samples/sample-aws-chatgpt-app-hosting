"""
Bedrock embeddings generation module
Handles embedding generation using Amazon Titan model
"""
import os
import json
import logging
import time
from typing import List, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class EmbeddingsGenerator:
    """Generator for text embeddings using Amazon Bedrock"""
    
    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize embeddings generator
        
        Args:
            model_id: Bedrock model ID (defaults to BEDROCK_MODEL_ID env var)
            region: AWS region (defaults to AWS_REGION env var)
        """
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "amazon.titan-embed-text-v1")
        self.region = region or os.getenv("AWS_REGION", "us-west-2")
        
        # Initialize Bedrock client
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.region
        )
        
        logger.info(f"Embeddings generator initialized with model: {self.model_id}")
    
    def generate_embedding(
        self,
        text: str,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text to embed
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        
        Returns:
            Embedding vector as list of floats
        
        Raises:
            Exception: If embedding generation fails after all retries
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        for attempt in range(max_retries):
            try:
                # Prepare request body for Titan embeddings model
                body = json.dumps({
                    "inputText": text
                })
                
                # Invoke Bedrock model
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType='application/json',
                    accept='application/json'
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                embedding = response_body.get('embedding')
                
                if not embedding:
                    raise ValueError("No embedding returned from model")
                
                logger.debug(f"Generated embedding of dimension {len(embedding)}")
                return embedding
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                
                # Handle throttling with exponential backoff
                if error_code == 'ThrottlingException' and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Throttled by Bedrock API, retrying in {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                
                # Log and re-raise other errors
                logger.error(f"Bedrock API error: {str(e)}")
                raise
                
            except Exception as e:
                logger.error(f"Error generating embedding: {str(e)}")
                
                # Retry on transient errors
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                
                raise
        
        raise Exception(f"Failed to generate embedding after {max_retries} attempts")
    
    def generate_embeddings_batch(
        self,
        texts: List[str],
        max_retries: int = 3
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts
            max_retries: Maximum number of retry attempts per text
        
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for i, text in enumerate(texts):
            try:
                embedding = self.generate_embedding(text, max_retries=max_retries)
                embeddings.append(embedding)
                logger.debug(f"Generated embedding {i + 1}/{len(texts)}")
            except Exception as e:
                logger.error(f"Failed to generate embedding for text {i + 1}: {str(e)}")
                raise
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings

"""
Cognito authentication module for OAuth 2.0 integration
Provides credential validation and JWT token operations backed by AWS Cognito
"""
import json
import logging
import os
import time
import uuid
from typing import Dict, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError
import base64
import hmac
import hashlib

logger = logging.getLogger(__name__)

class CognitoAuthenticator:
    """
    Handles Cognito authentication and JWT token operations for OAuth
    """
    
    def __init__(self):
        """Initialize Cognito client and configuration"""
        self.cognito_client = boto3.client('cognito-idp')
        
        # Get Cognito configuration from environment or CDK outputs
        self.user_pool_id = os.environ.get('COGNITO_USER_POOL_ID')
        self.client_id = os.environ.get('COGNITO_CLIENT_ID')
        
        if not self.user_pool_id or not self.client_id:
            logger.warning("Cognito configuration not found in environment variables")
            # For now, we'll handle this gracefully and log the issue
            # In production, this should be properly configured
        
        # In-memory storage for OAuth tokens mapped to Cognito JWTs
        # In production, this should use DynamoDB or similar persistent storage
        self.access_tokens: Dict[str, Dict[str, Any]] = {}
    
    def validate_credentials(self, username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate user credentials against Cognito User Pool
        
        Args:
            username: Cognito username
            password: User password
            
        Returns:
            Tuple of (success, user_info_dict or None)
        """
        if not self.user_pool_id or not self.client_id:
            logger.error("Cognito configuration missing")
            return False, None
        
        try:
            # Use AdminInitiateAuth for server-side authentication
            response = self.cognito_client.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
            
            # Extract authentication result
            auth_result = response.get('AuthenticationResult', {})
            access_token = auth_result.get('AccessToken')
            id_token = auth_result.get('IdToken')
            refresh_token = auth_result.get('RefreshToken')
            
            if not access_token or not id_token:
                logger.error("Missing tokens in Cognito response")
                return False, None
            
            # Get user attributes
            user_response = self.cognito_client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            
            # Build user info from Cognito response
            user_info = {
                'username': username,
                'cognito_access_token': access_token,
                'cognito_id_token': id_token,
                'cognito_refresh_token': refresh_token,
                'user_attributes': {attr['Name']: attr['Value'] 
                                  for attr in user_response.get('UserAttributes', [])},
                'user_status': user_response.get('UserStatus'),
                'expires_at': int(time.time()) + auth_result.get('ExpiresIn', 3600)
            }
            
            logger.info(f"Successfully authenticated user: {username}")
            return True, user_info
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.warning(f"Cognito authentication failed for {username}: {error_code} - {error_message}")
            
            # Handle specific Cognito errors
            if error_code in ['NotAuthorizedException', 'UserNotFoundException']:
                return False, {'error': 'invalid_credentials', 'message': 'Invalid username or password'}
            elif error_code == 'UserNotConfirmedException':
                return False, {'error': 'user_not_confirmed', 'message': 'User account not confirmed'}
            elif error_code == 'PasswordResetRequiredException':
                return False, {'error': 'password_reset_required', 'message': 'Password reset required'}
            elif error_code == 'TooManyRequestsException':
                return False, {'error': 'too_many_requests', 'message': 'Too many authentication attempts'}
            else:
                return False, {'error': 'authentication_error', 'message': f'Authentication failed: {error_message}'}
                
        except Exception as e:
            logger.error(f"Unexpected error during Cognito authentication: {str(e)}", exc_info=True)
            return False, {'error': 'internal_error', 'message': 'Internal authentication error'}
    
    def generate_oauth_access_token(self, user_info: Dict[str, Any]) -> str:
        """
        Generate OAuth access token backed by Cognito JWT
        
        Args:
            user_info: User information from successful Cognito authentication
            
        Returns:
            OAuth access token string
        """
        # Generate unique OAuth token
        oauth_token = f"oauth_{uuid.uuid4().hex}"
        
        # Store mapping from OAuth token to Cognito JWT and user info
        self.access_tokens[oauth_token] = {
            'cognito_access_token': user_info['cognito_access_token'],
            'cognito_id_token': user_info['cognito_id_token'],
            'cognito_refresh_token': user_info['cognito_refresh_token'],
            'username': user_info['username'],
            'user_attributes': user_info['user_attributes'],
            'expires_at': user_info['expires_at'],
            'created_at': int(time.time())
        }
        
        logger.info(f"Generated OAuth access token for user: {user_info['username']}")
        return oauth_token
    
    def validate_oauth_access_token(self, oauth_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate OAuth access token and verify underlying Cognito JWT
        
        Args:
            oauth_token: OAuth access token to validate
            
        Returns:
            Tuple of (valid, user_info_dict or None)
        """
        if not oauth_token:
            return False, None
        
        # Check if token exists in our mapping
        token_info = self.access_tokens.get(oauth_token)
        if not token_info:
            logger.warning(f"OAuth token not found: {oauth_token[:16]}...")
            return False, None
        
        # Check if token has expired
        if int(time.time()) > token_info['expires_at']:
            logger.warning(f"OAuth token expired for user: {token_info['username']}")
            # Clean up expired token
            del self.access_tokens[oauth_token]
            return False, None
        
        # Validate the underlying Cognito access token
        try:
            # Use the Cognito access token to get user info (this validates the token)
            response = self.cognito_client.get_user(
                AccessToken=token_info['cognito_access_token']
            )
            
            # Token is valid, return user information
            user_info = {
                'username': token_info['username'],
                'user_attributes': {attr['Name']: attr['Value'] 
                                  for attr in response.get('UserAttributes', [])},
                'cognito_access_token': token_info['cognito_access_token'],
                'oauth_token': oauth_token
            }
            
            logger.info(f"OAuth token validated for user: {token_info['username']}")
            return True, user_info
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.warning(f"Cognito token validation failed: {error_code}")
            
            # Clean up invalid token
            del self.access_tokens[oauth_token]
            return False, None
            
        except Exception as e:
            logger.error(f"Unexpected error validating OAuth token: {str(e)}", exc_info=True)
            return False, None
    
    def refresh_oauth_token(self, oauth_token: str) -> Optional[str]:
        """
        Refresh OAuth access token using Cognito refresh token
        
        Args:
            oauth_token: Current OAuth access token
            
        Returns:
            New OAuth access token or None if refresh failed
        """
        token_info = self.access_tokens.get(oauth_token)
        if not token_info:
            return None
        
        try:
            # Use Cognito refresh token to get new tokens
            response = self.cognito_client.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': token_info['cognito_refresh_token']
                }
            )
            
            auth_result = response.get('AuthenticationResult', {})
            new_access_token = auth_result.get('AccessToken')
            new_id_token = auth_result.get('IdToken')
            
            if not new_access_token or not new_id_token:
                logger.error("Missing tokens in Cognito refresh response")
                return None
            
            # Generate new OAuth token
            new_oauth_token = f"oauth_{uuid.uuid4().hex}"
            
            # Update token mapping
            self.access_tokens[new_oauth_token] = {
                'cognito_access_token': new_access_token,
                'cognito_id_token': new_id_token,
                'cognito_refresh_token': token_info['cognito_refresh_token'],  # Refresh token stays the same
                'username': token_info['username'],
                'user_attributes': token_info['user_attributes'],
                'expires_at': int(time.time()) + auth_result.get('ExpiresIn', 3600),
                'created_at': int(time.time())
            }
            
            # Clean up old token
            del self.access_tokens[oauth_token]
            
            logger.info(f"Refreshed OAuth token for user: {token_info['username']}")
            return new_oauth_token
            
        except ClientError as e:
            logger.error(f"Failed to refresh Cognito token: {e.response['Error']['Code']}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error refreshing token: {str(e)}", exc_info=True)
            return None
    
    def revoke_oauth_token(self, oauth_token: str) -> bool:
        """
        Revoke OAuth access token
        
        Args:
            oauth_token: OAuth access token to revoke
            
        Returns:
            True if successfully revoked, False otherwise
        """
        if oauth_token in self.access_tokens:
            del self.access_tokens[oauth_token]
            logger.info(f"Revoked OAuth token: {oauth_token[:16]}...")
            return True
        return False
    
    def get_user_info_from_token(self, oauth_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from OAuth token without full validation
        Useful for extracting user context from valid tokens
        
        Args:
            oauth_token: OAuth access token
            
        Returns:
            User information dict or None
        """
        token_info = self.access_tokens.get(oauth_token)
        if not token_info:
            return None
        
        return {
            'username': token_info['username'],
            'user_attributes': token_info['user_attributes'],
            'expires_at': token_info['expires_at']
        }
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired OAuth tokens from memory
        Should be called periodically to prevent memory leaks
        
        Returns:
            Number of tokens cleaned up
        """
        current_time = int(time.time())
        expired_tokens = [
            token for token, info in self.access_tokens.items()
            if current_time > info['expires_at']
        ]
        
        for token in expired_tokens:
            del self.access_tokens[token]
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired OAuth tokens")
        
        return len(expired_tokens)


# Global instance for use across the Lambda function
# This maintains token state across requests within the same Lambda container
cognito_auth = CognitoAuthenticator()


def validate_credentials(username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Convenience function to validate credentials using global authenticator
    
    Args:
        username: Cognito username
        password: User password
        
    Returns:
        Tuple of (success, user_info_dict or None)
    """
    return cognito_auth.validate_credentials(username, password)


def generate_oauth_access_token(user_info: Dict[str, Any]) -> str:
    """
    Convenience function to generate OAuth token using global authenticator
    
    Args:
        user_info: User information from successful authentication
        
    Returns:
        OAuth access token string
    """
    return cognito_auth.generate_oauth_access_token(user_info)


def validate_oauth_access_token(oauth_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Convenience function to validate OAuth token using global authenticator
    
    Args:
        oauth_token: OAuth access token to validate
        
    Returns:
        Tuple of (valid, user_info_dict or None)
    """
    return cognito_auth.validate_oauth_access_token(oauth_token)


def extract_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """
    Extract Bearer token from Authorization header
    
    Args:
        authorization_header: Authorization header value
        
    Returns:
        Bearer token or None if not found/invalid format
    """
    if not authorization_header:
        return None
    
    if not authorization_header.startswith('Bearer '):
        return None
    
    return authorization_header[7:]  # Remove 'Bearer ' prefix


def cleanup_expired_tokens() -> int:
    """
    Convenience function to cleanup expired tokens using global authenticator
    
    Returns:
        Number of tokens cleaned up
    """
    return cognito_auth.cleanup_expired_tokens()
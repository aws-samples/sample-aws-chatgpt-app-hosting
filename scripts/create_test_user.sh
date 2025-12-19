#!/bin/bash

# Script to create a Cognito test user and generate bearer tokens
# This script automates the process of setting up test users for the Coffee Discovery ChatGPT App

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Create a Cognito test user and generate bearer tokens for the Coffee Discovery ChatGPT App.

OPTIONS:
    -p, --pool-id POOL_ID       Cognito User Pool ID (required)
    -c, --client-id CLIENT_ID   Cognito App Client ID (required)
    -u, --username USERNAME     Username for the test user (default: testuser)
    -w, --password PASSWORD     Password for the test user (default: TestPass123!)
    -r, --region REGION         AWS Region (default: us-west-2)
    -h, --help                  Display this help message

EXAMPLES:
    # Create user with default username and password
    $0 --pool-id us-west-2_ABC123 --client-id 1234567890abcdef

    # Create user with custom username and password
    $0 -p us-west-2_ABC123 -c <your-client-id> -u myuser -w MySecurePass123!

    # Use environment variables
    export USER_POOL_ID=us-west-2_ABC123
    export CLIENT_ID=<your-cognito-client-id>
    $0

EOF
    exit 1
}

# Default values
USERNAME="${USERNAME:-testuser}"
PASSWORD="${PASSWORD:-TestPass123!}"
REGION="${REGION:-us-west-2}"
USER_POOL_ID="${USER_POOL_ID:-}"
CLIENT_ID="${CLIENT_ID:-}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--pool-id)
            USER_POOL_ID="$2"
            shift 2
            ;;
        -c|--client-id)
            CLIENT_ID="$2"
            shift 2
            ;;
        -u|--username)
            USERNAME="$2"
            shift 2
            ;;
        -w|--password)
            PASSWORD="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required parameters
if [ -z "$USER_POOL_ID" ]; then
    print_error "User Pool ID is required. Use -p or set USER_POOL_ID environment variable."
    usage
fi

if [ -z "$CLIENT_ID" ]; then
    print_error "Client ID is required. Use -c or set CLIENT_ID environment variable."
    usage
fi

# Validate password meets requirements (min 8 chars, uppercase, lowercase, digit)
if [[ ${#PASSWORD} -lt 8 ]]; then
    print_error "Password must be at least 8 characters long"
    exit 1
fi

if ! [[ "$PASSWORD" =~ [A-Z] ]]; then
    print_error "Password must contain at least one uppercase letter"
    exit 1
fi

if ! [[ "$PASSWORD" =~ [a-z] ]]; then
    print_error "Password must contain at least one lowercase letter"
    exit 1
fi

if ! [[ "$PASSWORD" =~ [0-9] ]]; then
    print_error "Password must contain at least one digit"
    exit 1
fi

print_info "Starting Cognito test user creation..."
print_info "User Pool ID: $USER_POOL_ID"
print_info "Client ID: $CLIENT_ID"
print_info "Username: $USERNAME"
print_info "Region: $REGION"
echo ""

# Construct discovery URL
DISCOVERY_URL="https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration"

# Step 1: Check if user already exists
print_info "Checking if user already exists..."
if aws cognito-idp admin-get-user \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --region "$REGION" &> /dev/null; then
    print_warning "User '$USERNAME' already exists. Skipping user creation."
    USER_EXISTS=true
else
    print_info "User does not exist. Creating new user..."
    USER_EXISTS=false
fi

# Step 2: Create user if it doesn't exist
if [ "$USER_EXISTS" = false ]; then
    print_info "Creating user '$USERNAME'..."
    aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "$USERNAME" \
        --temporary-password "$PASSWORD" \
        --message-action SUPPRESS \
        --region "$REGION" > /dev/null

    if [ $? -eq 0 ]; then
        print_info "User created successfully"
    else
        print_error "Failed to create user"
        exit 1
    fi

    # Step 3: Set permanent password
    print_info "Setting permanent password..."
    aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "$USERNAME" \
        --password "$PASSWORD" \
        --permanent \
        --region "$REGION" > /dev/null

    if [ $? -eq 0 ]; then
        print_info "Password set successfully"
    else
        print_error "Failed to set password"
        exit 1
    fi
else
    # If user exists, try to update password
    print_info "Updating password for existing user..."
    aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "$USERNAME" \
        --password "$PASSWORD" \
        --permanent \
        --region "$REGION" > /dev/null 2>&1 || true
fi

# Step 4: Generate bearer token
print_info "Generating bearer token..."
AUTH_RESPONSE=$(aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "$CLIENT_ID" \
    --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
    --region "$REGION" \
    --output json)

if [ $? -ne 0 ]; then
    print_error "Failed to generate bearer token"
    print_error "Make sure the password is correct and the user is confirmed"
    exit 1
fi

# Extract tokens
ACCESS_TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"AccessToken": *"[^"]*"' | sed 's/"AccessToken": *"\(.*\)"/\1/')
ID_TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"IdToken": *"[^"]*"' | sed 's/"IdToken": *"\(.*\)"/\1/')
REFRESH_TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"RefreshToken": *"[^"]*"' | sed 's/"RefreshToken": *"\(.*\)"/\1/')
EXPIRES_IN=$(echo "$AUTH_RESPONSE" | grep -o '"ExpiresIn": *[0-9]*' | sed 's/"ExpiresIn": *\([0-9]*\)/\1/')

if [ -z "$ACCESS_TOKEN" ]; then
    print_error "Failed to extract access token from response"
    exit 1
fi

# Calculate expiration time
EXPIRES_AT=$(date -u -v+${EXPIRES_IN}S +"%Y-%m-%d %H:%M:%S UTC" 2>/dev/null || date -u -d "+${EXPIRES_IN} seconds" +"%Y-%m-%d %H:%M:%S UTC" 2>/dev/null || echo "Unknown")

# Print success message and outputs
echo ""
print_info "✓ Test user setup completed successfully!"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "                    COGNITO CONFIGURATION"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "User Pool ID:     $USER_POOL_ID"
echo "Client ID:        $CLIENT_ID"
echo "Discovery URL:    $DISCOVERY_URL"
echo "Username:         $USERNAME"
echo "Region:           $REGION"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "                    AUTHENTICATION TOKENS"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Access Token (Bearer Token):"
echo "$ACCESS_TOKEN"
echo ""
echo "ID Token:"
echo "$ID_TOKEN"
echo ""
echo "Refresh Token:"
echo "$REFRESH_TOKEN"
echo ""
echo "Token Expires In: ${EXPIRES_IN} seconds (${EXPIRES_AT})"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "                    CHATGPT CONNECTOR SETUP"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "1. Open ChatGPT Settings → Connectors"
echo "2. Add a new connector with the AgentCore Invocation URL"
echo "3. Configure OAuth 2.0 authentication:"
echo "   - Discovery URL: $DISCOVERY_URL"
echo "   - Client ID: $CLIENT_ID"
echo "4. When prompted, use these credentials:"
echo "   - Username: $USERNAME"
echo "   - Password: $PASSWORD"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "                    ENVIRONMENT VARIABLES"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "# Export these for easy reuse:"
echo "export USER_POOL_ID=\"$USER_POOL_ID\""
echo "export CLIENT_ID=\"$CLIENT_ID\""
echo "export DISCOVERY_URL=\"$DISCOVERY_URL\""
echo "export USERNAME=\"$USERNAME\""
echo "export ACCESS_TOKEN=\"$ACCESS_TOKEN\""
echo "export REGION=\"$REGION\""
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Save tokens to a file for easy access
TOKEN_FILE="cognito_tokens_${USERNAME}.txt"
cat > "$TOKEN_FILE" << EOF
# Cognito Test User Tokens
# Generated: $(date)
# Expires: ${EXPIRES_AT}

USER_POOL_ID=$USER_POOL_ID
CLIENT_ID=$CLIENT_ID
DISCOVERY_URL=$DISCOVERY_URL
USERNAME=$USERNAME
REGION=$REGION

ACCESS_TOKEN=$ACCESS_TOKEN
ID_TOKEN=$ID_TOKEN
REFRESH_TOKEN=$REFRESH_TOKEN
EXPIRES_IN=${EXPIRES_IN}
EOF

print_info "Tokens saved to: $TOKEN_FILE"
echo ""
print_warning "Note: Access tokens expire in ${EXPIRES_IN} seconds. Use the refresh token to obtain new tokens."
echo ""

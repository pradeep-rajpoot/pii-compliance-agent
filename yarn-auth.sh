#!/usr/bin/env bash

function auth_npm {
    command -v grep >/dev/null 2>&1 || { echo >&2 "grep is not installed. Aborting."; exit 1; }
    command -v aws >/dev/null 2>&1 || { echo >&2 "AWS-CLI is not installed. Aborting."; exit 1; }
    command -v okta-aws >/dev/null 2>&1 || { echo >&2 "okta-aws is not installed. See https://chegg.atlassian.net/wiki/x/GIZHw for installation instructions."; exit 1; }

    NPMRC_FILENAME=~/.npmrc

    if grep -q "chegg.jfrog.io" $NPMRC_FILENAME; then
        echo "Backing up .npmrc configuration"
        mv "$NPMRC_FILENAME" "${NPMRC_FILENAME}.old"
    fi

    if ! grep -q "^always-auth=true" $NPMRC_FILENAME; then
        echo "Configuring npm to always provide credentials"
        echo "always-auth=true" >> $NPMRC_FILENAME
    fi

    CODEARTIFACT_ACCOUNT_NAME="${CODEARTIFACT_ACCOUNT_NAME:-chegg-app-web1-nonprod}"
    CODEARTIFACT_ROLE_NAME="${CODEARTIFACT_ROLE_NAME:-EngSAMStandard}"
    CODEARTIFACT_PROFILE_NAME="${CODEARTIFACT_PROFILE_NAME:-codeartifact-user}"
    CODEARTIFACT_DOMAIN_OWNER="${CODEARTIFACT_DOMAIN_OWNER:-084139392869}"
    CODEARTIFACT_DOMAIN="${CODEARTIFACT_DOMAIN:-chegg}"
    CODEARTIFACT_REPOSITORY="${CODEARTIFACT_REPOSITORY:-js-chegg}"
    CODEARTIFACT_REGION="${CODEARTIFACT_REGION:-us-west-2}"

    echo ".: Authenticating to AWS :."
    printf " CODEARTIFACT_ACCOUNT_NAME %s\n" "$CODEARTIFACT_ACCOUNT_NAME"
    printf " CODEARTIFACT_ROLE_NAME    %s\n" "$CODEARTIFACT_ROLE_NAME"
    printf " CODEARTIFACT_PROFILE_NAME %s\n" "$CODEARTIFACT_PROFILE_NAME"


    if okta-aws "$CODEARTIFACT_ACCOUNT_NAME" "$CODEARTIFACT_ROLE_NAME" "$CODEARTIFACT_PROFILE_NAME"; then
        echo "AWS authentication successful"
    else
        echo "Failed to Authenticate with AWS, error: $?"
        echo "Make sure you have access to role $CODEARTIFACT_ROLE_NAME on the $CODEARTIFACT_ACCOUNT_NAME account"
        exit 1
    fi

    echo ".: Authenticating to CodeArtifact :."
    printf " CODEARTIFACT_DOMAIN       %s\n" "$CODEARTIFACT_DOMAIN"
    printf " CODEARTIFACT_REGION       %s\n" "$CODEARTIFACT_REGION"
    printf " CODEARTIFACT_REPOSITORY   %s\n" "$CODEARTIFACT_REPOSITORY"
    printf " CODEARTIFACT_DOMAIN_OWNER %s\n" "$CODEARTIFACT_DOMAIN_OWNER"

    if aws codeartifact login \
        --profile "$CODEARTIFACT_PROFILE_NAME" \
        --tool npm \
        --repository "$CODEARTIFACT_REPOSITORY" \
        --domain "$CODEARTIFACT_DOMAIN" \
        --domain-owner "$CODEARTIFACT_DOMAIN_OWNER" \
        --region "$CODEARTIFACT_REGION"; then

        echo "Authenticated to CodeArtifact"
    else
        echo "Failed to Authenticate with CodeArtifact, error: $?"
        exit 1
    fi
}

if [[ "$GITLAB_CI" != "true" && "$HOME" != "/kaniko/" ]]; then
    auth_npm
fi
#!/usr/bin/env python3
"""Render ALB ingress TLS annotations based on ACM availability."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render_ingress.py <ingress.yaml>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    acm_cert_arn = os.environ.get("ACM_CERT_ARN", "").strip()
    auth_mode = os.environ.get("AUTH_MODE", "basic").strip().lower()
    cognito_enabled = auth_mode == "cognito"
    cognito_user_pool_arn = os.environ.get("COGNITO_USER_POOL_ARN", "").strip()
    cognito_app_client_id = os.environ.get("COGNITO_APP_CLIENT_ID", "").strip()
    cognito_user_pool_domain = os.environ.get("COGNITO_USER_POOL_DOMAIN", "").strip()

    if cognito_enabled and not acm_cert_arn:
        print(
            "Cognito ALB authentication requires an ACM certificate and HTTPS.",
            file=sys.stderr,
        )
        return 1

    if cognito_enabled and not all(
        [cognito_user_pool_arn, cognito_app_client_id, cognito_user_pool_domain]
    ):
        print(
            "Cognito authentication is enabled but Cognito outputs are missing.",
            file=sys.stderr,
        )
        return 1

    output: list[str] = []
    skip_without_tls = (
        "alb.ingress.kubernetes.io/certificate-arn:",
        "alb.ingress.kubernetes.io/ssl-policy:",
        "alb.ingress.kubernetes.io/ssl-redirect:",
    )
    skip_without_cognito = (
        "alb.ingress.kubernetes.io/auth-type:",
        "alb.ingress.kubernetes.io/auth-scope:",
        "alb.ingress.kubernetes.io/auth-session-timeout:",
        "alb.ingress.kubernetes.io/auth-on-unauthenticated-request:",
        "alb.ingress.kubernetes.io/auth-idp-cognito:",
    )

    for line in path.read_text().splitlines():
        stripped = line.strip()

        if acm_cert_arn:
            if stripped.startswith("alb.ingress.kubernetes.io/certificate-arn:"):
                output.append(
                    f"    alb.ingress.kubernetes.io/certificate-arn: {acm_cert_arn}"
                )
                continue
        else:
            if stripped.startswith(skip_without_tls):
                continue

            if stripped.startswith("alb.ingress.kubernetes.io/listen-ports:"):
                output.append(
                    "    alb.ingress.kubernetes.io/listen-ports: '[{\"HTTP\":80}]'"
                )
                continue

            if stripped.startswith("# TLS"):
                output.append(
                    "    # HTTP only - set app_domain_name and Route 53 "
                    "in OpenTofu to enable HTTPS"
                )
                continue

        if not cognito_enabled and stripped.startswith(skip_without_cognito):
            continue

        if not cognito_enabled and stripped.startswith("# Cognito authentication"):
            output.append(
                "    # Cognito authentication disabled - set "
                "enable_cognito_auth=true with HTTPS to enable"
            )
            continue

        if cognito_enabled and stripped.startswith(
            "alb.ingress.kubernetes.io/auth-idp-cognito:"
        ):
            output.append(
                "    alb.ingress.kubernetes.io/auth-idp-cognito: "
                f'\'{{"userPoolARN":"{cognito_user_pool_arn}",'
                f'"userPoolClientID":"{cognito_app_client_id}",'
                f'"userPoolDomain":"{cognito_user_pool_domain}"}}\''
            )
            continue

        if cognito_enabled and stripped.startswith("# Cognito authentication"):
            output.append(
                "    # Cognito authentication enabled - users are authorized by gateway role groups"
            )
            continue

        output.append(line)

    if not acm_cert_arn:
        print("No ACM certificate ARN found; rendering HTTP-only ALB ingress.")

    path.write_text("\n".join(output) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

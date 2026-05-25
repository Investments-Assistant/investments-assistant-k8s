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

    output: list[str] = []
    skip_without_tls = (
        "alb.ingress.kubernetes.io/certificate-arn:",
        "alb.ingress.kubernetes.io/ssl-policy:",
        "alb.ingress.kubernetes.io/ssl-redirect:",
    )

    for line in path.read_text().splitlines():
        stripped = line.strip()

        if acm_cert_arn:
            if stripped.startswith("alb.ingress.kubernetes.io/certificate-arn:"):
                output.append(
                    f"    alb.ingress.kubernetes.io/certificate-arn: {acm_cert_arn}"
                )
                continue
            output.append(line)
            continue

        if stripped.startswith(skip_without_tls):
            continue

        if stripped.startswith("alb.ingress.kubernetes.io/listen-ports:"):
            output.append(
                "    alb.ingress.kubernetes.io/listen-ports: '[{\"HTTP\":80}]'"
            )
            continue

        if stripped.startswith("# TLS"):
            output.append(
                "    # HTTP only - set app_domain_name and a Route 53 zone in Terraform to enable HTTPS"
            )
            continue

        output.append(line)

    if not acm_cert_arn:
        print("No ACM certificate ARN found; rendering HTTP-only ALB ingress.")

    path.write_text("\n".join(output) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

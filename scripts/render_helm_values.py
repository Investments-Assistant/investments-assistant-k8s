#!/usr/bin/env python3
"""Render local Helm values files from OpenTofu outputs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def tf_value(outputs: dict[str, object], name: str) -> str:
    item = outputs.get(name, {})
    if not isinstance(item, dict):
        return ""
    value = item.get("value", "")
    if value is None:
        return ""
    return str(value).strip()


def required(name: str, value: str) -> str:
    if value:
        return value
    print(f"Missing OpenTofu output required for Helm values: {name}", file=sys.stderr)
    raise SystemExit(1)


def render_file(path: Path, replacements: dict[str, str]) -> None:
    text = path.read_text()
    for key, value in replacements.items():
        text = text.replace(key, value)
    if "REPLACE_WITH_" in text:
        print(f"Rendered Helm values still contain placeholders: {path}", file=sys.stderr)
        raise SystemExit(1)
    path.write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    if not source_dir.is_dir():
        print(f"Missing Helm values directory: {source_dir}", file=sys.stderr)
        return 1

    try:
        outputs = json.loads(os.environ.get("TF_OUTPUTS", "{}"))
    except json.JSONDecodeError as exc:
        print(f"Invalid TF_OUTPUTS JSON: {exc}", file=sys.stderr)
        return 1

    account = os.environ.get("AWS_ACCOUNT", "").strip()
    aws_region = os.environ.get("AWS_REGION", "").strip()
    cluster = required("cluster_name", tf_value(outputs, "cluster_name"))
    vpc_id = required("vpc_id", tf_value(outputs, "vpc_id"))
    efs_id = required("efs_id", tf_value(outputs, "efs_id"))

    efs_csi_role_arn = tf_value(outputs, "efs_csi_role_arn")
    albc_role_arn = tf_value(outputs, "aws_load_balancer_controller_role_arn")
    if not efs_csi_role_arn and account:
        efs_csi_role_arn = f"arn:aws:iam::{account}:role/{cluster}-efs-csi-role"
    if not albc_role_arn and account:
        albc_role_arn = f"arn:aws:iam::{account}:role/{cluster}-albc-role"

    replacements = {
        "REPLACE_WITH_CLUSTER_NAME": cluster,
        "REPLACE_WITH_AWS_REGION": required("AWS_REGION", aws_region),
        "REPLACE_WITH_VPC_ID": vpc_id,
        "REPLACE_WITH_EFS_ID": efs_id,
        "REPLACE_WITH_EFS_CSI_ROLE_ARN": required(
            "efs_csi_role_arn", efs_csi_role_arn
        ),
        "REPLACE_WITH_ALBC_ROLE_ARN": required(
            "aws_load_balancer_controller_role_arn", albc_role_arn
        ),
    }

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    value_files = sorted(source_dir.glob("*.y*ml"))
    if not value_files:
        print(f"No Helm values files found in {source_dir}", file=sys.stderr)
        return 1

    for source in value_files:
        target = output_dir / source.name
        shutil.copy2(source, target)
        render_file(target, replacements)

    print(f"Rendered Helm values to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

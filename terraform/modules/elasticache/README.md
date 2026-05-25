# ElastiCache Module

Creates a Redis replication group for shared runtime state.

## Resources

- `aws_elasticache_subnet_group.main`: subnet group using private subnets.
- `aws_security_group.redis`: allows Redis traffic from EKS worker nodes.
- `aws_elasticache_replication_group.main`: single-node Redis replication group.

The Redis node type defaults to `cache.t3.micro`, uses at-rest encryption, and
enables transit encryption when `auth_token` is set. Override `node_type` if the
target region or capacity plan requires a different supported cache node type.

## Inputs

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `cluster_name` | `string` | Yes | Prefix for Redis resource names. |
| `vpc_id` | `string` | Yes | VPC where the Redis security group is created. |
| `private_subnet_ids` | `list(string)` | Yes | Private subnets for the Redis subnet group. |
| `eks_node_sg_id` | `string` | Yes | EKS node security group allowed to connect to Redis. |
| `node_type` | `string` | No | ElastiCache node type. Defaults to `cache.t3.micro`. |
| `auth_token` | `string` | No | Optional Redis auth token. Blank strings are treated as disabled. Valid values must be 16-128 characters and cannot contain `@`, `"`, or `/`. Marked sensitive. |

## Outputs

| Name | Description |
| --- | --- |
| `endpoint` | Redis primary endpoint address. |
| `port` | Redis port, currently `6379`. |

## Used By

The gateway stores runtime trading mode in Redis. The portfolio service reads
that mode so trade execution behavior is consistent across services.

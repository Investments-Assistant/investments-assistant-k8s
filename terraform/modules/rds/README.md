# RDS Module

Creates an Aurora PostgreSQL Serverless v2 database for service-owned tables.

## Resources

- `aws_db_subnet_group.main`: subnet group using private subnets.
- `aws_security_group.rds`: allows PostgreSQL traffic from EKS worker nodes.
- `aws_rds_cluster.main`: encrypted Aurora PostgreSQL cluster.
- `aws_rds_cluster_instance.writer`: serverless writer instance.

The cluster uses PostgreSQL port `5432`, deletion protection, a final snapshot
on destroy, and serverless v2 capacity from 0.5 to 4 ACUs. The engine version
defaults to `null`, which lets AWS choose a valid regional default; pin
`engine_version` only when you have confirmed the target region supports it.

## Inputs

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `cluster_name` | `string` | Yes | Prefix for RDS resource names. |
| `vpc_id` | `string` | Yes | VPC where the RDS security group is created. |
| `private_subnet_ids` | `list(string)` | Yes | Private subnets for the DB subnet group. |
| `eks_node_sg_id` | `string` | Yes | EKS node security group allowed to connect to PostgreSQL. |
| `db_name` | `string` | Yes | Initial database name. |
| `db_username` | `string` | Yes | Master database username. |
| `db_password` | `string` | Yes | Master database password. Marked sensitive. |
| `engine_version` | `string` | No | Optional Aurora PostgreSQL engine version. Defaults to `null` for AWS regional default selection. |

## Outputs

| Name | Description |
| --- | --- |
| `endpoint` | Aurora cluster writer endpoint. |
| `port` | Aurora cluster port. |

## Used By

Application services read `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
`POSTGRES_USER`, and `POSTGRES_PASSWORD` from Kubernetes configuration and
secrets. The gateway, news, portfolio, simulation, and scheduler services create
their own tables at startup.

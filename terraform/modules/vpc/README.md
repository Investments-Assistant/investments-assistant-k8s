# VPC Module

Creates the network foundation for the EKS cluster and private data services.

## Resources

- `aws_vpc.main`: VPC using CIDR `10.0.0.0/16`.
- `aws_internet_gateway.main`: internet gateway for public subnets.
- `aws_subnet.public`: one public subnet per input availability zone.
- `aws_subnet.private`: one private subnet per input availability zone.
- `aws_eip.nat`: elastic IP for the NAT gateway.
- `aws_nat_gateway.main`: NAT gateway in the first public subnet.
- `aws_route_table.public`: public route table.
- `aws_route.public_internet`: `0.0.0.0/0` route through the internet gateway.
- `aws_route_table_association.public`: public subnet associations.
- `aws_route_table.private`: private route table.
- `aws_route.private_nat`: `0.0.0.0/0` route through the NAT gateway.
- `aws_route_table_association.private`: private subnet associations.

The subnets are tagged for AWS Load Balancer Controller discovery:
`kubernetes.io/role/elb` for public subnets and
`kubernetes.io/role/internal-elb` for private subnets.

## Inputs

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `cluster_name` | `string` | Yes | EKS cluster name used in resource names and Kubernetes discovery tags. |
| `azs` | `list(string)` | Yes | Availability zones where public and private subnets are created. |

## Outputs

| Name | Description |
| --- | --- |
| `vpc_id` | ID of the created VPC. |
| `public_subnet_ids` | IDs of the public subnets. |
| `private_subnet_ids` | IDs of the private subnets. |

## Used By

The root stack passes this module's VPC and private subnet outputs to the EKS,
RDS, and ElastiCache modules.

aws_region           = "ap-northeast-1"
project_name         = "order-automation-poc"
environment          = "dev"

vpc_id               = "vpc-05a8d8a4320c28161"
public_subnet_ids    = ["subnet-0375aaa1f6bf8ae91", "subnet-04391eb5a544c4471", "subnet-0dfe6342647a6fdab"]
private_subnet_ids   = ["subnet-0375aaa1f6bf8ae91", "subnet-04391eb5a544c4471", "subnet-0dfe6342647a6fdab"]
db_subnet_ids        = ["subnet-0375aaa1f6bf8ae91", "subnet-04391eb5a544c4471", "subnet-0dfe6342647a6fdab"]

allowed_ingress_cidr = "0.0.0.0/0"

desired_count        = 0
worker_desired_count = 0
assign_public_ip     = true
container_cpu        = 1024
container_memory     = 2048
worker_cpu           = 1024
worker_memory        = 2048

db_instance_class    = "db.t4g.micro"
db_allocated_storage = 20

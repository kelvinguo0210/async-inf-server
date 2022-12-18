variable region {
 default = "us-east-1"
}

variable repo_name {
 default = "sagemaker-kwm-apigw"
}

variable stage_vars{
 type = map
 default = {
   "s3_bucket" = "sagemaker-studio-models"
   "white_list" = "sagemaker-kwm-deberta-inf"
   "role_arn" = "arn:aws:iam::405496568869:role/service-role/AmazonSageMaker-ExecutionRole-20221104T162296"
   "limit" = 1
 }
}


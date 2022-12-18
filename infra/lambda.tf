locals {
 repo_name = var.repo_name
 ecr_repository_name = "${local.repo_name}"
 ecr_image_tag       = "latest"
}
 
data aws_ecr_image lambda_image {
 repository_name = local.ecr_repository_name
 image_tag       = local.ecr_image_tag
}

data "aws_ecr_repository" "ecr_repo" {
  name = "${local.repo_name}"
}
 
resource aws_iam_role lambda_role {
 name = "${local.repo_name}-lambda-role"
 assume_role_policy = <<EOF
{
   "Version": "2012-10-17",
   "Statement": [
       {
           "Action": "sts:AssumeRole",
           "Principal": {
               "Service": "lambda.amazonaws.com"
           },
           "Effect": "Allow"
       }
   ]
}
 EOF
 
 //managed_policy_arns = [aws_iam_policy.lambda.arn]
}

resource aws_iam_policy policy_lambda {
   name = "${local.repo_name}-lambda-policy"
   path = "/"
   //policy = data.aws_iam_policy_document.lambda.json
   policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": [
        "s3:*"
      ],
      "Effect": "Allow",
      "Resource": "*"
    },
    {
      "Action": [
        "lambda:*"
      ],
      "Effect": "Allow",
      "Resource": "*"
    },
    {
      "Action": [
        "logs:*"
      ],
      "Effect": "Allow",
      "Resource": "*"
    },
    {
      "Action": [
        "sagemaker:*"
      ],
      "Effect": "Allow",
      "Resource": "*"
    },
    {
      "Action": [
        "dynamodb:*"
      ],
      "Effect": "Allow",
      "Resource": "*"
    },    
    {
      "Effect": "Allow",
       "Action": [
            "iam:PassRole"
        ],
        "Resource": "arn:aws:iam::*:role/*",
        "Condition": {
            "StringEquals": {
               "iam:PassedToService": "sagemaker.amazonaws.com"
            }
        }
    }    
  ]
}
 EOF

}

resource "aws_iam_role_policy_attachment" "policy_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.policy_lambda.arn
}

resource "aws_cloudwatch_log_group" "log_group" {
  name = "/aws/lambda/${aws_lambda_function.kwm-inf-gateway-lambda.function_name}"

  retention_in_days = 30
}

resource aws_lambda_function kwm-inf-gateway-lambda {
 function_name = "${local.repo_name}-lambda"
 role = aws_iam_role.lambda_role.arn
 timeout = 300
 image_uri = "${data.aws_ecr_repository.ecr_repo.repository_url}@${data.aws_ecr_image.lambda_image.id}"
 package_type = "Image"
}

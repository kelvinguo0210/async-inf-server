resource "aws_apigatewayv2_api" "apigw_lambda" {
  name          = "serverless_lambda_gw"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "apigw_lambda" {
  api_id = aws_apigatewayv2_api.apigw_lambda.id

  name        = "serverless_lambda_stage"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gw.arn

    format = jsonencode({
      requestId               = "$context.requestId"
      sourceIp                = "$context.identity.sourceIp"
      requestTime             = "$context.requestTime"
      protocol                = "$context.protocol"
      httpMethod              = "$context.httpMethod"
      resourcePath            = "$context.resourcePath"
      routeKey                = "$context.routeKey"
      status                  = "$context.status"
      responseLength          = "$context.responseLength"
      integrationErrorMessage = "$context.integrationErrorMessage"
      }
    )
  }
  
  stage_variables = var.stage_vars
}

resource "aws_apigatewayv2_integration" "kigw_lambda_integration" {
  api_id = aws_apigatewayv2_api.apigw_lambda.id

  integration_uri    = aws_lambda_function.kwm-inf-gateway-lambda.invoke_arn
  integration_type   = "AWS_PROXY"
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "kigw_lambda_route" {
  api_id = aws_apigatewayv2_api.apigw_lambda.id

  route_key = "POST /inference"
  target    = "integrations/${aws_apigatewayv2_integration.kigw_lambda_integration.id}"
}

resource "aws_cloudwatch_log_group" "api_gw" {
  name = "/aws/api_gw/${aws_apigatewayv2_api.apigw_lambda.name}"

  retention_in_days = 30
}

resource "aws_lambda_permission" "api_gw_perm" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.kwm-inf-gateway-lambda.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.apigw_lambda.execution_arn}/*/*"
}
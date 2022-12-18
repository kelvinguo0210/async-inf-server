import logging
import os
import json
from datetime import datetime
import sagemaker
from sagemaker.estimator import Estimator
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

account = boto3.client('sts').get_caller_identity().get('Account')
session = boto3.session.Session()
region = session.region_name 
if 'cn-north' in region:
    partition = '.cn'
else:
    partition = ''
    
LOGGER.info('account Id : %s', account)
LOGGER.info('region : %s', region)   

table_name = 'async-inf-jobs'
default_jobs_limit =1
default_inst_count = 1
default_inst_type = "ml.g4dn.xlarge"
default_white_list = 'kwm-model-a, kwm-model-b'
default_s3_bucket = 'sagemaker-studio-models' 
default_role_arn = 'arn:aws:iam::1234123412341234:role/service-role/AmazonSageMaker-ExecutionRole-xxxx'


class Jobs:
    def __init__(self, dyn_resource):
        self.dyn_resource = dyn_resource
        self.table = None

    def exists(self, table_name):
        try:
            table = self.dyn_resource.Table(table_name)
            table.load()
            exists = True
        except ClientError as err:
            if err.response['Error']['Code'] == 'ResourceNotFoundException':
                exists = False
            else:
                logger.error(
                    "Couldn't check for existence of %s. Here's why: %s: %s",
                    table_name,
                    err.response['Error']['Code'], err.response['Error']['Message'])
                raise
        else:
            self.table = table
        return exists

    
    def create_table(self, table_name):
        try:
            self.table = self.dyn_resource.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'job_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'job_id', 'AttributeType': 'S'}
                ],
                ProvisionedThroughput={'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10})
            self.table.wait_until_exists()
        except ClientError as err:
            logger.error(
                "Couldn't create table %s. Here's why: %s: %s", table_name,
                err.response['Error']['Code'], err.response['Error']['Message'])
            raise
        else:
            return self.table

    def add_job(self, job_id):
        try:
            self.table.put_item(
                Item={'job_id': job_id})
        except ClientError as err:
            logger.error(
                "Couldn't add job %s to table %s. Here's why: %s: %s",
                job_id, self.table.name,
                err.response['Error']['Code'], err.response['Error']['Message'])
            raise

            
    def get_job(self, job_id):
        try:
            response = self.table.get_item(Key={'job_id': job_id})
            #print(response)
        except ClientError as err:
            logger.error(
                "Couldn't get job %s from table %s. Here's why: %s: %s",
                title, self.table.name,
                err.response['Error']['Code'], err.response['Error']['Message'])
            raise
        else:
            return response.get('Item')


def checkLimit(jobPrefix='TrainAsInf', limit=1):
    sm = boto3.client('sagemaker') 
    resp = sm.list_training_jobs(MaxResults=100, StatusEquals='InProgress', NameContains=jobPrefix)
    #resp = sm.list_training_jobs(MaxResults=100, StatusEquals='Completed' , NameContains=jobPrefix)
    jobs = resp['TrainingJobSummaries']
    return {'available':limit-len(jobs), 'limit': limit}

def scheduleJob(role_arn=default_role_arn, s3_bucket=default_s3_bucket, jobPrefix='', container='', limit=1, instance_count=1, instance_type=default_inst_type):  
    training_data_s3_uri = f's3://{s3_bucket}/data/'
    output_folder_s3_uri = f's3://{s3_bucket}/output/'
    source_folder = f's3://{s3_bucket}/source-folders'
    base_job_name = f'{jobPrefix}-job-{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}'

    sm_estimator = Estimator(
        image_uri=container,
        role=role_arn,
        instance_count=instance_count,
        instance_type=instance_type,
        output_path=output_folder_s3_uri,
        code_location=source_folder,
        base_job_name=base_job_name,
        hyperparameters={},
        environment={},
        tags=[{"Key": "email",
               "Value": "kguoaws@amazon.com"}])

    sm_estimator.fit( {'training-data': training_data_s3_uri}, wait=False )
    training_job_name = sm_estimator.latest_training_job.name
    LOGGER.info('Starting training job : %s', training_job_name)

def checkJobStatus(detail={}):
    job_name = detail.get('TrainingJobName')
    job_status = detail.get('TrainingJobStatus')
    job_output = detail.get('OutputDataConfig').get('S3OutputPath')
    LOGGER.info('job_name: %s', job_name)
    LOGGER.info('job_status: %s', job_status)
    LOGGER.info('job_output: %s', job_output)
 
    ddb = boto3.resource('dynamodb')
    jobs = Jobs(ddb)
    jobs_exist = jobs.exists(table_name)
    if not jobs_exist:
        jobs.create_table(table_name)
        
    job = jobs.get_job(job_name)
    if (not job) and (job_status=='Completed'):
        jobs.add_job(job_name)
        ## send eamil
        ## trigger sns with sdk
        LOGGER.info('******* fire ses for job_name: %s', job_name)
    else:
        LOGGER.info('ignore fire ses for job_name: %s', job_name)
    
    return {'job_name':job_name, 'job_status':job_status, 'job_output':job_output}
    
def makeResp(errCode=200, errMsg=''):
    return {
        "statusCode": errCode,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({'status':errCode, 'errMsg': errMsg})          
    }
    
def handler(event, context):
    LOGGER.info('Event: %s', event)
    #LOGGER.info('Body: %s', event['body'])
    
    detail = event.get('detail')
    LOGGER.info('detail: %s', detail)
    if detail:
        chkResult = checkJobStatus( detail=detail )
        LOGGER.info('limit: %s', chkResult)  
        errMsg = 'dummy msg'
        return makeResp(errCode=200, errMsg=errMsg) 
    else:
        LOGGER.info('detail is None')  
        pass
    
    payload = json.loads(event['body'])
    if len(payload):
        stage_vars = event['stageVariables']
        s3_bucket = stage_vars.get('s3_bucket', default_s3_bucket)
        white_list = stage_vars.get('white_list', default_white_list)
        role_arn = stage_vars.get('role_arn', default_role_arn)
        limit = stage_vars.get('limit', default_jobs_limit)
    
        LOGGER.info('s3_bucket: %s', s3_bucket)
        LOGGER.info('white_list: %s', white_list)
        LOGGER.info('role_arn: %s', role_arn)
        LOGGER.info('limit: %s', limit)   

        
        jobPrefix = payload['type']
        LOGGER.info('imcoming inf type: %s', jobPrefix)
        if len(jobPrefix):
            if not jobPrefix in white_list.split(','):
                errMsg = f'The type [{jobPrefix}]  of inference request is NOT supported.'
                return makeResp(errCode=510, errMsg=errMsg)                
            ret = checkLimit(jobPrefix=jobPrefix, limit=default_jobs_limit)
            ava = ret['available']
            if ava > 0:
                LOGGER.info('check limit: %s', ret)
                container = f'{account}.dkr.ecr.{region}.amazonaws.com{partition}/{jobPrefix}:latest'
                LOGGER.info('containter : %s', container) 
                inst_count = payload.get('instance_count', default_inst_count)
                LOGGER.info('inst count : %s', inst_count) 
                inst_type = payload.get('instance_type', default_inst_type)                
                LOGGER.info('inst type : %s', inst_type) 
                
                jobName = scheduleJob(role_arn=role_arn, s3_bucket=s3_bucket, jobPrefix=jobPrefix, container=container, limit=default_jobs_limit, instance_count=inst_count, instance_type=inst_type)
                errMsg = f'A new job [{jobName}] was scheduled successfully, and {default_jobs_limit - ava} slots reminded.'
                return makeResp(errCode=200, errMsg=errMsg)
            else:
                LOGGER.error('Limit: %s', ret)
                errMsg = f'Failed to schedule inference at the moment, due to limit {default_jobs_limit} got reached.'                 
                return makeResp(errCode=502, errMsg=errMsg)            
            
    else:
        errMsg = 'missing "type" in your request, please check and try again.'
        return makeResp(errCode=501, errMsg=errMsg) 

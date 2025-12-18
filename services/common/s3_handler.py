import boto3
import os
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class S3Handler:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )

    def upload_file(self, file_path, object_name=None):
        if object_name is None:
            object_name = os.path.basename(file_path)
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, object_name)
            logger.info(f"File {file_path} uploaded to {self.bucket_name}/{object_name}")
            return True
        except ClientError as e:
            logger.error(e)
            return False

    def download_file(self, object_name, file_path):
        try:
            self.s3_client.download_file(self.bucket_name, object_name, file_path)
            logger.info(f"File {object_name} downloaded from {self.bucket_name} to {file_path}")
            return True
        except ClientError as e:
            logger.error(e)
            return False

    def get_signed_url(self, object_name, expiration=3600):
        try:
            response = self.s3_client.generate_presigned_url('get_object',
                                                            Params={'Bucket': self.bucket_name,
                                                                    'Key': object_name},
                                                            ExpiresIn=expiration)
            return response
        except ClientError as e:
            logger.error(e)
            return None

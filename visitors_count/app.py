import json
import boto3

dynamodb = boto3.resource('dynamodb', 'us-east-1')
table = dynamodb.Table('cloud-resume-challenge')


def visitors_count(event, context):
    response = table.update_item(Key={'ID': 'visitors'},
                                 AttributeUpdates={'visitors': {'Value': 1, 'Action': 'ADD'}},
                                 ReturnValues='UPDATED_NEW')

    body = {"visitors": str(response['Attributes']['visitors'])}

    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }





import json
import boto3

# Get the dynamodb table
dynamodb = boto3.resource('dynamodb', 'us-east-1')
table = dynamodb.Table('cloud-resume-challenge')


def visitors_count(event, context):
    # Adding 1 to the visitor item count
    response = table.update_item(Key={'ID': 'visitors'},
                                 AttributeUpdates={'visitors': {'Value': 1, 'Action': 'ADD'}},
                                 ReturnValues='UPDATED_NEW')
    # Get the item
    body = {"visitors": str(response['Attributes']['visitors'])}

    # Return a json response with the count in body
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }





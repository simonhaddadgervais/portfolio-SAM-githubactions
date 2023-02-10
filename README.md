# The Project

### This project aims to create a serverless portfolio website, with AWS.

To create this website, I'm going to use:

AWS ressources :
- IAM
- S3
- Lambda
- APIGateway
- DynamoDB
- CloudFormation
- ACM
- Route53
- Cloudfront
- SAM CLI

Program Languages:
- Python
- Javascript
- HTML
- CSS

- PyCharm as IDE
- Git as VSC
- Github Actions for CI/CD


I start by setting up [vault](https://github.com/99designs/aws-vault) to store my credentials

    * `aws-vault add my-user`


- Setup the [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)
    - `sam init`
    - `sam build`
- Add IAM permissions for SAM
    - CloudFormation
    - IAM
    - Lambda
    - S3
    - API Gateway
- Deploy SAM
    - `aws-vault exec my-user --no-session -- sam deploy --guided`

I can add to the SAM template the ressources I need:

A bucket to store my files, with policy to allow public access
```yml
   MyWebsite:
    Type: AWS::S3::Bucket
    Properties:
      AccessControl: PublicRead
      WebsiteConfiguration:
          IndexDocument: index.html
      BucketName: simonresume
  BucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      PolicyDocument:
        Id: MyPolicy
        Version: 2012-10-17
        Statement:
          - Sid: PublicReadForGetBucketObjects
            Effect: Allow
            Principal: "*"
            Action: "s3:GetObject"
            Resource: !Join
              - ""
              - - "arn:aws:s3:::"
                - !Ref MyWebsite
                - /*
      Bucket: !Ref MyWebsite
```

I add a Cloudfront distribution pointing to my bucket static website address:

```yml
  MyDistribution:
    Type: "AWS::CloudFront::Distribution"
    Properties:
      DistributionConfig:
        DefaultCacheBehavior:
          ViewerProtocolPolicy: allow-all
          TargetOriginId: simonresume.s3-website-us-east-1.amazonaws.com
          DefaultTTL: 0
          MinTTL: 0
          MaxTTL: 0
          ForwardedValues:
            QueryString: false
        Origins:
          - DomainName: simonresume.s3-website-us-east-1.amazonaws.com
            Id: simonresume.s3-website-us-east-1.amazonaws.com
            CustomOriginConfig:
              OriginProtocolPolicy: http-only
        Enabled: "true"
        DefaultRootObject: index.html
```

Then I a point my custom DNS to my Cloudfront distribution:
```yml
  MyRoute53Record:
    Type: "AWS::Route53::RecordSetGroup"
    Properties:
      HostedZoneId: Z0513579U6CHH2XQNOAD
      RecordSets:
        - Name: simonhaddadgervais.com
          Type: A
          AliasTarget:
            HostedZoneId: Z2FDTNDATAQYW2
            DNSName: !GetAtt MyDistribution.DomainName
```
*
Now to serve secure content I need a HTTPS certificate so I'm going to use ACM to request a certificate :
```yml
  MyCertificate:
    Type: AWS::CertificateManager::Certificate
    Properties:
      DomainName: simonhaddadgervais.com
      ValidationMethod: DNS
```

*
I use DNS validation, and I want this certificate to apply to my domain name. 
I also need to attach that certificate to my Cloudfront distribution, so I add to the distribution part in the template:
```yml
  # MyDistribution:
    # Properties:
      # DistributionConfig:
        ViewerCertificate:
            AcmCertificateArn: !Ref MyCertificate
            SslSupportMethod: sni-only
```


At that point, the sam deploy get stuck on validating the certificate so I figure I need to do it manually. I go to ACM and press "create a record in Route53"
to unlock this issue. It works and a record is created in Route53, and deployment finishes running.
*
I still can't access my distribution through my custom domain, so I need to allow this access, by adding this line to my distribution setup:



```yml
   # MyDistribution:
    # Properties:
      # DistributionConfig:
        # ViewerCertificate:
          # AcmCertificateArn: !Ref MyCertificate
          # SslSupportMethod: sni-only
          Aliases:
          - simonhaddadgervais.com
```

Now the frontend part is done and the website is working.
I want to implement a function that counts the number of visitors on my website, and returns that number.
For that I'm going to use Lambda for the function, DynamoDB to store the data and APIGateway to access that data from my website.

I create a dynamoDB table through SAM, adding to the template a new ressource :
```yaml
  DynamoDBTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: cloud-resume-challenge
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: "ID"
          AttributeType: "S"
      KeySchema:
        - AttributeName: "ID"
          KeyType: "HASH"
```
*
The function is written in Python. Import the AWS SDK boto3, it's gonna get our table, update it by adding 1 to our 'visitor' attribute, and then return a json response containing our visitor count: 

```py
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
```
*
I create a Lambda function on the template. The first time I forgot to add the permission for Lambda to access DynamoDB. After figuring it out, it looks like this :
```yaml
  VisitCountFunction:
    Type: AWS::Serverless::Function
    Properties:
      Policies:
        - DynamoDBCrudPolicy:
            TableName: cloud-resume-challenge
      CodeUri: visitors_count/
      Handler: app.visitors_count
      Runtime: python3.9
      Architectures:
        - x86_64
      Events:
        Visits:
          Type: Api
          Properties:
            Path: /visitors_count
            Method: get
```

`sam build && aws-vault exec USER --no-session -- sam deploy`

Everything is working like a charm, but everytime I update my code, or my html files, I need to manually open the command line and type use SAM to build and deploy...

So I'm gonna implement CI/CD to automate that process, using Github Actions

First, I want my function to be tested before anything is deployed. I'm using pytest and mock_dynamodb from moto to mock a dynamoDB table for my test.
I keep as the event for my test function the API event from the base test_helloworld function that came from SAM when I used `sam init`.
Then I create the test function.
This was the hardest part for me, as I was struggling using moto. The test function was trying to call my real table and I had to find help on StackOverflow to find out
I needed my mock table to be exactly identical to my real one.
I fixed it and it worked. I could locally pytest my function with success.

The final test looks like :
```py
import json
import boto3
import pytest
from moto import mock_dynamodb


# API event here


@mock_dynamodb
def test_visitors_count(apigw_event, mocker):
    from visitors_count import app
    table_name = 'cloud-resume-challenge'
    # Create mock DynamoDB table
    dynamodb = boto3.resource('dynamodb', 'us-east-1')
    table = dynamodb.create_table(
        TableName=table_name,
        KeySchema=[{'AttributeName': 'ID', 'KeyType': 'HASH'}],
        AttributeDefinitions=[{'AttributeName': 'ID', 'AttributeType': 'S'}],
        ProvisionedThroughput={'ReadCapacityUnits': 2, 'WriteCapacityUnits': 1}
    )

    ret = app.visitors_count(apigw_event, "")
    data = json.loads(ret["body"])

    assert ret["statusCode"] == 200
    assert data == {"visitors": "1"}
```

Now I implement it to Github actions, creating a ".github/workflows" directory and inside a yml file to tell Github Actions what to do

I want it to test my function everytime I push a commit. My AWS credentials are stored as secrets:
```yml
name: test build deploy
on: push

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python 3.8
      uses: actions/setup-python@v4
      with:
        python-version: "3.8"
    - run: pip install -r requirements.txt
    - name: Test with pytest
      env:
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      run: pytest
```
Then, a `sam build` and `sam deploy` once the test is done and successful :

```yml
  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.9"
      - uses: aws-actions/setup-sam@v1
      - uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - run: sam build
      - run: sam deploy --no-confirm-changeset --no-fail-on-empty-changeset
```

Finally, I also want my website files to be updated, and the old ones deleted, so I need to update my bucket as well:
```yml
  deploy-site:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: jakejarvis/s3-sync-action@master
        with:
          args: --delete
        env:
          AWS_S3_BUCKET: simonresume
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          SOURCE_DIR: resume-site
```


![resume-design](https://user-images.githubusercontent.com/100123312/218184031-6d36e1a6-6e3b-41ba-8476-a5116423ec61.png)

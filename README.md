
### This project aims to create a serverless portfolio website, with AWS.

To create this website, I used:

#### AWS resources :
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

#### Program Languages:
- Python
- Javascript
- HTML
- CSS

#### And
- PyCharm as IDE
- Git as VSC
- Github Actions for CI/CD

## Initializing 
I started by setting up [vault](https://github.com/99designs/aws-vault) to store my credentials

`aws-vault add USER`


Then [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)

`sam init`

`sam build`


I added IAM permissions to my user:

* CloudFormation
* IAM
* Lambda
* S3
* APIGateway

And I deployed SAM:
    - `aws-vault exec USER --no-session -- sam deploy --guided`

After that I could step by step add the resources I needed to the SAM template.

Between each new resource I added, I ran `sam build && aws-vault exec USER --no-session -- sam deploy`.
If it ran without error, I kept adding resources.

### BACKEND

So, first I needed a bucket to store my files, with a policy to allow public access read
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

I added a Cloudfront distribution pointing to my bucket static website address:

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

Then I a pointed my custom DNS to my Cloudfront distribution:
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
To serve secure content I needed a HTTPS certificate so I used ACM to request one :
```yml
  MyCertificate:
    Type: AWS::CertificateManager::Certificate
    Properties:
      DomainName: simonhaddadgervais.com
      ValidationMethod: DNS
```

*
I used DNS validation, and I wanted this certificate to apply to my domain name. 
I also needed to attach that certificate to my Cloudfront distribution,
so I added to the distribution part in the template:
```yml
  # MyDistribution:
    # Properties:
      # DistributionConfig:
        ViewerCertificate:
            AcmCertificateArn: !Ref MyCertificate
            SslSupportMethod: sni-only
```


At that point, the deployment got stuck on validating the certificate,
so I figured I needed to do it manually.
I went to ACM and pressed `Create a record in Route53`to unlock this issue.
It worked and a record was created in Route53, and deployment successfully ended!
*
However, I still couldn't access my distribution through my custom domain,
so I needed to allow this access, by adding this line to my distribution setup:


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

The frontend part was done and the website was working!

### BACKEND

Part of the challenge was to implement a function that counts the number of visitors on my website, and returns that number.
For that I used **Lambda** for the function,
**DynamoDB** to store the data and **APIGateway** to access that data from my website.

I created a **DynamoDB** table through SAM template :
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
I wrote the function in **Python**. I imported the AWS SDK `boto3`, to get to my table,
update it by adding 1 to our 'visitor' attribute, and then return a json response containing my visitor count: 

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
I created a **Lambda** function on the template. 
The first time I forgot to add the permission for **Lambda** to access **DynamoDB**.
After figuring it out, it looks like this :
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

I added some **Javascript** on my html index file, so that loading the page fetches the API,
which calls the function I just created and adds 1 to the count.
It looks like this :
```
<script>
        fetch('https://xf5z9o0wwh.execute-api.us-east-1.amazonaws.com/Prod/visitors_count')
            .then(response => response.json())
            .then((data) => {
                document.getElementById('visitors').innerText = data.visitors
            })
    </script>
```
I also wanted to display that count on the website, so I added in a paragraph:

```
Visitors : <span id="visitors" />
```
*

I tried 
`sam build && aws-vault exec USER --no-session -- sam deploy`

Everything gets deployed without error! And when I visited my website,
the visitor count was displayed and updated on each refresh!

### CI/CD
My website is up and running, but everytime I brought changes to my files
I needed to manually open the command line and use SAM to build and deploy...

To automate that process, I implemented some CI/CD.


First, I wanted my function to be tested before anything is deployed.
So I used `pytest` and `mock_dynamodb` from `moto` to mock a **DynamoDB** table for my test.
I kept, as the event for my test function, the API event from the base
test_hello_world function that was created when I used `sam init`.
Then I created the test function.

This was the hardest part for me, as I was struggling using moto.
The test function was trying to call my real table and I had to find help on StackOverflow to find out
I needed my mock table to be **exactly** identical to my real one.
I fixed it by naming the table, the items and everything just like the real table's, and it worked!
I could locally pytest my function with success.

The final test looks like :
```py
import json
import boto3
import pytest
from moto import mock_dynamodb


# API event here


@mock_dynamodb
def test_visitors_count(apigw_event):
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
*
I implemented it to Github actions,
creating a ".github/workflows" directory and inside a yaml file to tell Github Actions what to do.

I wanted it to test my function everytime I push a commit. My AWS credentials were stored as secrets:
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
*
Finally, I also wanted my website files to be updated, and the old ones deleted,
so I needed my bucket to be synchronised on each push:
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

### That's it!
The final overall infrastructure looks like this :

![resume-design](https://user-images.githubusercontent.com/100123312/218184031-6d36e1a6-6e3b-41ba-8476-a5116423ec61.png)
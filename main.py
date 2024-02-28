import boto3
import json
import os
import sys

# Retrieving the config and mode
config = json.load(open(sys.argv[1]))

ACCESS_KEY = os.environ[config["ACCESS_KEY"]]
SECRET_KEY = os.environ[config["SECRET_KEY"]]

# # Bedrock runtime
bedrock_runtime = boto3.client(
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

input_text = ""

req_params = {
    "modelId": "amazon.titan-text-express-v1",
    "contentType": "application/json",
    "accept": "*/*",
    "body": json.dumps({"inputText": input_text}),
}

response = bedrock_runtime.invoke_model(**req_params)

response_body = json.loads(response.get("body").read())

# Titan Text Express: Price per 1,000 input tokens -> $0.0003 | Price per 1,000 output tokens -> $0.0004
# Total costs calculation
input_token_cost = int(response_body.get("inputTextTokenCount")) / 1000 * 0.0008
output_token_cost = int(response_body["results"][0]["tokenCount"]) / 1000 * 0.0016
total_token_cost = input_token_cost + output_token_cost
print(f"Total cost of this request is: {total_token_cost}$")

results = response_body["results"][0]["outputText"]

print(results)
import boto3
import json
import os
import sys
import uuid
import time

# Retrieving the config and mode
config = json.load(open(sys.argv[1]))

ACCESS_KEY = os.environ[config["ACCESS_KEY"]]
SECRET_KEY = os.environ[config["SECRET_KEY"]]
S3_BUCKET = os.environ[config["S3_BUCKET"]]

### S3 Bucket Stored Audio to ASR

# S3 Client
s3_client = boto3.client(
    "s3",
    region_name="us-west-2",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

# Uploading of the file, uncomment when uploading
file_name = "call_no_1"
# s3_client.upload_file("call_no_1", S3_BUCKET, "call_no_1")

# AWS Transcribe Client
transcribe_client = boto3.client(
    "transcribe",
    region_name="us-west-2",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)
transcript_name = f"transcript:{str(uuid.uuid4())}"

response = transcribe_client.start_transcription_job(
    TranscriptionJobName=transcript_name,
    Media={"MediaFileUri": f"s3://{S3_BUCKET}/{file_name}"},
    MediaFormat="mp3",
    LanguageCode="en-US",
    # a specific folder
    OutputBucketName=S3_BUCKET,
    Settings={
        "ShowSpeakerLabels": True,
        # up to 10
        "MaxSpeakerLabels": 2,
    },
)

status = transcribe_client.get_transcription_job(TranscriptionJobName=transcript_name)
while status["TranscriptionJob"]["TranscriptionJobStatus"] not in [
    "COMPLETED",
    "FAILED",
]:
    status = transcribe_client.get_transcription_job(
        TranscriptionJobName=transcript_name
    )
    time.sleep(5)


if status["TranscriptionJob"]["TranscriptionJobStatus"] != "FAILED":
    transcript_file_key = f"{transcript_name}.json"
    transcript_file = s3_client.get_object(Bucket=S3_BUCKET, Key=transcript_file_key)
    transcript_text = transcript_file["Body"].read().decode("utf-8")
    transcript_json = json.loads(transcript_text)

    output_text = ""
    current_speaker = ""

    items = transcript_json["results"]["items"]
    
    for item in items:
        speaker_name = item.get("speaker_label", "")
        speech = item["alternatives"][0]["content"]

        if speaker_name is not "" and speaker_name != current_speaker:
            current_speaker = speaker_name
            output_text += f"\n{current_speaker}: "

        # extra spaces
        if item["type"] == "punctuation":
            output_text = output_text.rstrip()

        # appending the speech
        output_text += f"{speech} "

    # Save the transcript to a text file
    # TODO: save on an S3 bucket as file

else:
    raise Exception("Task Failed")

### Transcribed Audio to LLM
transcribed_text = output_text

# Bedrock runtime configuration
bedrock_runtime = boto3.client(
    "bedrock-runtime",
    region_name="us-west-2",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)
# TODO: JSON Output Promt Engineering
input_text = f"""Given the provided conversation transcript within the angle brackets <>.
Generate a concise and coherent short summary of the conversation.

<{transcribed_text}>

"""

req_params = {
    "modelId": "amazon.titan-text-express-v1",
    "contentType": "application/json",
    "accept": "*/*",
    "body": json.dumps(
        {
            "inputText": input_text,
            # stop at 1000 tokens
            "textGenerationConfig": {"maxTokenCount": 1000},
            # creativity
            "temperature": 0,
            "topP": 0.9,
        }
    ),
}

response = bedrock_runtime.invoke_model(**req_params)
response_body = json.loads(response.get("body").read())

# Titan Text Express: Price per 1,000 input tokens -> $0.0003 | Price per 1,000 output tokens -> $0.0004
# Total costs calculation
input_token_cost = int(response_body.get("inputTextTokenCount")) / 1000 * 0.0008
output_token_cost = int(response_body["results"][0]["tokenCount"]) / 1000 * 0.0016
total_token_cost = input_token_cost + output_token_cost
print(f"Total cost of this request is: {total_token_cost}$")

# Results of the request
results = response_body["results"][0]["outputText"]

import logging
import azure.functions as func
import swagger_client as cris_client

from typing import List

import logging
import sys
import requests
import time
import swagger_client as cris_client
import json


def transcribe(url):
    logging.info("Starting transcription client...")
    # Your subscription key and region for the speech service
    SUBSCRIPTION_KEY = ""
    SERVICE_REGION = "southcentralus"
    NAME = "Simple transcription"
    DESCRIPTION = "Simple transcription description"
    LOCALE = "en-US"
    # Set subscription information when doing transcription with custom models
    ADAPTED_ACOUSTIC_ID = None  # guid of a custom acoustic model
    ADAPTED_LANGUAGE_ID = None  # guid of a custom language model


   # configure API key authorization: subscription_key
    configuration = cris_client.Configuration()
    configuration.api_key['Ocp-Apim-Subscription-Key'] = SUBSCRIPTION_KEY
    configuration.host = "https://{}.cris.ai".format(SERVICE_REGION)

    # create the client object and authenticate
    client = cris_client.ApiClient(configuration)

    # create an instance of the transcription api class
    transcription_api = cris_client.CustomSpeechTranscriptionsApi(api_client=client)

    # get all transcriptions for the subscription
    transcriptions: List[cris_client.Transcription] = transcription_api.get_transcriptions()

    logging.info("Deleting all existing completed transcriptions.")

    # delete all pre-existing completed transcriptions
    # if transcriptions are still running or not started, they will not be deleted
    for transcription in transcriptions:
        try:
            transcription_api.delete_transcription(transcription.id)
        except ValueError:
            # ignore swagger error on empty response message body: https://github.com/swagger-api/swagger-core/issues/2446
            pass

    # Use base models for transcription. Comment this block if you are using a custom model.
    # Note: you can specify additional transcription properties by passing a
    # dictionary in the properties parameter. See
    # https://docs.microsoft.com/azure/cognitive-services/speech-service/batch-transcription
    # for supported parameters.
    logging.info("Printing URL ::: {}".format(url))
    transcription_definition = cris_client.TranscriptionDefinition(
        name=NAME, description=DESCRIPTION, locale=LOCALE, recordings_url=url
    )

    # Uncomment this block to use custom models for transcription.
    # Model information (ADAPTED_ACOUSTIC_ID and ADAPTED_LANGUAGE_ID) must be set above.
    # if ADAPTED_ACOUSTIC_ID is None or ADAPTED_LANGUAGE_ID is None:
    #     logging.info("Custom model ids must be set to when using custom models")
    # transcription_definition = cris_client.TranscriptionDefinition(
    #     name=NAME, description=DESCRIPTION, locale=LOCALE, recordings_url=RECORDINGS_BLOB_URI,
    #     models=[cris_client.ModelIdentity(ADAPTED_ACOUSTIC_ID), cris_client.ModelIdentity(ADAPTED_LANGUAGE_ID)]
    # )

    data, status, headers = transcription_api.create_transcription_with_http_info(transcription_definition)

    # extract transcription location from the headers
    transcription_location: str = headers["location"]

    # get the transcription Id from the location URI
    created_transcription: str = transcription_location.split('/')[-1]

    logging.info("Created new transcription with id {}".format(created_transcription))

    logging.info("Checking status.")

    completed = False

    while not completed:
        running, not_started = 0, 0

        # get all transcriptions for the user
        transcriptions: List[cris_client.Transcription] = transcription_api.get_transcriptions()

        # for each transcription in the list we check the status
        for transcription in transcriptions:
            if transcription.status in ("Failed", "Succeeded"):
                # we check to see if it was the transcription we created from this client
                if created_transcription != transcription.id:
                    continue

                completed = True

                if transcription.status == "Succeeded":
                    results_uri = transcription.results_urls["channel_0"]
                    results = requests.get(results_uri)
                    logging.info("Transcription succeeded. Results: ")
                    logging.info(results.content.decode("utf-8"))
                    return results.content.decode("utf-8")
                else:
                    logging.info("Transcription failed :{}.".format(transcription.status_message))

                break
            elif transcription.status == "Running":
                running += 1
            elif transcription.status == "NotStarted":
                not_started += 1

        logging.info("Transcriptions status: "
                "completed (this transcription): {}, {} running, {} not started yet".format(
                    completed, running, not_started))

        # wait for 5 seconds
        time.sleep(5)
        
#     input("Press any key...")



def main(req: func.HttpRequest) -> str:
    logging.info('Python HTTP trigger function processed a request.')
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(message)s")
    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        RECORDINGS_BLOB_URI = "https://srramconvai.blob.core.windows.net/audio/{}?sv=2018-03-28&ss=bfqt&srt=sco&sp=rwdlacup&se=2020-10-09T22:39:00Z&st=2019-09-12T14:39:00Z&spr=https&sig=hgUMUuE08D%2FcWvblcRGZ7semLnMZ9HWEv0BZjk1VGYY%3D".format(name)
        result = transcribe(RECORDINGS_BLOB_URI)
        #return func.HttpResponse(f"Transcribed Output : {result}!")
        return json.dumps({
                            'name': name,
                            'content': result })
    else:
        return func.HttpResponse(
             "Please pass a name on the query string or in the request body",
             status_code=400
        )

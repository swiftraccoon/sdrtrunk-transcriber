#include "curlHelper.h"
#include <stdexcept>

const std::string API_URL = "https://api.openai.com/v1/audio/transcriptions";
const std::string API_KEY = "KEY";

size_t WriteCallback(void *contents, size_t size, size_t nmemb, void *userp)
{
    ((std::string *)userp)->append((char *)contents, size * nmemb);
    return size * nmemb;
}

void setupCurlHeaders(CURL *curl, struct curl_slist *&headers)
{
    headers = curl_slist_append(headers, ("Authorization: Bearer " + API_KEY).c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
}

void setupCurlPostFields(CURL *curl, curl_mime *&mime, const std::string &file_path)
{
    curl_mimepart *part;
    mime = curl_mime_init(curl);

    // Add the file
    part = curl_mime_addpart(mime);
    curl_mime_name(part, "file");
    curl_mime_filedata(part, file_path.c_str());

    // Add other data fields
    part = curl_mime_addpart(mime);
    curl_mime_name(part, "model");
    curl_mime_data(part, "whisper-1", CURL_ZERO_TERMINATED);

    part = curl_mime_addpart(mime);
    curl_mime_name(part, "prompt");
    curl_mime_data(part, "Transcribe the radio dispatch audio. The speaker is usually a dispatcher, police officer, or EMS responder. There are often callsigns, ten-codes, and addresses said.", CURL_ZERO_TERMINATED);

    part = curl_mime_addpart(mime);
    curl_mime_name(part, "response_format");
    curl_mime_data(part, "json", CURL_ZERO_TERMINATED);

    part = curl_mime_addpart(mime);
    curl_mime_name(part, "temperature");
    curl_mime_data(part, "0", CURL_ZERO_TERMINATED);

    part = curl_mime_addpart(mime);
    curl_mime_name(part, "language");
    curl_mime_data(part, "en", CURL_ZERO_TERMINATED);
}

std::string makeCurlRequest(CURL *curl, curl_mime *mime)
{
    std::string response;
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    CURLcode res = curl_easy_perform(curl);

    if (res != CURLE_OK)
    {
        throw std::runtime_error("CURL request failed: " + std::string(curl_easy_strerror(res)));
    }
    return response;
}

std::string curl_transcribe_audio(const std::string &file_path)
{
    CURL *curl = curl_easy_init();
    if (!curl)
    {
        throw std::runtime_error("CURL initialization failed");
    }

    struct curl_slist *headers = NULL;
    setupCurlHeaders(curl, headers);

    curl_mime *mime;
    setupCurlPostFields(curl, mime, file_path);

    curl_easy_setopt(curl, CURLOPT_URL, API_URL.c_str());
    curl_easy_setopt(curl, CURLOPT_MIMEPOST, mime);

    std::string response = makeCurlRequest(curl, mime);

    curl_easy_cleanup(curl);
    curl_mime_free(mime);

    return response;
}

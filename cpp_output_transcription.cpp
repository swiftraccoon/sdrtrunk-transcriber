#include <iostream>
#include <fstream>
#include <string>
#include <curl/curl.h>
#include <json/json.h>

size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

std::string curl_transcribe_audio(const std::string& file_path) {
    // Define the endpoint and your API key
    std::string url = "https://api.openai.com/v1/audio/transcriptions";
    std::string api_key = "YOUR_KEY_HERE";

    // Initialize CURL
    CURL* curl = curl_easy_init();
    if (!curl) {
        return "CURL initialization failed";
    }

    // Setup headers
    struct curl_slist* headers = NULL;
    headers = curl_slist_append(headers, ("Authorization: Bearer " + api_key).c_str());

    // Setup POST fields
    curl_mime* mime;
    curl_mimepart* part;
    mime = curl_mime_init(curl);

    // Add the file part
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

    // Set CURL options
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_MIMEPOST, mime);

    // Make the POST request and capture the response
    std::string response;
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    CURLcode res = curl_easy_perform(curl);

    // Cleanup
    curl_easy_cleanup(curl);
    curl_mime_free(mime);

    // Return the response or handle as needed
    if (res != CURLE_OK) {
        return "CURL request failed: " + std::string(curl_easy_strerror(res));
    }
    return response;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: ./program <file_path>" << std::endl;
        return 1;
    }
    std::string file_path = argv[1];
    std::cout << curl_transcribe_audio(file_path) << std::endl;
    return 0;
}

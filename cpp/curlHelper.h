#pragma once
#include <string>
#include <curl/curl.h>

size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp);
void setupCurlHeaders(CURL* curl, struct curl_slist*& headers);
void setupCurlPostFields(CURL* curl, curl_mime*& mime, const std::string& file_path);
std::string makeCurlRequest(CURL* curl, curl_mime* mime);
std::string curl_transcribe_audio(const std::string& file_path);

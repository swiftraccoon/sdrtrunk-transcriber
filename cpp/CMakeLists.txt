cmake_minimum_required(VERSION 3.10)
project(sdrTrunkTranscriber)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

find_package(CURL REQUIRED)

add_executable(sdrTrunkTranscriber main.cpp curlHelper.cpp)

target_link_libraries(sdrTrunkTranscriber CURL::libcurl)
#include <iostream>
#include "curlHelper.h"

int main(int argc, char *argv[])
{
    if (argc < 2)
    {
        std::cout << "Usage: ./program <file_path>" << std::endl;
        return 1;
    }
    std::string file_path = argv[1];
    try
    {
        std::cout << curl_transcribe_audio(file_path) << std::endl;
    }
    catch (const std::exception &e)
    {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    return 0;
}
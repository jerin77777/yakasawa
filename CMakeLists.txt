cmake_minimum_required(VERSION 3.16)

# Only compile main and its required dependencies (skips ~90 unused network/display components)
# This reduces build from 1063 files to ~50 files, eliminating Windows file lock collisions and compiler bugs
set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32_ga700_rs485)

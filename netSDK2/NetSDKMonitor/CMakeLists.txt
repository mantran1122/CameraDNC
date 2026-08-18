cmake_minimum_required(VERSION 3.16)
project(NetSDKMonitor VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

if(NOT MSVC)
    message(FATAL_ERROR "dhnetsdk.h chi ho tro trinh dich MSVC - hay dung kit Qt MSVC 2022 64-bit")
endif()

set(NETSDK_ROOT "D:/dnc/netSDK2")

find_package(Qt6 REQUIRED COMPONENTS Widgets)

qt_add_executable(NetSDKMonitor WIN32
    main.cpp
    mainwindow.h
    mainwindow.cpp
)

target_include_directories(NetSDKMonitor PRIVATE "${NETSDK_ROOT}/Include/Common")
target_link_libraries(NetSDKMonitor PRIVATE
    Qt6::Widgets
    "${NETSDK_ROOT}/Lib/Win64/dhnetsdk.lib"
)

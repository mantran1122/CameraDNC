cmake_minimum_required(VERSION 3.16)
project(DemoLauncher VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)

qt_add_executable(DemoLauncher WIN32
    main.cpp
    mainwindow.h
    mainwindow.cpp
)

target_link_libraries(DemoLauncher PRIVATE Qt6::Widgets)

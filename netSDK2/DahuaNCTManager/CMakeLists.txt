cmake_minimum_required(VERSION 3.23)

project(DahuaManager VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)

set(DAHUA_SDK_ROOT "D:/dnc/netSDK2" CACHE PATH "Root directory of the Dahua NetSDK")
set(QT_DEPLOY_EXECUTABLE "" CACHE FILEPATH "Optional path to windeployqt.exe")
set(DAHUA_SDK_BIN_DIR "${DAHUA_SDK_ROOT}/Bin/Win64")
if(NOT EXISTS "${DAHUA_SDK_BIN_DIR}")
    set(DAHUA_SDK_BIN_DIR "${DAHUA_SDK_ROOT}/Bin")
endif()

set(PROJECT_SOURCES
    main.cpp
    src/controllers/appcontroller.cpp
    src/controllers/appcontroller.h
    src/dialogs/logindialog.cpp
    src/dialogs/logindialog.h
    src/managers/configmanager.cpp
    src/managers/configmanager.h
    src/managers/devicemanager.cpp
    src/managers/devicemanager.h
    src/managers/downloadmanager.cpp
    src/managers/downloadmanager.h
    src/managers/loggermanager.cpp
    src/managers/loggermanager.h
    src/managers/videomanager.cpp
    src/managers/videomanager.h
    src/models/deviceconnectioninfo.h
    src/models/downloadtask.h
    src/sdk/dahuasdkmanager.cpp
    src/sdk/dahuasdkmanager.h
    src/utils/pathutils.cpp
    src/utils/pathutils.h
    src/widgets/mainwindow.cpp
    src/widgets/mainwindow.h
    src/widgets/previewhost.cpp
    src/widgets/previewhost.h
)

add_executable(DahuaManager ${PROJECT_SOURCES})

target_include_directories(DahuaManager PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
    "${DAHUA_SDK_ROOT}/Include"
    "${DAHUA_SDK_ROOT}/Include/Common"
)

target_link_libraries(DahuaManager PRIVATE
    Qt6::Widgets
    "${DAHUA_SDK_ROOT}/Lib/Win64/dhnetsdk.lib"
    "${DAHUA_SDK_ROOT}/Lib/Win64/dhconfigsdk.lib"
)

if(EXISTS "${DAHUA_SDK_BIN_DIR}")
    file(GLOB DAHUA_SDK_DLLS "${DAHUA_SDK_BIN_DIR}/*.dll")
    foreach(SDK_DLL ${DAHUA_SDK_DLLS})
        add_custom_command(TARGET DahuaManager POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${SDK_DLL}"
            "$<TARGET_FILE_DIR:DahuaManager>"
        )
    endforeach()
endif()

if(QT_DEPLOY_EXECUTABLE AND EXISTS "${QT_DEPLOY_EXECUTABLE}")
    add_custom_command(TARGET DahuaManager POST_BUILD
        COMMAND "${QT_DEPLOY_EXECUTABLE}" --dir "$<TARGET_FILE_DIR:DahuaManager>" "$<TARGET_FILE:DahuaManager>"
        COMMENT "Deploying Qt runtime with windeployqt"
    )
endif()

# 10_Coding_Standards

## C++ Standard

-   C++17
-   Qt6

## Naming

Class: DeviceManager

Member: m_loginHandle

Function: startLive()

Constant: constexpr

## Rules

-   Một class một nhiệm vụ.
-   Không dùng global variable.
-   Không include dhnetsdk.h ngoài sdk/.
-   Ưu tiên RAII.
-   Dùng std::unique_ptr khi phù hợp.
-   Signal/Slot thay callback UI.

## Formatting

-   4 spaces
-   UTF-8
-   LF
-   Header/.cpp tách riêng.

## Git

feature/\* develop main

Commit:

feat: fix: refactor: docs: test:

## Review Checklist

-   Build OK
-   Không warning nghiêm trọng
-   Memory leak check
-   Handle được giải phóng
-   Log đầy đủ

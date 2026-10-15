# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AnthoDingo
idf_component_register(SRCS "main.c" "ota.c" PRIV_REQUIRES bt nvs_flash app_update esp_app_format)
# Debug build, logs on a USB serial port (main.c): idf.py -B build-debug -DAPPLEREMOTE_USB_LOG=1 build
# (PlatformIO: env xiao_esp32s3_debug sets the macro through build_flags)
if(APPLEREMOTE_USB_LOG)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE APPLEREMOTE_USB_LOG)
endif()

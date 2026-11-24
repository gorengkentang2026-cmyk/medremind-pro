[app]
title = MedRemind Pro
package.name = medremindpro
package.domain = com.rolly.medremind

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.main = app_mobile.py

version = 1.0.0
requirements = python3==3.11.8,kivy==2.3.0

orientation = portrait
fullscreen = 0

android.permissions = RECEIVE_BOOT_COMPLETED, VIBRATE, POST_NOTIFICATIONS, WAKE_LOCK, FOREGROUND_SERVICE, SCHEDULE_EXACT_ALARM, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

android.allow_backup = True
android.icon = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 0

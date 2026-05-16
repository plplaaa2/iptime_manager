ipTIME Manager 폴더 구조 최신화 현황입니다.
기존 루트에 존재하던 소스 코드들을 HACS 배포 규격에 따라 custom_components 서브디렉토리 하위로 이동 재배치했습니다.

iptime_manager (루트)
|   .gitignore
|   hacs.json
|   icon.png
|   README.md
|   README.ko.md
|   tree.md
|
+---custom_components
    |   caution.jsonl
    |   changelog.jsonl
    |   tree.md
    |   web_api.md
    |
    \---iptime_manager
        |   __init__.py
        |   api.py
        |   binary_sensor.py
        |   button.py
        |   config_flow.py
        |   const.py
        |   coordinator.py
        |   device_tracker.py
        |   manifest.json
        |   select.py
        |   sensor.py
        |   strings.json
        |   switch.py
        |   
        +---brand
        |       icon.png
        |       logo.png
        |       
        \---translations
                en.json
                ko.json

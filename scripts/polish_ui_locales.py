#!/usr/bin/env python3
"""One-off polish: remove dead guide keys, align nav/help copy with Station/Data/Service naming."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "app" / "ui" / "locales"

DELETE_KEYS = {
    "settings": [
        "guideTitle",
        "guideIntro",
        "guideStep1",
        "guideStep2",
        "guideStep3",
        "guideStep4",
        "openConnections",
        "openNotifications",
        "openRecognition",
        "openService",
    ],
    "library": [
        "guideTitle",
        "guideIntro",
        "guideStep1",
        "guideStep2",
        "guideStep3",
        "openArchive",
        "openMaintenance",
    ],
    "timeline": [
        "guideTitle",
        "guideIntro",
        "guideStep1",
        "guideStep2",
        "guideStep3",
        "openSpeciesDirectory",
        "openReview",
        "reviewGuideTitle",
        "reviewGuideIntro",
        "reviewGuideStep1",
        "reviewGuideStep2",
        "reviewGuideStep3",
        "openRecognitionImprovement",
    ],
    "video": ["guideTitle", "guideIntro", "guideStep1", "guideStep2", "guideStep3"],
    "system": [
        "guideTitle",
        "guideIntro",
        "guideStep1",
        "guideStep2",
        "guideStep3",
        "openHealth",
        "openCatalog",
        "openWorkspace",
    ],
    "speciesDirectory": [
        "guideTitle",
        "guideIntro",
        "guideStep1",
        "guideStep2",
        "guideStep3",
        "openRecordings",
        "openSeasonality",
    ],
}

PATCHES: dict[str, dict[str, object]] = {
    "ru": {
        "nav.settingsHint": "Камеры, поток, уведомления, интеграции и распознавание — каждая тема в своём блоке; подсказки у полей.",
        "nav.systemHint": "Сводка работы станции, каталог видов и редкие инструменты обслуживания.",
        "nav.libraryHint": "Файлы архива на диске, выгрузки для обучения и уход за хранилищем. Просмотр роликов — в «Записи».",
        "nav.unknowns": "Проверка",
        "protected.passwordRequired": "Раздел для настройки станции или сервисного обслуживания. Введите пароль администратора.",
        "library.serviceNotice": "Архив и обслуживание данных. Повседневный просмотр роликов — в разделе «Записи».",
        "library.sections.archiveDescription": "Календарь по реальным файлам на диске: выберите день и перейдите в «Записи», чтобы открыть ролики и детекции.",
        "library.sections.exportDescription": "В обзорном режиме — период, фильтры и выгрузка. Дополнительные параметры датасета — в сервисном режиме страницы.",
        "library.sections.storageDescription": "Диск, объём записей и обслуживание базы. Веса моделей и правки каталога видов — на странице «Сервис».",
        "library.sections.maintenanceDescription": "Прогон с диска, импорт и прочие операции для администратора — только в сервисном режиме.",
        "library.datasetToolsLibraryHint": "На этой же странице: сканирование архива, резервное копирование, обзор хранилища.",
        "timeline.intro": "Выберите день с записями, откройте ролик и при необходимости перейдите к виду или к проверке распознавания.",
        "timeline.scanHint": "(раздел «Данные» → календарь архива)",
        "live.noCameras": "Камеры не заданы. Добавьте их в «Станция» → блок подключений и камер (имя потока из Go2RTC или Frigate).",
        "overview.regionComparisonConfigure": "Укажите ключ eBird API в «Станция» → блок eBird, чтобы включить сравнение с регионом.",
        "speciesDirectory.description": "Виды, которые уже встречались на станции: счётчики по записям, карточка вида и переход к роликам.",
        "system.pageDescription": "Сводка состояния, каталог и диагностика. Расширенный режим — для логов, обслуживания и редких операций.",
        "system.sections.overviewDescription": "Готовность, ресурсы и уведомления — то, что чаще всего стоит проверить первым.",
        "system.sections.catalogDescription": "Проверка и починка справочника видов: сначала основные действия, подробная диагностика — в расширенном режиме.",
        "system.sections.workspaceDescription": "Автоматизация и задачи обслуживания для администратора.",
        "food.description": "Какой корм сейчас в кормушке: система связывает это с визитами для учёта.",
        "help.library.title": "Данные и архив",
        "help.library.description": "Календарь архива на диске, выгрузки для обучения и обслуживание хранилища. Для просмотра роликов откройте «Записи».",
        "help.library.details[2].title": "Что на этой странице",
        "help.library.details[2].content": "Просмотр архива, импорт с диска, экспорт датасета, резервные копии и обзор занятого места — в одном разделе меню «Данные».",
        "help.library.details[3].title": "Связь с «Сервис»",
        "help.library.details[3].content": "«Сервис» — мониторинг, логи процессора и глубокая диагностика. Работа с файлами архива сосредоточена здесь.",
        "help.library.details[4].title": "Про обслуживание",
        "help.library.details[4].content": "Тяжёлые операции (импорт, пересборка, очистка) лучше делать, когда вы понимаете, какие дни уже есть в архиве; календарь показывает это по файлам на диске.",
        "help.migrationCalendar.title": "Сезонность",
        "help.migrationCalendar.description": "По месяцам: насколько часто каждый вид появлялся у кормушки в ваших данных.",
        "help.unknowns.details[1].content": "Порог задаётся в «Станция» → распознавание и процессор (блок про неуверенные детекции). Значение по умолчанию в поставке часто около 0,48 — ниже попадают сюда.",
        "help.videoDetails.details[2].content": "В блоке обнаруженных видов: число срабатываний, уверенность, длительность, ссылка на карточку вида. Исправление вида здесь то же, что на странице проверки для этой детекции.",
        "migrationCalendar.title": "Сезонность",
        "migrationCalendar.description": "Таблица по месяцам: сколько визитов каждого вида было у кормушки за выбранный период. Фильтр влияет только на таблицу.",
        "migrationCalendar.errorLoad": "Не удалось загрузить таблицу сезонности.",
        "migrationCalendar.filterSectionTitle": "Период и каталог",
        "unknowns.title": "Проверка распознавания",
        "unknowns.intro": "Детекции с низкой уверенностью: откройте запись, подтвердите или исправьте вид.",
        "common.pageNotFoundDescription": "Адрес изменился или ссылка устарела. Вернитесь на главную или выберите раздел в меню.",
        "help.timeline.description": "Выбор дня, фильтры и карточки визитов; из записи — к виду или к исправлению распознавания.",
        "system.heroIssueReadiness": "Сводка готовности станции просела: сначала раздел «Сервис» (готовность, диск, база), затем глубокое обслуживание.",
    },
    "en": {
        "nav.settingsHint": "Cameras, stream, alerts, integrations, and recognition—each in its own section with field hints.",
        "nav.systemHint": "Station health, species catalog, and maintenance tools you rarely need every day.",
        "nav.libraryHint": "On-disk archive, training exports, and storage care. Watch clips under Recordings.",
        "nav.unknowns": "Review",
        "protected.passwordRequired": "This area is for station setup or service maintenance. Enter the admin password.",
        "library.serviceNotice": "Archive and data maintenance. Day-to-day clips live under Recordings.",
        "library.sections.archiveDescription": "The calendar reflects real files on disk: pick a day, then open Recordings to view clips and detections.",
        "library.sections.exportDescription": "Overview mode keeps period, filters, and export. Extra dataset tuning is under the page’s service mode.",
        "library.sections.storageDescription": "Disk usage, recording volume, and database care. Model weights and catalog tools live under Service.",
        "library.sections.maintenanceDescription": "File replay, import, and similar admin tools—only in service mode on this page.",
        "library.datasetToolsLibraryHint": "On this same page: archive scan, backups, and storage overview.",
        "timeline.intro": "Pick a day that has recordings, open a clip, then jump to a species page or review if you need to fix recognition.",
        "timeline.scanHint": "(Data → archive calendar)",
        "live.noCameras": "No cameras configured. Add them under Station → connections and cameras (stream name from Go2RTC or Frigate).",
        "overview.regionComparisonConfigure": "Add your eBird API key under Station → eBird to enable regional comparison.",
        "speciesDirectory.description": "Species already seen at this station: counts from recordings, species page, and links back to clips.",
        "system.pageDescription": "Health summary, catalog, and diagnostics. Advanced mode is for logs, maintenance, and rare operations.",
        "system.sections.overviewDescription": "Readiness, resources, and notifications—usually the first things to check.",
        "system.sections.catalogDescription": "Species catalog health: main actions first; deep diagnostics in advanced mode.",
        "system.sections.workspaceDescription": "Automation and maintenance tasks for administrators.",
        "food.description": "Which food is in the feeder now; visits are linked to it for your records.",
        "help.library.title": "Data and archive",
        "help.library.description": "Disk archive calendar, training exports, and storage maintenance. Open Recordings to watch clips.",
        "help.library.details[2].title": "What you can do here",
        "help.library.details[2].content": "Browse the archive, scan/import from disk, export datasets, backups, and storage overview—all under the Data menu item.",
        "help.library.details[3].title": "How this relates to Service",
        "help.library.details[3].content": "Service is for monitoring, processor logs, and deep diagnostics. File-based archive work is concentrated here.",
        "help.library.details[4].title": "About maintenance",
        "help.library.details[4].content": "Heavy tasks (import, rebuild, cleanup) are easier when you already know which days exist in the archive; the calendar reflects files on disk.",
        "help.migrationCalendar.title": "Seasonality",
        "help.migrationCalendar.description": "Month by month: how often each species showed up at your feeder in your data.",
        "help.unknowns.details[1].content": "The threshold is set under Station → processor / recognition (uncertain detections). The shipped default is often around 0.48—candidates below that land here.",
        "help.videoDetails.details[2].content": "Detected species: hit counts, confidence, duration, link to the species page. Correcting a species here is the same action as on the review page for that detection.",
        "migrationCalendar.title": "Seasonality",
        "migrationCalendar.description": "Monthly grid: how many visits each species had at your feeder in the selected period. Filters apply to the table only.",
        "migrationCalendar.errorLoad": "Could not load the seasonality table.",
        "migrationCalendar.filterSectionTitle": "Period and catalog",
        "unknowns.title": "Recognition review",
        "unknowns.intro": "Low-confidence detections: open the clip, then confirm or correct the species.",
        "common.pageNotFoundDescription": "The address may have changed or the link is outdated. Go home or pick a section from the menu.",
        "help.timeline.description": "Choose a day, filter visits, open clips—jump to a species page or review when fixing recognition.",
        "system.heroIssueReadiness": "Readiness looks degraded—open Service (health, disk, database) before running heavy maintenance.",
    },
    "zh": {
        "nav.settingsHint": "摄像头、流、通知、集成与识别各有独立区块，字段旁有说明。",
        "nav.systemHint": "站点状态、物种目录与不常用的维护工具。",
        "nav.libraryHint": "磁盘归档、训练导出与存储维护。日常看录像请用「记录」。",
        "nav.unknowns": "复核",
        "protected.passwordRequired": "此区域用于站点设置或服务维护，请输入管理员密码。",
        "library.serviceNotice": "归档与数据维护。日常观看录像请前往「记录」。",
        "library.sections.archiveDescription": "日历对应磁盘上的真实文件：选日期后到「记录」查看片段与检测。",
        "library.sections.exportDescription": "概览模式保留周期、筛选与导出；数据集高级参数在本页的服务模式。",
        "library.sections.storageDescription": "磁盘、录像体量与数据库维护。模型权重与目录工具在「服务」页。",
        "library.sections.maintenanceDescription": "文件回放、导入等管理操作仅在本页服务模式。",
        "library.datasetToolsLibraryHint": "本页同一处：归档扫描、备份与存储概览。",
        "timeline.intro": "选择有录像的日期，打开片段，需要时再进入物种页或识别复核。",
        "timeline.scanHint": "（「数据」→ 归档日历）",
        "live.noCameras": "尚未配置摄像头。请在「站点」→ 连接与摄像头中添加（Go2RTC 或 Frigate 的流名称）。",
        "overview.regionComparisonConfigure": "在「站点」→ eBird 中填写 eBird API 密钥以启用区域对比。",
        "speciesDirectory.description": "本站点已出现过的鸟类：按录像统计、物种卡片并可回到原片段。",
        "system.pageDescription": "状态摘要、目录与诊断。扩展模式用于日志、维护与少见操作。",
        "system.sections.overviewDescription": "就绪状态、资源与通知——通常先从这里看。",
        "system.sections.catalogDescription": "物种目录健康：先做主要操作，深度诊断在扩展模式。",
        "system.sections.workspaceDescription": "面向管理员的自动化与维护任务。",
        "food.description": "当前食槽中的饲料类型；系统会把它与到访记录关联。",
        "help.library.title": "数据与归档",
        "help.library.description": "磁盘归档日历、训练导出与存储维护。观看片段请用「记录」。",
        "help.library.details[2].title": "本页能做什么",
        "help.library.details[2].content": "浏览归档、从磁盘扫描/导入、导出数据集、备份与存储概览——都在菜单「数据」下。",
        "help.library.details[3].title": "与「服务」的关系",
        "help.library.details[3].content": "「服务」侧重监控、处理器日志与深度诊断；基于文件的归档工作集中在此。",
        "help.library.details[4].title": "关于维护",
        "help.library.details[4].content": "导入、重建、清理等重操作前，建议先确认归档里已有哪些日期；日历按磁盘文件反映。",
        "help.migrationCalendar.title": "季节性",
        "help.migrationCalendar.description": "按月查看：各物种在您的数据中于喂食器出现的频率。",
        "help.unknowns.details[1].content": "阈值在「站点」→ 处理器/识别（不确定检测）中设置。发行默认常约为 0.48，低于此的候选会出现在这里。",
        "help.videoDetails.details[2].content": "检测到的物种：次数、置信度、时长、物种页链接。在此更正物种与复核页上对同一检测的更正相同。",
        "migrationCalendar.title": "季节性",
        "migrationCalendar.description": "按月统计所选时段内各物种在喂食器的到访次数；筛选仅作用于表格。",
        "migrationCalendar.errorLoad": "无法加载季节性表格。",
        "migrationCalendar.filterSectionTitle": "时段与目录",
        "unknowns.title": "识别复核",
        "unknowns.intro": "置信度偏低的检测：先打开片段，再确认或更正物种。",
        "common.pageNotFoundDescription": "地址可能已变更或链接失效。请返回首页或从菜单选择栏目。",
        "help.timeline.description": "选择日期、筛选到访、打开片段；需要时可进入物种页或识别复核。",
        "system.heroIssueReadiness": "就绪状态变差：请先到「服务」页查看健康、磁盘与数据库，再执行深度维护。",
    },
}


def _set_nested(data: dict, dotted: str, value: object) -> None:
    if "[" in dotted:
        base, rest = dotted.split("[", 1)
        idx_str, tail = rest.split("]", 1)
        index = int(idx_str)
        key = tail.lstrip(".")
        cur = data
        for part in base.split("."):
            cur = cur[part]
        item = cur[index]
        if key:
            item[key] = value
        else:
            cur[index] = value
        return
    parts = dotted.split(".")
    cur = data
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value


def _del_nested_keys(root: dict, section: str, keys: list[str]) -> None:
    sec = root.get(section)
    if not isinstance(sec, dict):
        return
    for k in keys:
        sec.pop(k, None)


def polish_file(lang: str) -> None:
    path = LOCALES / f"{lang}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for section, keys in DELETE_KEYS.items():
        _del_nested_keys(data, section, keys)
    patch = PATCHES.get(lang, {})
    for dotted, value in patch.items():
        _set_nested(data, dotted, value)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    for lang in ("ru", "en", "zh"):
        polish_file(lang)
    print("Updated", ", ".join(f"{lang}.json" for lang in ("ru", "en", "zh")))


if __name__ == "__main__":
    main()

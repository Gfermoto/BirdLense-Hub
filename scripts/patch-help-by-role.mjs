#!/usr/bin/env node
/**
 * Nest help.<page> under help.<page>.guest|operator|admin.
 * Existing copy becomes operator; guest/admin are tailored per page.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, '..', 'app', 'ui', 'locales');

const COPY = {
  ru: {
    videoDetails: {
      guest: {
        description:
          'Автоматическая запись визита: ролик, какие птицы попали в кадр, что они делали и как изменился вес на кормушке.',
        extraDetails: [
          {
            title: 'Вид',
            content:
              'Название вида, который система увидела на записи. Это оценка модели, а не ручная подпись.',
          },
          {
            title: 'Поведение',
            content:
              'Короткая метка активности (кормление, отдых, полёт и т.п.), если модель её распознала.',
          },
          {
            title: 'Изменение веса',
            content:
              'Зелёная стрелка вверх — птица прибавила в весе на платформе за визит, красная вниз — убавила. Мелкие колебания (до ~5 г) не показываются.',
          },
        ],
      },
      operator: {
        description:
          'Проверка записи: ролик, виды, поведение, вес. Исправления вида и метки поведения — здесь; клички (Re-ID) — в карточке визита или профиле птицы.',
        extraDetails: [
          {
            title: 'Исправление вида',
            content:
              'В блоке «Обнаруженные виды» — «Исправить вид». То же действие, что на странице «Проверка». Нужен доступ оператора.',
          },
          {
            title: 'Поведение и Behavior v2.1',
            content:
              'Метка поведения на ролике (кнопка «Изменить поведение»). Модель v2.1 в режиме auto подставляет метку при обработке; оператор может поправить вручную.',
          },
          {
            title: 'Очередь эксперта',
            content:
              'Спорные случаи (семантика, Re-ID) попадают в Expert Queue / разметку. Геометрия рамки — в «Разметке», вид и поведение — здесь.',
          },
        ],
      },
      admin: {
        description:
          'Полная карточка записи плюс служебные поля для админа: версия процессора, трассировка слияния треков, пороги на «Станции».',
        extraDetails: [
          {
            title: 'Станция и модели',
            content:
              'Пороги детекции, behavior engine (auto / shadow / canary), OpenVINO и веса — «Станция» → распознавание и процессор. Версия процессора в блоке «Информация о записи» — для сопоставления с логами.',
          },
          {
            title: 'Fusion trace',
            content:
              'Кнопка трассировки слияния треков — отладка пайплайна детектора. Только для администратора.',
          },
        ],
      },
    },
    timeline: {
      guest: {
        description:
          'Лента визитов за выбранный день: кто прилетал, как долго, погода и оценка веса на карточке.',
        extraDetails: [
          {
            title: 'Карточка визита',
            content:
              'Вид, длительность, температура. Раскройте карточку — отдельные срабатывания по времени. Клик по ролику откроет детали записи.',
          },
        ],
      },
      operator: {
        description:
          'Записи за день: фильтры по виду и поведению, исправления, привязка клички (Re-ID) с карточки визита.',
        extraDetails: [
          {
            title: 'Re-ID и кличка',
            content:
              'На карточке визита можно привязать или отвязать профиль птицы (кличку), если включён Re-ID.',
          },
          {
            title: 'Фильтры',
            content:
              'Фильтр по виду и по метке поведения; параметры попадают в URL — удобно делиться ссылкой с коллегой.',
          },
        ],
      },
      admin: {
        description:
          'Таймлайн визитов и диагностика: при пустом дне смотрите «Данные» (архив на диске) и статус процессора.',
        extraDetails: [
          {
            title: 'Расхождение архива и UI',
            content:
              'День есть в «Данные», но пусто здесь — нет детекций или визитов; проверьте логи процессора и импорт.',
          },
        ],
      },
    },
    overview: {
      guest: {
        description:
          'Сводка активности у кормушки за выбранный день: сколько видов и визитов, погода и суточный ритм.',
        extraDetails: [],
      },
      operator: {
        description:
          'Дашборд активности: метрики визитов, топ видов, соотношение аудио/видео. Используйте для ежедневного контроля качества данных.',
        extraDetails: [],
      },
      admin: {
        description:
          'Обзор станции и качества пайплайна; при аномалиях — «Сервис», очереди и настройки на «Станции».',
        extraDetails: [],
      },
    },
    unknowns: {
      guest: {
        description:
          'Раздел проверки сомнительных распознаваний. Для просмотра записей используйте «Записи» и карточку видео.',
        extraDetails: [],
      },
      operator: {
        description:
          'Очередь неуверенных детекций: выберите правильный вид и «Применить». Тот же API, что «Исправить вид» в карточке ролика.',
        extraDetails: [
          {
            title: 'Expert Queue',
            content:
              'Сложные семантические кейсы уходят в разметку / expert review; здесь — быстрые исправления вида по порогу уверенности.',
          },
        ],
      },
      admin: {
        description:
          'Порог попадания в очередь задаётся на «Станции». Массовые сбои — логи процессора и метрики behavior/detector.',
        extraDetails: [],
      },
    },
    library: {
      guest: {
        description: 'Календарь дней, когда на диске есть файлы записей (архив).',
        extraDetails: [],
      },
      operator: {
        description:
          'Архив записей, импорт с диска, экспорт датасетов. Ролики смотрите в «Записях».',
        extraDetails: [],
      },
      admin: {
        description:
          'Обслуживание хранилища, бэкапы, импорт. Тяжёлые операции — при понимании занятости диска по календарю.',
        extraDetails: [],
      },
    },
    food: {
      guest: {
        description: 'Какой корм отмечен активным — для контекста визитов.',
        extraDetails: [],
      },
      operator: {
        description:
          'Управление типами корма в кормушке; активный корм связывается с новыми визитами.',
        extraDetails: [],
      },
      admin: {
        description: 'Справочник кормов и аналитика привлекаемых видов.',
        extraDetails: [],
      },
    },
    migrationCalendar: {
      guest: {
        description: 'Сезонность: в какие месяцы вид чаще появлялся у кормушки.',
        extraDetails: [],
      },
      operator: {
        description: 'Тепловая карта визитов по месяцам; клик по виду — сводная страница.',
        extraDetails: [],
      },
      admin: {
        description: 'Данные из SpeciesVisit за все годы; для отчётов экспортируйте сводки отдельно.',
        extraDetails: [],
      },
    },
  },
  en: {
    videoDetails: {
      guest: {
        description:
          'Automatic visit record: clip, species seen, behavior, and feeder weight change when available.',
        extraDetails: [
          {
            title: 'Species',
            content: 'Species name estimated by the system from the video.',
          },
          {
            title: 'Behavior',
            content: 'Short activity label (feeding, resting, flying, etc.) when recognized.',
          },
          {
            title: 'Weight change',
            content:
              'Green up — bird gained weight on the scale during the visit; red down — lost. Changes under ~5 g are hidden as noise.',
          },
        ],
      },
      operator: {
        description:
          'Review the clip, species, behavior, and weight. Fix species here; nicknames (Re-ID) from the visit card.',
        extraDetails: [
          {
            title: 'Correct species',
            content: 'In Detected species — Correct species. Same as the Review page. Operator access required.',
          },
          {
            title: 'Behavior v2.1',
            content:
              'Edit behavior on the clip. v2.1 in auto mode sets labels at processing time; operators can override.',
          },
          {
            title: 'Expert queue',
            content: 'Hard cases go to labelling / expert review. Box geometry in Labelling; species/behavior here.',
          },
        ],
      },
      admin: {
        description:
          'Full recording card plus admin fields: processor version, fusion trace, thresholds under Station.',
        extraDetails: [
          {
            title: 'Station & models',
            content:
              'Detection thresholds, behavior engine (auto/shadow/canary), OpenVINO — Station → recognition & processor.',
          },
          {
            title: 'Fusion trace',
            content: 'Track-merge debug trace for the detector pipeline. Admin only.',
          },
        ],
      },
    },
    timeline: {
      guest: {
        description: 'Visit feed for the selected day: species, duration, weather, weight on the card.',
        extraDetails: [
          {
            title: 'Visit card',
            content: 'Species, duration, temperature. Expand for detections over time. Open a clip for details.',
          },
        ],
      },
      operator: {
        description: 'Daily visits: filters by species and behavior; fixes and Re-ID nicknames on the visit card.',
        extraDetails: [
          {
            title: 'Re-ID',
            content: 'Link or unlink a bird profile (nickname) on the visit card when Re-ID is enabled.',
          },
        ],
      },
      admin: {
        description: 'Visit timeline; if a day is empty, check Library (on-disk archive) and processor status.',
        extraDetails: [],
      },
    },
    overview: {
      guest: {
        description: 'Feeder activity summary for the day: species, visits, weather, daily pattern.',
        extraDetails: [],
      },
      operator: {
        description: 'Activity dashboard for daily data-quality checks.',
        extraDetails: [],
      },
      admin: {
        description: 'Station overview; anomalies — Service logs and Station settings.',
        extraDetails: [],
      },
    },
    unknowns: {
      guest: {
        description: 'Review queue for uncertain detections. Browse recordings under Timeline and video details.',
        extraDetails: [],
      },
      operator: {
        description: 'Low-confidence detections: pick species and Apply. Same API as Correct species on the video page.',
        extraDetails: [
          {
            title: 'Expert queue',
            content: 'Semantic cases go to labelling; this page is for quick species fixes.',
          },
        ],
      },
      admin: {
        description: 'Queue threshold on Station. Pipeline issues — processor logs and behavior/detector metrics.',
        extraDetails: [],
      },
    },
    library: {
      guest: { description: 'Calendar of days with recording files on disk.', extraDetails: [] },
      operator: {
        description: 'Archive, disk import, dataset export. Watch clips under Timeline.',
        extraDetails: [],
      },
      admin: {
        description: 'Storage maintenance and backups; heavy jobs — check disk usage on the calendar first.',
        extraDetails: [],
      },
    },
    food: {
      guest: { description: 'Which feed types are marked active for visit context.', extraDetails: [] },
      operator: {
        description: 'Manage feed types; active feed is linked to new visits.',
        extraDetails: [],
      },
      admin: { description: 'Feed catalog and species attraction analytics.', extraDetails: [] },
    },
    migrationCalendar: {
      guest: { description: 'Seasonality: which months a species visited most.', extraDetails: [] },
      operator: {
        description: 'Monthly visit heatmap; click a species for its summary page.',
        extraDetails: [],
      },
      admin: {
        description: 'All SpeciesVisit history; export summaries separately for reports.',
        extraDetails: [],
      },
    },
  },
  zh: {
    videoDetails: {
      guest: {
        description: '自动记录的访问：视频、识别到的物种、行为及喂鸟器重量变化（如有）。',
        extraDetails: [
          { title: '物种', content: '系统从视频中估计的物种名称。' },
          { title: '行为', content: '识别到的简短活动标签（进食、休息、飞行等）。' },
          {
            title: '体重变化',
            content: '绿色向上表示访问期间增重，红色向下表示减轻；约 5 克以内的波动不显示。',
          },
        ],
      },
      operator: {
        description: '查看片段、物种、行为与体重。在此修正物种；昵称（Re-ID）在访问卡片上操作。',
        extraDetails: [
          { title: '修正物种', content: '在「检测到的物种」中使用「修正物种」，与「检查」页相同，需操作员权限。' },
          { title: 'Behavior v2.1', content: '可编辑片段行为标签；auto 模式下 v2.1 在处理时自动标注，操作员可覆盖。' },
          { title: '专家队列', content: '复杂语义案例进入标注/专家复核；框几何在「标注」，物种/行为在此。' },
        ],
      },
      admin: {
        description: '完整录像卡片及管理员字段：处理器版本、融合轨迹、「站点」阈值。',
        extraDetails: [
          { title: '站点与模型', content: '检测阈值、behavior 引擎（auto/shadow/canary）、OpenVINO — 站点 → 识别与处理器。' },
          { title: '融合轨迹', content: '检测管道轨迹合并调试，仅管理员。' },
        ],
      },
    },
    timeline: {
      guest: {
        description: '所选日期的访问列表：物种、时长、天气及卡片上的体重。',
        extraDetails: [{ title: '访问卡片', content: '物种、时长、温度；展开可查看时间线上的检测；点击片段查看详情。' }],
      },
      operator: {
        description: '当日访问：按物种与行为筛选；在访问卡片上修正并绑定 Re-ID 昵称。',
        extraDetails: [{ title: 'Re-ID', content: '启用 Re-ID 后可在访问卡片上绑定或解绑鸟类档案（昵称）。' }],
      },
      admin: {
        description: '访问时间线；若某日为空，请检查「数据」归档与处理器状态。',
        extraDetails: [],
      },
    },
    overview: {
      guest: { description: '当日喂鸟器活动概览：物种、访问次数、天气与日节律。', extraDetails: [] },
      operator: { description: '活动仪表板，用于日常数据质量检查。', extraDetails: [] },
      admin: { description: '站点总览；异常请查看「服务」日志与站点设置。', extraDetails: [] },
    },
    unknowns: {
      guest: { description: '不确定检测的复核队列。浏览录像请用「记录」与视频详情。', extraDetails: [] },
      operator: {
        description: '低置信度检测：选择物种并应用。与视频页「修正物种」相同 API。',
        extraDetails: [{ title: '专家队列', content: '语义案例进入标注；本页用于快速修正物种。' }],
      },
      admin: { description: '队列阈值在「站点」配置。管道问题请查处理器日志与 behavior/检测指标。', extraDetails: [] },
    },
    library: {
      guest: { description: '磁盘上有录像文件的日期日历。', extraDetails: [] },
      operator: { description: '归档、磁盘导入、数据集导出；在「记录」中观看片段。', extraDetails: [] },
      admin: { description: '存储维护与备份；重型操作前先查看日历中的磁盘占用。', extraDetails: [] },
    },
    food: {
      guest: { description: '当前标记为活跃的饲料类型，用于访问上下文。', extraDetails: [] },
      operator: { description: '管理饲料类型；活跃饲料与新访问关联。', extraDetails: [] },
      admin: { description: '饲料目录与吸引物种分析。', extraDetails: [] },
    },
    migrationCalendar: {
      guest: { description: '季节性：物种在哪些月份最常出现。', extraDetails: [] },
      operator: { description: '按月访问热力图；点击物种打开汇总页。', extraDetails: [] },
      admin: { description: '全部 SpeciesVisit 历史；报告请单独导出汇总。', extraDetails: [] },
    },
  },
};

function buildTier(base, patch) {
  const details = [...(base.details || [])];
  for (const d of patch.extraDetails || []) {
    details.push(d);
  }
  return {
    title: base.title,
    description: patch.description || base.description,
    details,
  };
}

for (const lang of ['ru', 'en', 'zh']) {
  const file = path.join(root, `${lang}.json`);
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  const langCopy = COPY[lang] || COPY.en;
  for (const [pageKey, base] of Object.entries(data.help || {})) {
    if (base && typeof base === 'object' && 'guest' in base) {
      continue;
    }
    const patches = langCopy[pageKey] || langCopy.videoDetails;
    const pagePatches = langCopy[pageKey] || {
      guest: { description: base.description, extraDetails: [] },
      operator: { description: base.description, extraDetails: [] },
      admin: { description: base.description, extraDetails: [] },
    };
    data.help[pageKey] = {
      guest: buildTier(base, pagePatches.guest),
      operator: buildTier(base, pagePatches.operator),
      admin: buildTier(base, pagePatches.admin),
    };
  }
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`);
  console.log(`patched ${lang}.json`);
}

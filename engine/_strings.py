"""_strings.py — bilingual UI-strings layer for the dashboard chrome.

The engine renders its own UI chrome (menu, headers, labels, buttons, section
titles, weekday/month names, status/due labels) through ``t()``. With
``instance.locale: en`` (default) the chrome stays English; with ``ru`` it
renders in Russian, restoring the original engine's look.

DATA is never translated here — client names, task titles, amounts, and any
content that comes from the instance's data files pass through untouched. Only
the engine's own literal chrome lives in this catalog.

Coverage is intentionally partial-safe: ``t(s)`` falls back to the English
key when no translation exists, so adding a ``t()`` call before its catalog
entry never crashes — it just renders English under ``ru`` until the pair is
added.

Distinct from ``_vocab.py``: that module is the data-token locale (keyword /
status matchers that read the instance's data). This module is the *display*
locale (the engine's own visible chrome).
"""

from _config import LOCALE


# ── UI catalog. KEY = the English string used in the code; value = its Russian
#    rendering (copied faithfully from the original engine). t('Dashboard')
#    returns 'Дашборд' under ru, 'Dashboard' under en (or any unknown locale).
UI = {
    'en': {},  # en is identity: the key IS the English string (see t()).
    'ru': {
        # ── _updater.py — "Update Saldo" affordance ─────────────────
        'Update available': 'Доступно обновление',
        'Update Saldo': 'Обновить Saldo',
        'A new version of Saldo is available': 'Доступна новая версия Saldo',
        "What's new": 'Что нового',
        'commits behind': 'отставание, коммитов',
        'latest': 'новейшая',
        'Press the button below, then paste into the chat with the assistant. Nothing is changed until you confirm.': 'Нажмите кнопку ниже и вставьте текст в чат с помощником. Ничего не изменится, пока вы не подтвердите.',
        'When you press the button, the assistant will:': 'Когда вы нажмёте кнопку, помощник:',
        'make a backup of your data': 'сделает резервную копию ваших данных',
        'download the new engine version': 'скачает новую версию движка',
        'show you exactly what will change and wait for your «yes»': 'покажет, что именно изменится, и дождётся вашего «да»',
        'apply the update, migrate your data, and rebuild the dashboard': 'применит обновление, перенесёт данные и пересоберёт дашборд',
        'check that everything works and report back': 'проверит, что всё работает, и отчитается',
        'Copy the update command': 'Скопировать команду обновления',
        'Copied.': 'Скопировано.',
        'Switch to the chat with the assistant, paste, and send.': 'Перейдите в чат с помощником, вставьте текст и отправьте.',
        'If the button does not work, just write to the assistant: «обнови систему Saldo» — it knows what to do.': 'Если кнопка не сработала, просто напишите помощнику: «обнови систему Saldo» — он знает, что делать.',
        'You are on the latest version. There is nothing to update right now. When a new version appears, an «Update available» item will show up in the menu on the left.': 'У вас самая свежая версия. Обновлять сейчас нечего. Когда появится новая версия, в меню слева появится пункт «Доступно обновление».',
        # ── _sidebar.py — left menu ───────────────────────────────────────
        'Dashboard': 'Дашборд',
        'Plan': 'План',
        'Today': 'Сегодня',
        'This Week': 'Неделя',
        'Month': 'Месяц',
        'Calendar': 'Календарь',
        'Periods': 'Периоды',
        'done': 'готово',
        'in progress': 'в работе',
        'clients': 'клиентов',
        'No monthly-cycle tasks.': 'Нет задач месячного цикла.',
        'Each open reporting period and how far each stage has progressed across clients.':
            'Каждый открытый отчётный период и насколько продвинулась каждая стадия по клиентам.',
        'Clients': 'Клиенты',
        'How to use': 'Как пользоваться',

        # ── _changelog.py / state-change audit ───────────────────────────
        'Changelog': 'Изменения',
        'Field-level log of every change to client state, newest first. '
        'Shows which fields moved, not their values.':
            'Пожурнальный лог всех изменений state клиентов, новые сверху. '
            'Показывает, какие поля менялись, без значений.',
        'No state changes recorded yet.': 'Изменений state пока нет.',
        'Week': 'Неделя',
        'Undated': 'Без даты',
        'changes': 'изменений',
        'added': 'добавлено',
        'removed': 'удалено',
        'changed': 'изменено',
        'State changes (7d)': 'Изменения state (7д)',
        'state changes': 'изменений state',
        'No state changes this week': 'За неделю изменений state нет',
        'View all state logs': 'посмотреть все логи',

        # ── _overview_shared.py — header & morning digest ─────────────────
        'Mail': 'Почта',
        'Anomalies': 'Аномалии',
        'News': 'Новости',
        'Updates': 'Обновления',
        'not run': 'не запущено',
        'records': 'записей',
        'Current time in Bali and Moscow': 'Сейчас на Бали и в Москве',
        'MSK': 'МСК',
        'Last daemon snapshot': 'Последний snapshot демонов',
        'read': 'читать',
        'No significant news': 'Значимых новостей нет',
        '(no subject)': '(без темы)',
        'from': 'от',
        'client': 'клиент',
        'No mail needs a reply': 'Писем требующих ответа нет',
        'updates need my decision': 'обновлений требуют моего решения',
        'Nothing was updated': 'Ничего не обновлялось',
        'Morning digest': 'Утренний дайджест',
        'Top news': 'Главное в новостях',
        'Top mail': 'Главное в почте',
        'Overnight auto-updates': 'Автообновления за ночь',

        # ── generate.py — summary labels (--print-summary) ────────────────
        'SOURCES': 'ИСТОЧНИКИ',
        'not started': 'не запущен',
        'no triggers': 'без триггеров',

        # ── _overview_v2.py — focus line, zones, filters, cards ────────────
        'Focus of the day:': 'Фокус дня:',
        'general': 'общее',
        'A day with no urgent tracks. A good time to tackle "what I don\'t remember" or push routine work forward.':
            'День без срочных треков. Хорошее время разобрать «что я не помню» или продвинуть рутину.',
        'WAITING': 'ЖДЁМ',
        'BLOCKED': 'БЛОК',
        'CLOSED': 'ЗАКРЫТ',
        'Track ': 'Трек ',
        '🎯 Active tracks': '🎯 Активные треки',
        'Client mental_models not found or contain no active tracks.':
            'Mental_model клиентов не найдены или не содержат активных треков.',
        'High priority': 'Высокий приоритет',
        '🔥 URGENT': '🔥 СРОЧНО',
        'Low priority': 'Низкий приоритет',
        'not urgent': 'не срочно',
        '⏳ Expectations': '⏳ Ожидания',
        'Nothing external pending': 'Ничего внешнего не ждём',
        'Remind': 'Напомнить',
        '❓ Awaiting clarification': '❓ Ждут пояснения',
        'Mental_models say everything is clear': 'Mental_model говорят, что всё понятно',
        'Clarify': 'Уточнить',
        '💬 Open in chat': '💬 Открыть в чате',
        'Dashboard →': 'Дашборд →',
        '👥 Clients': '👥 Клиенты',
        'All ': 'Все ',
        '↳ choice is remembered': '↳ выбор запоминается',
        'Bookkeeping — ': 'Бухгалтерия — ',

        # ── due-date chip / badge labels (shared across overview & plan) ───
        'overdue {}d': 'просрочено · {}дн',
        'today': 'сегодня',
        'in {}d · {}': 'через {}д · {}',
        '{} · {}d': '{} · {}д',
        'in {}d': 'через {}д',
        'and {} more': 'и ещё {}',
        'waiting {}d': 'ждём {}д',
        '🔥 Urgent': '🔥 Горит',
        '📅 This week': '📅 Неделя',
        'Nothing urgent': 'Срочного нет',
        'Nothing due this week': 'На этой неделе дедлайнов нет',

        # short weekday names (the plan grids wrap these as t('Mon') etc.;
        # they mirror the WEEKDAYS array but are also reachable via t()).
        'Mon': 'пн', 'Tue': 'вт', 'Wed': 'ср', 'Thu': 'чт',
        'Fri': 'пт', 'Sat': 'сб', 'Sun': 'вс',

        # scenario badge abbreviations (SCENARIO_RU values)
        'USN': 'УСН',
        'Tax no. (NPWP)': 'ИНН (NPWP)',
        'Reg. no. (NIB)': 'ОГРН (NIB)',
        'Legal form': 'Форма',
        'OKVED (KBLI)': 'ОКВЭД (KBLI)',
        'Capital': 'Капитал',
        'Investment': 'Инвестиции',
        'Scale': 'Масштаб',
        'Director': 'Директор',
        'Supervisor': 'Комиссар',
        'Management': 'Руководство',
        'OSNO': 'ОСНО',
        'PSN': 'ПСН',
        'NPD': 'НПД',
        'ESHN': 'ЕСХН',
        'USN+Patent': 'УСН+Патент',
        'WB+Patent': 'WB+Патент',
        'video+self-employed': 'видео+СЗ',
        'video+SE': 'видео+СЗ',
        'rental': 'аренда',
        'WB': 'WB',
        'AUSN': 'АУСН',

        # full regime labels — jurisdiction-pack object tokens (jurisdictions/
        # <code>/regimes.yaml) rendered on the operator surface via
        # _jurisdiction.render_regime_label. Keys must match the pack tokens
        # exactly (incl. the U+2212 minus in Income−Expenses).
        'USN Income': 'УСН Доходы',
        'USN Income−Expenses': 'УСН Доходы минус расходы',
        'AUSN Income': 'АУСН Доходы',
        '+ PSN': '+ ПСН',
        # id pack
        'UMKM final': 'UMKM',
        'UMKM final (turnover)': 'UMKM (оборот)',

        # ── _plan_today.py / _plan_week.py / _plan_month.py — page chrome ──
        'general ': 'общее ',
        'team': 'команда',
        'direct': 'прямой',
        '— empty —': '— пусто —',
        'Plan — Today': 'План — Сегодня',
        'Plan — Week': 'План — Неделя',
        'Plan — week · ': 'План — неделя · ',
        'Plan — Month': 'План — Месяц',
        'Plan — ': 'План — ',
        'Individual tasks': 'Отдельные задачи',
        'Operations (batchable)': 'Операции — можно пачкой',
        'No fixed date': 'Без точной даты',
        'active tracks and recurring processes': 'активные треки и регулярные процессы',
        'track': 'трек',
        'recurring': 'регулярная',
        'updater': 'апдейтер',
        'urgent/overdue ': 'срочное/просрочка ',
        'this week ': 'этой недели ',
        'planned ': 'планово ',
        'tax date': 'налоговая дата',

        # month names (nominative — for the Month page period label)
        'January': 'январь', 'February': 'февраль', 'March': 'март', 'April': 'апрель',
        'May': 'май', 'June': 'июнь', 'July': 'июль', 'August': 'август',
        'September': 'сентябрь', 'October': 'октябрь', 'November': 'ноябрь',
        'December': 'декабрь',

        # ── _plan_waves.py — wave page chrome & operation labels ───────────
        'Urgent — due in ≤ 7 days': 'Горит — дедлайн ≤ 7 дней',
        'Planned — this month': 'Плановое — этот месяц',
        'Backlog — no due date and later': 'Бэклог — без срока и дальше',
        'Waiting — on the client/bank side': '⏳ Ждём — на стороне клиента/банка',
        'Tasks': 'Задачи',
        '{} ready': '{} готовы',
        '{} waiting': '{} ждут',
        '{} blocked': '{} затык',
        'can run as a batch': 'можно пройти пачкой',
        'run the ready ones, follow up on the rest': 'запусти готовых, по остальным добор',
        'waiting on data — nothing to run yet': 'ждём данные — запускать пока нечего',
        '{} ready · {} waiting · {} blocked': '{} готовы · {} ждут · {} затык',
        'stands out from the wave': 'выбивается из волны',
        'Process the whole wave at once': 'Разобрать всю волну сразу',
        '🔍 Process wave': '🔍 Разобрать волну',
        'Dictate for the wave': 'Надиктовать по волне',
        '🎤 Dictate': '🎤 Надиктовать',
        'Expand all': 'Развернуть всё',
        'Process wave': 'Обработать волну',
        'Dictate': 'Надиктовать',
        'Collapse all': 'Свернуть всё',
        # wave operation labels (_OP_RU values)
        'bank check': 'проверка банка',
        'KUDIR posting': 'разноска КУДИР',
        'prepare payment order': 'сформировать ПП',
        'AUSN reconciliation': 'сверка АУСН',
        'AUSN monthly': 'АУСН помесячно',
        'AUSN markup review': 'разметка АУСН',
        'AUSN bank marking': 'разметка банка АУСН',
        'month close': 'закрытие месяца',
        'period close': 'закрытие периода',
        'month audit': 'аудит месяца',
        'cash register check': 'проверка кассы',
        'acquiring reconciliation': 'сверка эквайринга',
        'acquiring': 'эквайринг',
        'client service payment': 'оплата услуг клиентом',
        'Client clarifications': 'Вопросы и уточнения по клиентам',
        '❓ Open questions': '❓ Открытые вопросы',
        'tasks in flight': 'задач в работе',
        'observations': 'наблюдения',
        'Context': 'Контекст',
        'Top 3 for today': 'Топ-3 на сегодня',
        'Show all tasks': 'Показать все задачи',
        'unblocks {}': 'разблокирует {}',
        'no due date': 'без срока',
        'blocked, waiting on': 'заблокировано — ждёт',
        'Top for today': 'Главное на сегодня',
        'Show the rest': 'Показать остальные',
        'show {} more': 'показать ещё {}',
        'ENS reconciliation': 'сверка ЕНС',
        'self-employed receipts reconciliation': 'сверка чеков СЗ',
        'client follow-up': 'запрос у клиента',
        'client action': 'действие клиента',
        'source documents collection': 'сбор первички',
        'regulatory monitoring': 'регуляторный мониторинг',
        'regulatory': 'регуляторное',
        'routine check': 'рутинная проверка',
        'recurring task': 'регулярная задача',
        'reply to email': 'ответить на письмо',
        'NDFL register': 'регистр НДФЛ',
        'period recovery': 'восстановление периода',
        'tax return': 'декларация',
        'notification': 'уведомление',
        'sign payment order': 'подпись ПП',
        'patent': 'патент',
        'statistical reporting': 'статотчётность',
        'EGRIP extract': 'выписка ЕГРИП',
        'technical in 1C': 'техническое в 1С',
        'balance reconciliation': 'сверка сальдо',

        # ── _v2_sections.py — section titles ──────────────────────────────
        '(empty for now)': '(пока пусто)',
        'Financial model & trends': 'Финмодель и динамика',
        'Tax calendar 2026': 'Налоговый календарь 2026',
        'Work plan (2-3 months ahead)': 'План работы (2-3 мес вперёд)',
        'Red flags & risks': 'Красные флаги и риски',
        'Client behavior pattern': 'Паттерн поведения клиента',
        'Links between sources': 'Связи между источниками',
        'Key counterparty dossiers': 'Досье ключевых контрагентов',

        # ── _client_dashboard_v2.py — section titles & chrome ──────────────
        '🧭 Understanding snapshot': '🧭 Снимок понимания',
        'Firmly understood': 'Прочно понятно',
        'In progress': 'В процессе',
        'Not yet clarified': 'Не выяснено',
        '📜 Key decisions history': '📜 История ключевых решений',
        '📋 Client details': '📋 Реквизиты клиента',
        '⚠️ Client risks': '⚠️ Риски клиента',
        '📊 Periods': '📊 Периоды',
        '📅 Tax calendar 2026': '📅 Налоговый календарь 2026',
        '💰 Financial model and calendar': '💰 Финмодель и календарь',
        '🤝 Counterparties': '🤝 Контрагенты',
        '🏦 Accounts and registers': '🏦 Счета и кассы',
        '🏠 Real estate': '🏠 Недвижимость',
        '🗣 Client communication style': '🗣 Стиль клиента',
        '🔗 Quick access': '🔗 Быстрые доступы',
        '🔍 Review': '🔍 Разобрать',
        'Period': 'Период',
        'USN income': 'Доход УСН',
        'Taxes': 'Налоги',
        # KPI row labels (client dashboard top metrics)
        'Turnover': 'Оборот',
        'Headcount': 'Сотрудники',
        'pers.': 'чел',
        'net payroll': 'ФОТ нетто',
        'vs prev.': 'к пред.',
        'Next deadline': 'Ближайший срок',
        'in {} d.': 'через {} дн',
        'Annual pace': 'Годовой прогон',
        'Pace': 'Прогон',
        'annual': 'в год',
        'growth': 'рост',
        'forecast': 'прогноз',
        'est.': 'оценка',
        'fixed': 'фикс.',
        'under PKP threshold': 'под порогом PKP',
        'approaching PKP threshold': 'у порога PKP',
        'Status': 'Статус',
        'Date': 'Дата',
        'What': 'Что',
        'Amount': 'Сумма',
        'Task': 'Задача',
        # client details row labels
        'INN': 'ИНН', 'OGRNIP': 'ОГРНИП', 'Reg. date': 'Дата рег.', 'IFNS': 'ИФНС',
        'OKVED': 'ОКВЭД', 'Address': 'Адрес', 'Regime': 'Режим', 'Phone': 'Телефон',
        'Bank': 'Банк', 'BIK': 'БИК', 'Accounting': 'Учёт', 'Filing': 'Подача',
        'Signature': 'Подпись',
        'updated': 'обновлён',
        'Mental_model is empty or has no tracks': 'Mental_model пуста или треков нет',
        # quick-access
        'Service': 'Сервис', 'Open ↗': 'Войти ↗', 'login': 'логин', 'copy': 'копир.',
        'password': 'пароль', 'show': 'показать', 'hide': 'скрыть',
        'login/password needed': 'нужны логин/пароль',

        # ── _css.py — "prompt ready" copy-modal chrome ────────────────────
        'Prompt ready': 'Промпт готов',
        'Copy again': 'Скопировать снова',
        '✓ Copied — paste into Cowork (Ctrl+V)': '✓ Скопировано — вставьте в Cowork (Ctrl+V)',
        'Failed — select and press Ctrl+C, then Ctrl+V in Cowork':
            'Не удалось — выделите и нажмите Ctrl+C, затем Ctrl+V в Cowork',
        'Select the text and press Ctrl+C, then Ctrl+V in Cowork':
            'Выделите текст и нажмите Ctrl+C, затем Ctrl+V в Cowork',
        '✓ Copied': '✓ Скопировано',
        'Ctrl+C to copy': 'Ctrl+C чтобы скопировать',
        'Edit or dictate (Win+H) below, then paste into Cowork.':
            'Отредактируйте или надиктуйте (Win+H) ниже, затем вставьте в Cowork.',
        'Tip: <kbd>Win</kbd>+<kbd>H</kbd> is the built-in Windows dictation — it works in any text field, including this one.':
            'Подсказка: <kbd>Win</kbd>+<kbd>H</kbd> — встроенная диктовка Windows, работает в любом текстовом поле, в том числе в этом.',
        'Press Win+H to dictate, then Copy': 'Нажмите Win+H, чтобы надиктовать, затем «Скопировать»',
        'Task context · always included': 'Контекст задачи · добавляется всегда',
        'Write your own prompt or dictate (Win+H)…': 'Напишите свой промпт или надиктуйте (Win+H)…',
        'Review this client and propose today\'s priorities.':
            'Разбери клиента и предложи приоритеты на сегодня.',
        'Client': 'Клиент',
        'Break it down and propose the next step.': 'Разбери и предложи следующий шаг.',
        'Close the question: apply to state and remove it from open items.':
            'Закрой вопрос: применить к state и убрать из открытых.',
        'Clarify with the client — help me phrase the request.':
            'Уточнить у клиента — помоги сформулировать запрос.',
        'Defer it with a wake-up in a quarter.': 'Отложить с напоминанием через квартал.',
        "I'll answer differently — my answer: ": 'Отвечу иначе — мой ответ: ',

        # ── _track_modal.py — modal headings & buttons ────────────────────
        'Close': 'Закрыть',
        'Properties': 'Свойства',
        '📋 Particulars': '📋 Подробности',
        '📋 Context': '📋 Контекст',
        '🕒 Event history': '🕒 История событий',
        '🧭 System hypothesis': '🧭 Гипотеза системы',
        '🎯 Next action': '🎯 Следующее действие',
        '🔒 Dependencies': 'Зависит от',
        '🔓 Blocks': 'Блокирует',
        '📑 Details': '📑 Детали',
        '💬 Comments': '💬 Комментарии',
        '💬 Draft reply to client': '💬 Готовый ответ клиенту',
        '🔍 Break down': '🔍 Разобрать',

        # ── _track_attrs.py — task_type chip labels (localized via t()) ───
        'waiting externally': 'ждём внешнего',
        'regime question': 'вопрос по режиму',
        'investigation': 'разбор',
        'infrastructure': 'инфраструктура',
        'conversation with the team': 'разговор с командой',
        'long-term track': 'долгий трек',
        'wait externally, then act': 'ждём внешнее, потом действие',
        'multi-step preparation': 'многошаговая подготовка',
        'access request': 'запрос доступа',
        'data export': 'выгрузка данных',
        'strategic decision': 'стратегическое решение',
        'client departure': 'уход клиента',
        'preparation': 'подготовка',
        'documentation': 'документирование',
        'monitoring': 'мониторинг',
        'Coretax billing': 'начисление Coretax',
        'turnover collection': 'сбор оборота',
        # id pack (Indonesia) task-type labels -> operator locale (INSTRUCTIONS §0.1)
        'compute final tax 0.5%': 'расчёт налога 0,5%',
        'payroll': 'зарплата',
        'payroll: income tax + contributions': 'зарплата: подоходный + взносы',
        'withholding (rent/services)': 'удержания (аренда/услуги)',
        'tax payment': 'уплата налога',
        'record payment receipt': 'фиксация квитанции об уплате',
        'monthly tax return': 'ежемесячная декларация',
        'annual tax return': 'годовая декларация',
        'note': 'заметка',
        'data request': 'запрос данных',
        'access ready': 'доступ есть',
        'access with client': 'доступ у клиента',
        'access after first payment': 'после оплаты первого счёта',
        'request access': 'нужно запросить',
        'Income (turnover)': 'Выручка (оборот)',
        'taxes total': 'налоги, итого',
        # risk categories -> operator locale
        'business': 'бизнес',
        'client relationship': 'отношения с клиентом',
        'regulatory': 'регуляторное',
        'finance': 'финансы',
        'operations': 'операционное',
        'taxes': 'налоги',
        'accounting': 'учёт',
        'data gap': 'качество данных',
        'infrastructure': 'инфраструктура',
        'client behavior': 'поведение клиента',
        'tax regime': 'налоговый режим',
        'reporting': 'отчётность',
        'legal': 'юридическое',
        'control': 'контроль',
        'reconciliation': 'сверка',
        'review checkpoint': 'контрольная проверка',
        'tax calc': 'расчёт налога',
        'tax reconciliation': 'сверка по налогу',
        # ── _status.py — canonical status labels not already in the catalog ─
        'deferred': 'отложено',
        'archived': 'в архиве',

        # ── _track_attrs.py — status-badge display values ─────────────────
        'routine': 'рутина',
        'waiting': 'ждём',
        'closed': 'закрыт',
        'dropped': 'снят',

        # ── _analytics_widgets.py — stat cards (humanized EN; no SHOUTING) ──
        'Open items': 'В работе',
        'Overdue': 'Просрочено',
        'Due today': 'Сегодня',
        'Closed today': 'Закрыто сегодня',
        'Day streak': 'Дней подряд',
        # Top-5 / deadlines / activity widgets
        'Nothing urgent for today': 'На сегодня срочного нет',
        '🎯 Top-5 for today': '🎯 Топ-5 на сегодня',
        '→ full plan': '→ весь план',
        '📅 All deadlines': '📅 Все сроки',
        'ahead': 'впереди',
        'No deadlines': 'Сроков нет',
        '📋 Recent updates and decisions': '📋 Недавние действия и решения',
        'No task activity recorded in the last 2 weeks': 'За последние 2 недели действий не было',
        'yesterday': 'вчера',
        '{}d ago': '{} дн назад',
        '{}w ago': '{} нед назад',
        # activity action labels (_ACTION_LABELS values, passed through t())
        'Payment': 'Оплата',
        'Filed': 'Подано',
        'Client replied': 'Клиент ответил',
        'Document': 'Документ',
        'Status changed': 'Статус изменён',
        'Note': 'Заметка',
        'Decision recorded': 'Решение зафиксировано',
        'Updated': 'Обновлено',
        '{}d': '{} дн',

        # ── _brief.py — brief sentence + cards ─────────────────────────────
        '🧭 Brief for today': '🧭 Сводка на сегодня',
        'nothing urgent on you': 'срочного на вас нет',
        '{} awaiting your decision': '{} ждут вашего решения',
        'nearest due — {} {}': 'ближайший срок — {} {}',
        '{} long-standing questions can be closed': '{} давних вопросов можно закрыть',
        '🚩 Needs your decision': '🚩 Нужно ваше решение',
        'Nothing urgent on you — all under control': 'Срочного на вас нет — всё под контролем',
        'decision': 'решение',
        'stale for {}d': 'без движения {} дн',
        "❓ Let's clarify 1-2 things": '❓ Уточним 1–2 вещи',
        'helps close gaps': 'помогает закрыть пробелы',
        'pending {}d': 'ждёт {} дн',
        'question': 'вопрос',
        '{}d without movement': '{} дн без движения',
        'Ask the client': 'Спросить клиента',
        'Defer a quarter': 'Отложить на квартал',
        'recommended': 'рекомендуется',
        'answer differently': 'ответить иначе',
        'hypothesis:': 'гипотеза:',
        # analysis zone
        '{} active item in flight': 'в работе {} вопрос',
        '{} active items in flight': 'в работе {} вопросов',
        '; nearest due {} — {}': '; ближайший срок {} — {}',
        'due {}': 'срок {}',
        'updated {}': 'обновлено {}',
        'date ?': 'дата ?',
        'stale — refresh': 'устарело — обновить',
        'important': 'важно',
        'medium': 'средне',
        'later': 'позже',
        '🔍 Break it down': '🔍 Разобрать',
        'Recommendations': 'Рекомендации',
        '🧠 Analysis and recommendations': 'Сводка на сегодня',
        'judgment, not fact': 'оценка, не факт',

        # ── _assistant_brief.py — narrative sentence fragments ─────────────
        'tomorrow': 'завтра',
        'in 2 days': 'через 2 дня',
        ' +{} more': ' и ещё {}',
        'No urgent deadlines.': 'Срочных сроков нет.',
        'No deadlines.': 'Сроков нет.',
        ' and others': ' и другие',
        '{} — planned tracks, not urgent.': '{} — плановые треки, не срочно.',
        ' ({} more without a reply)': ' (ещё {} без ответа)',
        'Waiting for a reply from {} — {}d{}.': 'Ждём ответа от {} — {} дн{}.',
        'Today is {}.': 'Сегодня {}.',

        # ── _overview_v2.py — focus line, badges, cards ────────────────────
        'urgent tracks: {} (nearest — {}: {})': 'срочных треков: {} (ближайший — {}: {})',
        '{} more in the week zone': 'ещё {} в зоне недели',
        '{} awaiting an external signal': '{} ждут внешнего сигнала',
        '→ dashboard': '→ дашборд',
        'Blocked: {}': 'Заблокировано: {}',
        '(active {})': '(активных {})',
        '1 track': '1 трек',
        '{} tracks': '{} треков',

        # ── _plan_today.py — summary, group "show more" ────────────────────
        'Show {} more': 'Показать ещё {}',
        '{} tasks': '{} задач',
        '{} in the next 7 days': '{} в ближайшие 7 дней',
        '{} planned': '{} планово',
        '{} in backlog': '{} в бэклоге',
        '{} later': '{} дальше',
        'archive': 'архив',
        'archive (micro)': 'архив (микро)',
        'calculated': 'рассчитано',
        'invoice sent to client': 'счёт выставлен клиенту',
        'paid': 'оплачено',
        'current': 'текущий',
        'in progress': 'в работе',
        'scheduled': 'запланировано',
        'pending': 'ожидает',
        'archive (pre-switch)': 'архив (до перехода)',
        'waiting for statement': 'ждём выписку',
        'calculated, paid': 'рассчитано, оплачено',
        'calculated, checking payment': 'рассчитано, проверяем оплату',
        'current (AUSN)': 'текущий (АУСН)',
        'last serviced period': 'последний обслуженный период',
        'offset by contributions': 'перекрыто взносами',
        'scheduled (calc by fact)': 'запланировано (расчёт по факту)',
        'upcoming': 'предстоит',
        'overdue': 'просрочено',
        'sent': 'отправлено',
        'cancelled': 'отменено',
        'done': 'готово',
        'passed automatically': 'прошло автоматически',
        'waiting for Q1 statement': 'ждём выписку за 1 кв',
        'decision required': 'нужно решение',
        'checking payment': 'проверяем оплату',
        'solves problems herself': 'решает вопросы сама',
        'fast': 'быстро',
        'fast and active': 'быстро и активно',
        'moderate (occasional pauses due to travel)': 'умеренно (паузы из-за поездок)',
        'passive': 'пассивно',
        'self-managing': 'самостоятельно',
        'slow': 'медленно',
        'slow, polite': 'медленно, вежливо',
        'slow, with delays': 'медленно, с задержками',
        'technically competent': 'технически грамотно',
        'variable': 'переменно',
        'via team lead': 'через тимлида',
        'formal, concise': 'формально, кратко',
        'friendly': 'дружелюбно',
        'friendly, curious': 'дружелюбно, с интересом',
        'friendly, with emoji': 'дружелюбно, с эмодзи',
        'minimal': 'минимально',
        'minimal, via team': 'минимально, через команду',
        'polite': 'вежливо',
        'polite, thankful': 'вежливо, с благодарностью',
        'professional and active': 'профессионально и активно',
        'professional, technical': 'профессионально, технически',
        'short, factual': 'кратко, по делу',
        'via team': 'через команду',
        'informal (ty)': 'на «ты»',
        'formal (vy)': 'на «вы»',
        'formal, via team': 'формально, через команду',
        'neutral': 'нейтрально',
        'mixed': 'смешанно',
        'frequent': 'часто',
        'frequent (thanks)': 'часто (благодарности)',
        'none': 'нет',
        'occasional': 'иногда',
        'occasional (thanks)': 'иногда (благодарности)',
        'rare': 'редко',
        'team via assistant': 'команда через ассистента',
        'team via assistant and representative': 'команда через ассистента и представителя',
        'team via Finkoper': 'команда через Финкопер',
        'EDO': 'ЭДО',
        'email': 'эл. почта',
        'phone': 'телефон',
        'B2B (main)': 'B2B (основной)',
        'Supplier': 'поставщик',
        'Agent': 'агент',
        'Self-employed contractor': 'самозанятый исполнитель',
        'Self-employed supplier': 'самозанятый поставщик',
        'Bookkeeping provider (team lead)': 'бухсопровождение (рук. команды)',
        'gov orders': 'госзаказы',
        'marketplace': 'маркетплейс',
        'marketplace (taxi)': 'маркетплейс (такси)',
        'rental': 'аренда',
        'IT consulting': 'IT-консалтинг',
        'labor/individual contractors': 'физлица-исполнители',
        'monthly': 'ежемесячно',
        'payment processing': 'обработка платежей',
        'client (production)': 'клиент (продакшн)',
        'executor (production)': 'исполнитель (продакшн)',
        'rental (via aggregator)': 'аренда (через агрегатор)',
        'tenant': 'арендатор',
        'subcontractor SP': 'субподрядчик ИП',
        'creditor': 'кредитор',
        'property management': 'управление недвижимостью',
        'recruiting client': 'клиент (подбор персонала)',
        'recurring executor': 'исполнитель (регулярный)',
        'rental (short-term, agent)': 'аренда (краткосрочная, агент)',
        'rental income': 'доход от аренды',
        'services': 'услуги',
        'services buyer': 'покупатель услуг',
        'tenant (commercial)': 'арендатор (коммерческий)',
        'tenant (direct, long-term)': 'арендатор (прямой, долгосрочный)',
        'tenant (medical equipment)': 'арендатор (медоборудование)',
        'open questions:': 'открытые вопросы:',
        'tasks:': 'задачи:',
        'INN:': 'ИНН:',
        'likes:': 'нравится:',
        'dislikes:': 'не нравится:',
        'USN advance': 'аванс УСН',
        'Past in': 'Прошло в',
        'open question': 'открытый вопрос',
        'open questions': 'открытых вопросов',
        'Bank accounts': 'Счета в банках',
        'Foreign accounts': 'Зарубежные счета',
        'Registers and OFD': 'Кассы и ОФД',
        'Acquiring channels': 'Эквайринг',
        'Online banking access': 'Доступ к клиент-банку',
        'registering': 'регистрируется',
        'exists, details TBD': 'есть, детали уточнить',
        'archived': 'в архиве',
        'active': 'активна',
        'shifts': 'смен',
        'not confirmed': 'не подтверждено',
        'AUSN partner': 'банк-партнёр АУСН',
        'since': 'с',
        'closed': 'закрыт',
        'BIK changing': 'смена БИК',
        'KKT': 'ККТ',
        'Acquiring': 'Эквайринг',
        'Excel': 'Excel',
        '1C': '1С',
        '1C Fresh': '1С Fresh',
        '1C (cloud)': '1С (облако)',
        '1C on our server': '1С на сервере исполнителя',
        'team lead via Finkoper': 'тимлид через Финкопер',
        'client via FNS portal': 'клиент через ЛК ФНС',
        'Finkoper': 'Финкопер',
        'accountant': 'бухгалтер',
        'team lead': 'тимлид',
        'client': 'клиент',
        'client provides export/credentials': 'клиент даёт выгрузку/доступы',
        'client_provides_export_or_credentials': 'клиент даёт выгрузку/доступы',
        'no access': 'нет доступа',
        'view only': 'только просмотр',
        'full': 'полный',
        'via partner': 'через партнёра',
        'acquirer': 'эквайер',
        'payment gateway': 'платёжный шлюз',
        'payment service': 'платёжный сервис',
        'SP account': 'счёт ИП',
        'individual account': 'счёт физлица',
        'related entity': 'связанное лицо',
        'idle since connection': 'не используется с подключения',
        '{} tasks with deadlines this week': '{} задач со сроком на этой неделе',
        '{} tasks with deadlines this month': '{} задач со сроком в этом месяце',

        # ── _clients_group.py — group page chrome ──────────────────────────
        '{} task': '{} задача',
        '{} more': 'ещё {}',
        'profile': 'профиль',
        'A prose profile.md exists for this client': 'Для клиента есть текстовый profile.md',
        'No urgent tasks or anomalies': 'Срочных задач и аномалий нет',
        'No active tasks': 'Активных задач нет',
        '{} urgent': '{} срочных',
        '{} soon': '{} скоро',
        '{} ok': '{} в норме',
        'Clients — {}': 'Клиенты — {}',
        '{} {} clients': 'Клиентов в группе «{1}»: {0}',

        # ── _helpers._group_label / _mode_switch — group display names ─────
        'Team': 'Команда',
        'Direct': 'Прямые',
        'Ungrouped': 'Без группы',
        'All': 'Все',
        'All clients': 'Все клиенты',
        # owner report (one-pager)
        'Client report': 'Отчёт клиенту',
        'Turnover this month': 'Оборот за месяц',
        'Taxes & contributions — paid': 'Налоги и взносы — уплачены',
        'Taxes & contributions': 'Налоги и взносы',
        'No tax payments were due this month.': 'В этом месяце налоговых платежей не было.',
        'Total paid': 'Итого уплачено',
        "What's next": 'Что дальше',
        'Salaries paid; net payroll': 'Зарплата выплачена; фонд нетто',
        'Print / Save PDF': 'Печать / Сохранить PDF',
        'Prepared by': 'Подготовлено',
        'Final tax 0.5% (PP55)': 'Налог 0,5% (PP55)',
        'Final tax 0.5%': 'Налог 0,5%',
        'Payroll income tax (PPh 21)': 'Подоходный с зарплат (PPh 21)',
        'Rent withholding': 'Удержание с аренды',
        'Services withholding (PPh 23)': 'Удержание с услуг (PPh 23)',
        'Social insurance (BPJS)': 'Соцстрах (BPJS)',
        'Construction final tax': 'Налог со стройуслуг',
        'USN advance': 'Аванс УСН',
        '1% surplus': '1% с превышения',
        'Fixed contributions': 'Фиксир. взносы',
        'Main tax: 0.5% of turnover': 'Основной налог: 0,5% с оборота',
        'Income tax on salaries': 'Подоходный налог с зарплат',
        'Tax on rent paid': 'Налог с арендной платы',
        'Tax withheld on services': 'Удержано с оплаты услуг',
        'Employee social contributions': 'Соцвзносы за сотрудников',
        'Final tax on construction': 'Финальный налог со строительства',
        'Simplified-tax advance': 'Аванс по упрощёнке',
        '1% over the threshold': '1% сверх порога',
        'Fixed insurance contributions': 'Фиксированные страховые взносы',
        'Client report for the owner': 'Отчёт клиенту',
        # jurisdiction cheat-sheet panel
        'Jurisdiction cheat sheet': 'Шпаргалка по юрисдикции',
        'Tax authority': 'Налоговый орган',
        'Portal': 'Портал',
        'Currency': 'Валюта',
        'Social insurance': 'Соцстрах',
        'Term': 'Термин',
        'In plain terms': 'Простыми словами',
        # quick_access service map (migration 0006 builds these via t())
        'set access status': 'уточнить',
        'Finkoper — client card': 'Finkoper — карточка клиента',
        'Finkoper: tasks, chat, client documents.': 'Finkoper: задачи, чат, документы клиента.',
        '1C:Fresh': '1С:Фреш',
        '1C:Fresh: posting primary docs and reporting.': '1С:Фреш: разноска первички и отчётность.',
        'Bank — portal': 'ЛК банка',
        'Bank portal: statements and payment orders.': 'ЛК банка: выписки и платёжные поручения.',
        'FNS — personal cabinet': 'ЛК ФНС',
        'FNS cabinet: ENS reconciliation, notices, demands.': 'ЛК ФНС: сверка ЕНС, уведомления, требования.',
        'OFD — fiscal data operator': 'ЛК ОФД',
        'OFD cabinet: receipts and cash reports.': 'ЛК ОФД: отчёты по чекам и наличным.',
        'Acquiring': 'Эквайринг',
        'Acquiring: reconcile acquiring inflows.': 'Эквайринг: сверка эквайринговых поступлений.',
        'Rosstat — statistics portal': 'ЛК Росстата',
        'Rosstat: statistics reporting.': 'ЛК Росстата: статистическая отчётность.',
        # proper nouns / channel + service tokens (identity, to keep the i18n guard clean)
        'Telegram': 'Telegram',
        'whatsapp': 'WhatsApp',
        'coretax': 'Coretax',
        'onboarding': 'онбординг',
        'auto ausn': 'авто АУСН',
        'excel parallel for control': 'excel для сверки',
        'only': 'только',
        # i18n gaps found by the coverage guard (genuine UI chrome)
        'Real estate': 'Недвижимость',
        'Show all': 'Показать все',
        'Showing': 'Показано',
        'hidden': 'скрыто',
        'services': 'услуги',
        'creditor': 'кредитор',
        'submitted': 'сдано',
        'reconciled': 'сверено',
        'presumably paid': 'предположительно оплачено',
        'scheduled (conditional)': 'запланировано (условно)',
        'scheduled (finalization)': 'запланировано (финализация)',
        'unknown': 'неизвестно',
        'calculated, checking payment': 'рассчитано, проверяем оплату',

        # ── dictation (folded into the prompt modal) ──────────────────────
        'Dictate': 'Надиктовать',
        'Dictate your thoughts': 'Надиктуйте мысли',
        'Press <kbd>Win</kbd>+<kbd>H</kbd> in the field and speak — or type by hand.':
            'Нажмите <kbd>Win</kbd>+<kbd>H</kbd> в поле и говорите — или наберите вручную.',
        'Press Win+H and dictate here…': 'Нажмите Win+H и диктуйте сюда…',
        'Prompt copied to clipboard': 'Промпт скопирован в буфер',
        'Switch to the chat with Claude and paste (Ctrl+V).':
            'Перейдите в чат с Claude и вставьте (Ctrl+V).',
        'Copy as prompt': 'Скопировать как промпт',
        'Tip: <kbd>Win</kbd>+<kbd>H</kbd> is the built-in Windows dictation, it works in any text field. The card context is automatically appended to the copied prompt.':
            'Подсказка: <kbd>Win</kbd>+<kbd>H</kbd> — встроенная диктовка Windows, работает в любом текстовом поле. Контекст карточки добавляется к скопированному промпту автоматически.',
        'Dictate thoughts about this': 'Надиктовать мысль об этом',

        # ── _overview_shared.py — header ───────────────────────────────────
        'snapshot': 'снимок',

        # ── _client_dashboard_v2.py — communication-style prefixes ─────────
        'Speed:': 'Скорость:',
        'tone:': 'тон:',
        'emoji:': 'эмодзи:',

        # ── _track_modal.py — JS-side runtime chrome ───────────────────────
        'active': 'активен',
        'waiting (external)': 'ждём (внешнее)',
        'blocked': 'заблокирован',
        'cancelled': 'отменён',
        'high priority': 'высокий приоритет',
        'low priority': 'низкий приоритет',
        'stale for': 'без движения',
        'd': 'дн',
        'Related task': 'Связанная задача',
        'Action': 'Действие',
        'auto': 'авто',
    },
}


import re as _re
# Pictographic emoji are stripped from every chrome label so the UI uses the
# project's monochrome line icons (_icons.py) instead. Arrows (U+2190–21FF),
# triangles (U+25B8/25BE) and the middot live below U+2300 and are preserved.
_EMOJI_RE = _re.compile('[\U0001F000-\U0001FAFF⌀-➿⬀-⯿️⃣]')


# ── i18n coverage guard ────────────────────────────────────────────────────
# t() falls back to the English key when the active locale lacks a translation.
# For a non-EN operator that is a silent English leak. We record such misses so
# generate.py can surface them loudly (an untranslated operator string is a bug,
# per CLAUDE.md Invariant 4 — validate the operator-locale render, not just EN).
_T_MISS = set()


def _looks_untranslated(s):
    # Flag only human UI chrome, not data/enum tokens that happen to pass through t().
    if not s or len(s) < 4 or len(s) > 60:
        return False
    if '_' in s or '://' in s:          # snake_case identifiers / URLs are data
        return False
    if any(ch.isdigit() for ch in s):   # codes/dates are data
        return False
    try:
        s.encode('ascii')               # non-ASCII (e.g. Cyrillic) -> already localized
    except Exception:
        return False
    return bool(_re.search(r'[a-z]{2,}', s))   # has a lowercase word -> looks like EN UI


def i18n_misses():
    """Operator-facing strings that had no translation in the active locale."""
    return sorted(_T_MISS)


def t(s):
    """Return the localized chrome string for ``s`` (with emoji stripped).

    ``s`` is the English string used in code (the catalog key). Falls back to
    ``s`` itself when the active locale has no entry — so partial coverage
    renders English rather than crashing.
    """
    catalog = UI.get(LOCALE, UI['en'])
    if LOCALE != 'en' and s not in catalog and _looks_untranslated(s):
        _T_MISS.add(s)
    v = catalog.get(s, s)
    v = _EMOJI_RE.sub('', v)
    return _re.sub(r'\s{2,}', ' ', v).strip()


def tp(en, ru):
    """Localized free text (prompts / full sentences): pick ru under the ru locale,
    else en. Unlike t(), keeps the text verbatim (no emoji-stripping / whitespace
    collapsing) — for clipboard prompts where the wording must stay intact."""
    return ru if LOCALE == 'ru' else en


# ── Localized date arrays the date code needs (mirrors the original engine's
#    DAYS_RU / MONTHS_RU_GEN). Selected by LOCALE at import time.
_WEEKDAYS = {
    'en': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    'ru': ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'],
}
_WEEKDAYS_FULL = {
    'en': ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
           'Friday', 'Saturday', 'Sunday'],
    'ru': ['понедельник', 'вторник', 'среда', 'четверг',
           'пятница', 'суббота', 'воскресенье'],
}
_MONTHS_GEN = {
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July',
           'August', 'September', 'October', 'November', 'December'],
    'ru': ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
           'августа', 'сентября', 'октября', 'ноября', 'декабря'],
}

WEEKDAYS = _WEEKDAYS.get(LOCALE, _WEEKDAYS['en'])
WEEKDAYS_FULL = _WEEKDAYS_FULL.get(LOCALE, _WEEKDAYS_FULL['en'])
MONTHS_GEN = _MONTHS_GEN.get(LOCALE, _MONTHS_GEN['en'])

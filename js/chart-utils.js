// Преобразование ISO строки в timestamp для Lightweight Charts
function isoToUtcTimestamp(isoString) {
    if (!isoString) return null;
    try {
        // Удаляем миллисекунды если есть
        const dateStr = isoString.split('.')[0].replace('T', ' ');
        const date = new Date(dateStr + ' UTC');
        return date.getTime() / 1000; // Lightweight Charts ожидает секунды
    } catch (e) {
        console.error('Error parsing date:', isoString, e);
        return null;
    }
}

// Проверка, является ли индикатор осциллятором
function isOscillator(name) {
    if (!name || typeof name !== 'string') return false;

    const oscillatorNames = [
        'rsi', 'RSI', 'stoch', 'STOCH', 'stochastic', 'STOCHASTIC',
        'macd', 'MACD', 'awesome', 'Awesome', 'momentum', 'Momentum',
        'williams', 'Williams', 'wpr', 'WPR',
        'cci', 'CCI', 'mfi', 'MFI', 'stochrsi', 'StochRSI',
        'uo', 'UO', 'ao', 'AO', 'ac', 'AC',
        'atr', 'ATR', 'adx', 'ADX', 'roc', 'ROC',
        'obv', 'OBV', 'bop', 'BOP', 'cmf', 'CMF',
        'rvi', 'RVI', 'tsi', 'TSI', 'volume', 'VOLUME',
        'volatility', 'VOLATILITY', 'kvo', 'KVO', 'eom', 'EOM'
    ];

    const lowerName = name.toLowerCase();
    return oscillatorNames.some(oscName => lowerName.includes(oscName.toLowerCase()));
}

// Проверка, является ли индикатор трендовым (должен быть на основном графике)
function isTrendIndicator(name) {
    if (!name || typeof name !== 'string') return false;

    const trendIndicators = [
        'sma', 'SMA', 'ema', 'EMA', 'ma', 'MA', 'moving average', 'MOVING AVERAGE',
        'bb', 'BB', 'bollinger', 'Bollinger', 'bollinger bands', 'BOLLINGER BANDS',
        'ichimoku', 'Ichimoku', 'ichimoku cloud', 'ICHIMOKU CLOUD',
        'supertrend', 'Supertrend', 'SUPERTREND',
        'parabolic', 'Parabolic', 'sar', 'SAR', 'parabolic sar', 'PARABOLIC SAR',
        'keltner', 'Keltner', 'keltner channel', 'KELTNER CHANNEL',
        'donchian', 'Donchian', 'donchian channel', 'DONCHIAN CHANNEL',
        'vwap', 'VWAP', 'vwma', 'VWMA', 'hull', 'HULL', 'hma', 'HMA',
        'linear regression', 'LINEAR REGRESSION', 'lr', 'LR',
        'support', 'SUPPORT', 'resistance', 'RESISTANCE', 'trendline', 'TRENDLINE',
        'channel', 'CHANNEL', 'pivot', 'PIVOT'
    ];

    const lowerName = name.toLowerCase();

    // Проверяем, есть ли в названии трендовый индикатор
    const isTrend = trendIndicators.some(indicator =>
        lowerName.includes(indicator.toLowerCase())
    );

    return isTrend;
}

// Проверка, является ли индикатор объемным
function isVolumeIndicator(name) {
    if (!name || typeof name !== 'string') return false;

    const volumeIndicators = [
        'volume', 'VOLUME', 'obv', 'OBV', 'cmf', 'CMF',
        'mfi', 'MFI', 'vpt', 'VPT', 'nvi', 'NVI', 'pvi', 'PVI'
    ];

    const lowerName = name.toLowerCase();
    return volumeIndicators.some(indicator => lowerName.includes(indicator.toLowerCase()));
}

// Получение параметра из URL
function getQueryParam(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

// API запрос
async function apiGet(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Отображение таблицы сделок
function displayTradesTable(trades) {
    const tbody = document.getElementById('trades-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    trades.forEach((trade, index) => {
        const row = document.createElement('tr');

        // Форматируем даты
        const entryDate = new Date(trade.entry_time).toLocaleString('ru-RU');
        const exitDate = trade.exit_time ? new Date(trade.exit_time).toLocaleString('ru-RU') : '-';

        // Определяем направление на основе is_long
        const isLong = Boolean(trade.is_long);
        const directionClass = isLong ? 'trade-long' : 'trade-short';
        const profitClass = trade.pnl >= 0 ? 'profit-positive' : 'profit-negative';

        // Рассчитываем общее количество акций
        const tradeLots = Number(trade.lots) || 1;
        const totalShares = trade.totalShares || (tradeLots * (window.equityManager?.lotSize || 1) * (window.equityManager?.lotSizeFromDB || 1));

        row.innerHTML = `
            <td>${index + 1}</td>
            <td class="${directionClass}">${isLong ? 'Long' : 'Short'}</td>
            <td>${entryDate}</td>
            <td class="text-right">${trade.entry_price ? Number(trade.entry_price).toFixed(2) : '-'}</td>
            <td>${exitDate}</td>
            <td class="text-right">${trade.exit_price ? Number(trade.exit_price).toFixed(2) : '-'}</td>
            <td class="text-right">${tradeLots} × ${window.equityManager?.lotSize || 1} × ${window.equityManager?.lotSizeFromDB || 1} = ${totalShares.toFixed(0)} акц.</td>
            <td class="text-right ${profitClass}">${trade.pnl !== undefined ? trade.pnl.toFixed(2) : '-'}</td>
            <td class="text-right ${profitClass}">${trade.pnl_percent !== undefined ? trade.pnl_percent.toFixed(2) + '%' : '-'}</td>
            <td class="text-right">${trade.equity ? trade.equity.toFixed(2) : '-'}</td>
        `;

        tbody.appendChild(row);
    });
}

// Получение рекомендуемой высоты панели для индикатора
function getPanelHeightForIndicator(name) {
    if (!name) return 200;

    const lowerName = name.toLowerCase();

    if (lowerName.includes('macd') || lowerName.includes('stochastic')) {
        return 250; // MACD и Stochastic часто имеют несколько линий
    }

    if (lowerName.includes('volume')) {
        return 150; // Объемы обычно компактные
    }

    if (lowerName.includes('atr') || lowerName.includes('adx')) {
        return 200; // ATR и ADX средняя высота
    }

    return 200; // По умолчанию
}

// Экспорт функций в глобальную область видимости
window.isoToUtcTimestamp = isoToUtcTimestamp;
window.isOscillator = isOscillator;
window.isTrendIndicator = isTrendIndicator;
window.isVolumeIndicator = isVolumeIndicator;
window.getQueryParam = getQueryParam;
window.apiGet = apiGet;
window.displayTradesTable = displayTradesTable;
window.getPanelHeightForIndicator = getPanelHeightForIndicator;

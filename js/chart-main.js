let panelManager = null;
let candleSeries = null;
let tradeManager = null;
let equityManager = null;
let chartHotkeys = null;

// Определяем функцию isTrendIndicator локально, если она не определена в chart-utils.js
if (typeof window.isTrendIndicator === 'undefined') {
    window.isTrendIndicator = function(name) {
        const trendIndicators = [
            'sma', 'SMA', 'ema', 'EMA', 'ma', 'MA', 'moving',
            'bb', 'BB', 'bollinger', 'Bollinger',
            'ichimoku', 'Ichimoku', 'supertrend', 'Supertrend',
            'parabolic', 'Parabolic', 'sar', 'SAR',
            'keltner', 'Keltner', 'donchian', 'Donchian'
        ];

        if (!name) return false;

        const lowerName = name.toLowerCase();
        return trendIndicators.some(indicator =>
            lowerName.includes(indicator.toLowerCase())
        );
    };
}

function createZoomIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'zoom-indicator';
    indicator.id = 'zoom-indicator';
    indicator.style.display = 'none';
    document.body.appendChild(indicator);
    return indicator;
}

function showZoomIndicator(isZoomIn) {
    const indicator = document.getElementById('zoom-indicator');
    if (!indicator) return;

    indicator.textContent = isZoomIn ? 'Zoom In' : 'Zoom Out';
    indicator.style.display = 'block';

    setTimeout(() => {
        indicator.style.display = 'none';
    }, 1500);
}

function updateTradesCount(count) {
    const countElement = document.getElementById('trades-count');
    if (countElement) {
        countElement.textContent = `${count} сделок`;
    }
}

function getIndicatorColor(name) {
    const colors = [
        '#2196F3', '#4CAF50', '#FF9800', '#9C27B0',
        '#F44336', '#00BCD4', '#FF5722', '#607D8B',
        '#795548', '#3F51B5'
    ];

    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }

    const index = Math.abs(hash) % colors.length;
    return colors[index];
}

function processIndicatorData(indicatorArray) {
    if (!indicatorArray || !Array.isArray(indicatorArray)) return [];

    return indicatorArray
        .map(p => {
            if (!p) return null;
            const ts = isoToUtcTimestamp(p.time);
            return ts ? {
                time: ts,
                value: Number(p.value) || 0
            } : null;
        })
        .filter(p => p && Number.isFinite(p.value));
}

function createIndicatorPanel(panelManager, name, data, height = 200) {
    if (!data || data.length === 0) return null;

    console.log(`Creating panel for ${name} with ${data.length} data points`);

    const panel = panelManager.createChartPanel(name, height);

    // Настраиваем ось Y для осцилляторов
    panel.chart.priceScale().applyOptions({
        autoScale: true,
        scaleMargins: {
            top: 0.1,
            bottom: 0.1
        }
    });

    const lineSeries = panel.chart.addLineSeries({
        title: name,
        color: getIndicatorColor(name),
        lineWidth: 2
    });

    lineSeries.setData(data);
    panel.series.push(lineSeries);

    // Добавляем специальные уровни для разных типов осцилляторов
    addOscillatorLevels(panel, name, data);

    return panel;
}

function addOscillatorLevels(panel, name, data) {
    const lowerName = name.toLowerCase();

    // RSI - уровни 70 и 30
    if (lowerName.includes('rsi')) {
        const overboughtSeries = panel.chart.addLineSeries({
            title: 'Overbought (70)',
            color: 'rgba(239, 83, 80, 0.5)',
            lineWidth: 1,
            lineStyle: 2
        });
        overboughtSeries.setData([
            { time: data[0].time, value: 70 },
            { time: data[data.length - 1].time, value: 70 }
        ]);

        const oversoldSeries = panel.chart.addLineSeries({
            title: 'Oversold (30)',
            color: 'rgba(76, 175, 80, 0.5)',
            lineWidth: 1,
            lineStyle: 2
        });
        oversoldSeries.setData([
            { time: data[0].time, value: 30 },
            { time: data[data.length - 1].time, value: 30 }
        ]);

        panel.series.push(overboughtSeries, oversoldSeries);
    }

    // Stochastic - уровни 80 и 20
    else if (lowerName.includes('stoch')) {
        const overboughtSeries = panel.chart.addLineSeries({
            title: 'Overbought (80)',
            color: 'rgba(239, 83, 80, 0.5)',
            lineWidth: 1,
            lineStyle: 2
        });
        overboughtSeries.setData([
            { time: data[0].time, value: 80 },
            { time: data[data.length - 1].time, value: 80 }
        ]);

        const oversoldSeries = panel.chart.addLineSeries({
            title: 'Oversold (20)',
            color: 'rgba(76, 175, 80, 0.5)',
            lineWidth: 1,
            lineStyle: 2
        });
        oversoldSeries.setData([
            { time: data[0].time, value: 20 },
            { time: data[data.length - 1].time, value: 20 }
        ]);

        panel.series.push(overboughtSeries, oversoldSeries);
    }

    // Для осцилляторов, которые колеблются вокруг нуля - добавляем нулевую линию
    else if (lowerName.includes('atr') || lowerName.includes('adx') ||
             lowerName.includes('roc') || lowerName.includes('volatility') ||
             lowerName.includes('macd') || lowerName.includes('cci') ||
             lowerName.includes('ao') || lowerName.includes('awesome') ||
             lowerName.includes('mfi') || lowerName.includes('williams') ||
             lowerName.includes('uo') || lowerName.includes('bop') ||
             lowerName.includes('cmf') || lowerName.includes('rvi')) {

        const zeroLine = panel.chart.addLineSeries({
            title: 'Zero Line',
            color: 'rgba(150, 150, 150, 0.5)',
            lineWidth: 1,
            lineStyle: 2
        });
        zeroLine.setData([
            { time: data[0].time, value: 0 },
            { time: data[data.length - 1].time, value: 0 }
        ]);
        panel.series.push(zeroLine);
    }
}

async function main() {
    try {
        console.log('Initializing chart...');

        const sessionId = getQueryParam('sessionid');
        if (!sessionId) {
            alert('sessionid is required');
            return;
        }

        console.log('Loading session data...');
        const sessData = await apiGet(`api/optimization-session.php?id=${sessionId}`);
        console.log('Session data loaded:', sessData);

        const s = sessData.session;
        const trials = sessData.trials;

        document.getElementById('info-symbol').textContent = `${s.symbol_ticker} (${s.symbol_name}) ID:${s.symbol_id}`;
        document.getElementById('info-strategy').textContent = `${s.strategy_name} (${s.strategy_code})`;
        document.getElementById('info-timeframe').textContent = s.timeframe_table;
        document.getElementById('info-period').textContent = `${s.window_start} — ${s.window_end}`;

        let trial = trials.find(t => t.is_best == 1);
        if (!trial && trials.length) trial = trials[0];
        if (!trial) {
            alert('No trials found');
            return;
        }

        if (trial.params_json) {
            try {
                const params = JSON.parse(trial.params_json);
                const paramsText = Object.entries(params)
                    .map(([key, value]) => `${key}=${value}`)
                    .join(', ');
                document.getElementById('info-params').textContent = paramsText;
            } catch (e) {
                document.getElementById('info-params').textContent = '-';
            }
        } else {
            document.getElementById('info-params').textContent = '-';
        }

        console.log('Loading OHLC data...');
        const ohlcUrl = `api/ohlcv.php?symbol_id=${s.symbol_id}&timeframe_table=${encodeURIComponent(s.timeframe_table)}&start=${encodeURIComponent(s.window_start)}&end=${encodeURIComponent(s.window_end)}`;
        const ohlcData = await apiGet(ohlcUrl);
        console.log('OHLC data loaded:', ohlcData.candles?.length, 'candles');

        const rawCandles = ohlcData.candles || [];
        const candles = rawCandles
            .map(c => {
                if (!c) return null;
                const ts = isoToUtcTimestamp(c.time);
                return {
                    time: ts,
                    open: Number(c.open) || 0,
                    high: Number(c.high) || 0,
                    low: Number(c.low) || 0,
                    close: Number(c.close) || 0,
                    volume: Number(c.volume) || 0
                };
            })
            .filter(c => c && c.time !== null &&
                Number.isFinite(c.open) &&
                Number.isFinite(c.high) &&
                Number.isFinite(c.low) &&
                Number.isFinite(c.close));

        console.log('Filtered candles:', candles.length);
        if (!candles.length) {
            alert('No valid candles found');
            return;
        }

        let trades = [];
        let indicators = {};

        if (trial.trades_json) {
            try {
                trades = JSON.parse(trial.trades_json);
                console.log('Trades loaded:', trades.length);

                // Логируем структуру первой сделки для отладки
                if (trades.length > 0) {
                    console.log('First trade structure:', trades[0]);
                    console.log('Trade has is_long property:', 'is_long' in trades[0]);
                    console.log('Trade is_long value:', trades[0].is_long);
                    console.log('Trade direction (computed):', trades[0].is_long ? 'long' : 'short');
                }

                updateTradesCount(trades.length);
            } catch (e) {
                console.warn('Failed to parse trades_json:', e);
            }
        }

        if (trial.indicators_json) {
            try {
                indicators = JSON.parse(trial.indicators_json);
                console.log('Indicators loaded:', Object.keys(indicators));
            } catch (e) {
                console.warn('Failed to parse indicators_json:', e);
            }
        }

        // Загружаем размер лота из базы данных
        let lotSizeFromDB = 1; // По умолчанию 1
        try {
            const lotHistoryUrl = `api/lot-history.php?symbol_id=${s.symbol_id}`;
            const lotHistoryData = await apiGet(lotHistoryUrl);
            if (lotHistoryData && lotHistoryData.lotHistory && lotHistoryData.lotHistory.length > 0) {
                // Берем последнюю запись (самый актуальный размер лота)
                const latestLot = lotHistoryData.lotHistory.reduce((latest, current) => {
                    return new Date(current.change_date) > new Date(latest.change_date) ? current : latest;
                });
                lotSizeFromDB = Number(latestLot.lot_size) || 1;
                console.log(`Lot size from DB: ${lotSizeFromDB}`);
            } else {
                console.log('No lot history found, using default (1)');
            }
        } catch (e) {
            console.warn('Failed to load lot history, using default (1):', e);
        }

        // Создаем индикатор масштабирования
        createZoomIndicator();

        console.log('Initializing panel manager...');
        panelManager = new ChartPanelManager();
        panelManager.init();

        // ====== 1. СОЗДАЕМ ОСНОВНОЙ ГРАФИК (ТОЛЬКО СВЕЧИ И ТРЕНДОВЫЕ ИНДИКАТОРЫ) ======
        console.log('Creating price panel...');
        const pricePanel = panelManager.createChartPanel('Price', 450);

        // Добавляем свечи
        candleSeries = pricePanel.chart.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350'
        });
        candleSeries.setData(candles);

        // Добавляем объемы
        const volumeData = candles.map(c => ({
            time: c.time,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
        }));

        const volumeSeries = pricePanel.chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
            scaleMargins: { top: 0.8, bottom: 0 }
        });
        volumeSeries.setData(volumeData);

        pricePanel.chart.priceScale('volume').applyOptions({
            scaleMargins: { top: 0.8, bottom: 0 }
        });

        // ====== 2. ДОБАВЛЯЕМ ТРЕНДОВЫЕ ИНДИКАТОРЫ НА ОСНОВНОЙ ГРАФИК ======
        console.log('Adding trend indicators to main panel...');

        // Определяем, какие индикаторы трендовые и должны быть на основном графике
        const trendIndicatorsOnMainChart = {};
        const oscillatorsOnSeparatePanels = {};

        Object.keys(indicators).forEach(name => {
            if (window.isTrendIndicator(name)) {
                trendIndicatorsOnMainChart[name] = indicators[name];
            } else {
                oscillatorsOnSeparatePanels[name] = indicators[name];
            }
        });

        console.log('Trend indicators for main chart:', Object.keys(trendIndicatorsOnMainChart));
        console.log('Oscillators for separate panels:', Object.keys(oscillatorsOnSeparatePanels));

        // Добавляем трендовые индикаторы на основной график
        Object.keys(trendIndicatorsOnMainChart).forEach(name => {
            const indicatorData = processIndicatorData(trendIndicatorsOnMainChart[name]);

            if (indicatorData.length) {
                const lineSeries = pricePanel.chart.addLineSeries({
                    title: name,
                    color: getIndicatorColor(name),
                    lineWidth: 2
                });
                lineSeries.setData(indicatorData);
                pricePanel.series.push(lineSeries);
            }
        });

        // ====== 3. СОЗДАЕМ ОТДЕЛЬНЫЕ ПАНЕЛИ ДЛЯ ОСЦИЛЛЯТОРОВ ======
        console.log('Creating separate panels for oscillators...');

        Object.keys(oscillatorsOnSeparatePanels).forEach(name => {
            const indicatorData = processIndicatorData(oscillatorsOnSeparatePanels[name]);

            if (indicatorData.length) {
                createIndicatorPanel(panelManager, name, indicatorData, 200);
            }
        });

        // ====== 4. СОЗДАЕМ ПАНЕЛЬ ДЛЯ КРИВОЙ ЭКВИТИ ======
        console.log('Creating equity panel...');
        const equityPanel = panelManager.createChartPanel('Equity Curve', 250);

        equityManager = new EquityManager(equityPanel.chart);
        equityManager.setTrades(trades);
        equityManager.setLotSize(parseInt(document.getElementById('lotSize').value) || 10);
        equityManager.setLotSizeFromDB(lotSizeFromDB); // Устанавливаем размер лота из БД
        equityManager.update();

        // ====== 5. СОЗДАЕМ ПАНЕЛЬ ДЛЯ ТАБЛИЦЫ СДЕЛОК ======
        console.log('Creating trades panel...');
        panelManager.createTradesPanel();

        // ====== 6. ИНИЦИАЛИЗИРУЕМ МЕНЕДЖЕР СДЕЛОК ======
        console.log('Initializing trade manager...');
        tradeManager = new TradeManager(pricePanel.chart, candleSeries);
        tradeManager.setTrades(trades);
        tradeManager.update();

        // Сохраняем ссылки в глобальную область видимости
        window.panelManager = panelManager;
        window.equityManager = equityManager;
        window.tradeManager = tradeManager;

        // Настраиваем синхронизацию кроссхейра
        panelManager.syncCrosshair();

        // Настраиваем горячие клавиши
        chartHotkeys = new ChartHotkeys(panelManager);
        window.chartHotkeys = chartHotkeys;

        // Обновляем таблицу сделок
        updateTradesTable();

        // Настраиваем обработчики событий
        setupEventListeners();

        // Автоматически подгоняем данные при инициализации
        setTimeout(() => {
            if (pricePanel.chart) {
                pricePanel.chart.timeScale().fitContent();
            }
            // Прокручиваем контейнер вниз чтобы показать таблицу
            if (panelManager.container) {
                panelManager.container.scrollTop = panelManager.container.scrollHeight;
            }
        }, 500);

        console.log('Chart initialized successfully!');

    } catch (err) {
        console.error('Error during initialization:', err);
        alert('Error: ' + (err.message || 'Unknown error occurred'));
    }
}

function setupEventListeners() {
    console.log('Setting up event listeners...');

    const showTradeLines = document.getElementById('showTradeLines');
    const showEntryMarkers = document.getElementById('showEntryMarkers');
    const showExitMarkers = document.getElementById('showExitMarkers');
    const recalcEquity = document.getElementById('recalcEquity');
    const lotSizeInput = document.getElementById('lotSize');
    const resetSizesBtn = document.getElementById('resetSizes');

    if (showTradeLines) {
        showTradeLines.addEventListener('change', () => {
            if (tradeManager) tradeManager.update();
        });
    }

    if (showEntryMarkers) {
        showEntryMarkers.addEventListener('change', () => {
            if (tradeManager) tradeManager.update();
        });
    }

    if (showExitMarkers) {
        showExitMarkers.addEventListener('change', () => {
            if (tradeManager) tradeManager.update();
        });
    }

    if (recalcEquity && lotSizeInput) {
        recalcEquity.addEventListener('click', () => {
            const lotSize = parseInt(lotSizeInput.value) || 10;
            if (equityManager) {
                equityManager.setLotSize(lotSize);
                equityManager.update();
            }
            updateTradesTable();
        });
    }

    if (resetSizesBtn) {
        resetSizesBtn.addEventListener('click', () => {
            if (panelManager) {
                panelManager.resetAllHeights();
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && panelManager) {
            panelManager.panels.forEach(panel => {
                if (panel.chart) {
                    panel.chart.clearCrosshairPosition();
                }
            });
        }

        if (e.key === 'r' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            if (panelManager) {
                panelManager.resetAllHeights();
            }
        }
    });

    console.log('Event listeners set up');
}

function updateTradesTable() {
    console.log('Updating trades table...');
    if (!equityManager) {
        console.warn('Equity manager not initialized');
        return;
    }

    try {
        const tradesWithCapital = equityManager.getTradesWithCapital();
        displayTradesTable(tradesWithCapital);
        updateTradesCount(tradesWithCapital.length);
        console.log('Trades table updated:', tradesWithCapital.length, 'trades');
    } catch (err) {
        console.error('Error updating trades table:', err);
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
} else {
    main();
}

window.showZoomIndicator = showZoomIndicator;
window.getIndicatorColor = getIndicatorColor;

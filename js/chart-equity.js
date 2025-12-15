class EquityManager {
    constructor(chart) {
        this.chart = chart;
        this.trades = [];
        this.equitySeries = null;
        this.lotSize = 1; // Количество лотов для торговли (из интерфейса)
        this.lotSizeFromDB = 1; // Количество акций в лоте (из базы данных)
        this.initialCapital = 10000;
    }

    setTrades(trades) {
        this.trades = trades || [];
    }

    setLotSize(lotSize) {
        this.lotSize = lotSize || 1;
    }

    setLotSizeFromDB(lotSize) {
        this.lotSizeFromDB = lotSize || 1;
        console.log(`Lot size from DB set to: ${this.lotSizeFromDB}`);
    }

    update() {
        if (!this.equitySeries) {
            this.equitySeries = this.chart.addLineSeries({
                title: 'Equity',
                color: '#2196F3',
                lineWidth: 2
            });
        }

        const equityData = this.calculateEquityCurve();
        this.equitySeries.setData(equityData);
    }

    calculateEquityCurve() {
        if (!this.trades.length) return [];

        const equityData = [];
        let currentEquity = this.initialCapital;

        // Сортируем сделки по времени входа
        const sortedTrades = [...this.trades].sort((a, b) => {
            const timeA = a.entry_time ? new Date(a.entry_time).getTime() : 0;
            const timeB = b.entry_time ? new Date(b.entry_time).getTime() : 0;
            return timeA - timeB;
        });

        // Добавляем начальную точку
        const firstTradeTime = isoToUtcTimestamp(sortedTrades[0].entry_time);
        if (firstTradeTime) {
            equityData.push({
                time: firstTradeTime - 86400, // За день до первой сделки
                value: currentEquity
            });
        }

        // Рассчитываем equity после каждой сделки
        sortedTrades.forEach(trade => {
            if (!trade.entry_time || !trade.entry_price) return;

            const entryTime = isoToUtcTimestamp(trade.entry_time);
            if (!entryTime) return;

            // Перед сделкой
            equityData.push({
                time: entryTime - 1, // Непосредственно перед входом
                value: currentEquity
            });

            // Рассчитываем P&L
            let pnl = 0;
            let pnlPercent = 0;
            if (trade.exit_price && trade.exit_time) {
                const exitTime = isoToUtcTimestamp(trade.exit_time);
                if (exitTime) {
                    // Количество лотов в сделке (из данных или по умолчанию 1)
                    const tradeLots = Number(trade.lots) || 1;

                    // Общее количество акций = лоты в сделке × множитель из интерфейса × количество акций в лоте из БД
                    const totalShares = tradeLots * this.lotSize * this.lotSizeFromDB;

                    // Разница в цене
                    const priceDiff = Number(trade.exit_price) - Number(trade.entry_price);

                    // Расчет P&L в зависимости от направления (используем is_long)
                    const isLong = Boolean(trade.is_long);
                    if (isLong) {
                        pnl = priceDiff * totalShares;
                    } else {
                        pnl = -priceDiff * totalShares;
                    }

                    // Расчет процента P&L
                    pnlPercent = (pnl / currentEquity) * 100;

                    // После сделки
                    currentEquity += pnl;

                    equityData.push({
                        time: exitTime,
                        value: currentEquity
                    });

                    // Сохраняем P&L в сделку для таблицы
                    trade.pnl = pnl;
                    trade.pnl_percent = pnlPercent;
                    trade.equity = currentEquity;
                    trade.totalShares = totalShares; // Сохраняем общее количество акций
                    trade.direction = isLong ? 'long' : 'short'; // Добавляем direction для удобства
                }
            }
        });

        return equityData;
    }

    getTradesWithCapital() {
        return this.trades.map(trade => {
            // Убедимся, что у каждой сделки есть direction
            const isLong = Boolean(trade.is_long);
            return {
                ...trade,
                direction: isLong ? 'long' : 'short',
                equity: trade.equity || this.initialCapital
            };
        });
    }
}

window.EquityManager = EquityManager;

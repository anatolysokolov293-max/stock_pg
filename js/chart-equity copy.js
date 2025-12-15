class EquityManager {
    constructor(chart) {
        this.chart = chart;
        this.trades = [];
        this.equitySeries = null;
        this.lotSize = 1;
        this.initialCapital = 10000;
    }

    setTrades(trades) {
        this.trades = trades || [];
    }

    setLotSize(lotSize) {
        this.lotSize = lotSize || 1;
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
            if (trade.exit_price && trade.exit_time) {
                const exitTime = isoToUtcTimestamp(trade.exit_time);
                if (exitTime) {
                    const priceDiff = trade.exit_price - trade.entry_price;
                    pnl = trade.direction === 'long' ? priceDiff : -priceDiff;
                    pnl *= this.lotSize * 100; // Предполагаем, что 1 лот = 100 единиц

                    // После сделки
                    currentEquity += pnl;

                    equityData.push({
                        time: exitTime,
                        value: currentEquity
                    });

                    // Сохраняем P&L в сделку для таблицы
                    trade.pnl = pnl;
                    trade.pnl_percent = (pnl / currentEquity) * 100;
                    trade.equity = currentEquity;
                }
            }
        });

        return equityData;
    }

    getTradesWithCapital() {
        return this.trades.map(trade => ({
            ...trade,
            equity: trade.equity || this.initialCapital
        }));
    }
}

window.EquityManager = EquityManager;

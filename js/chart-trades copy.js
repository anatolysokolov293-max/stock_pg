// Управление отображением сделок

class TradeManager {
    constructor(mainChart, candleSeries) {
        this.mainChart = mainChart;
        this.candleSeries = candleSeries;
        this.trades = [];
        this.tradeLines = [];
    }

    setTrades(trades) {
        this.trades = trades;
    }

    updateMarkers() {
        if (!this.candleSeries || !this.trades.length) return;

        const showEntry = document.getElementById('showEntryMarkers').checked;
        const showExit = document.getElementById('showExitMarkers').checked;

        const markers = [];

        this.trades.forEach(t => {
            const entryTs = isoToUtcTimestamp(t.entry_time);
            const exitTs = isoToUtcTimestamp(t.exit_time);

            // Маркер входа
            if (showEntry && entryTs !== null) {
                markers.push({
                    time: entryTs,
                    position: t.is_long ? 'belowBar' : 'aboveBar',
                    color: t.is_long ? '#26a69a' : '#ef5350',
                    shape: t.is_long ? 'arrowUp' : 'arrowDown',
                    text: `${t.is_long ? 'LONG' : 'SHORT'} ${t.entry_price.toFixed(2)}`
                });
            }

            // Маркер выхода
            if (showExit && exitTs !== null && t.exit_price) {
                const profitColor = t.pnl >= 0 ? '#2196F3' : '#FF6B6B';
                markers.push({
                    time: exitTs,
                    position: t.is_long ? 'aboveBar' : 'belowBar',
                    color: profitColor,
                    shape: 'circle',
                    text: `EXIT ${t.exit_price.toFixed(2)} (${t.pnl_percent.toFixed(1)}%)`
                });
            }
        });

        this.candleSeries.setMarkers(markers);
    }

    updateLines() {
        if (!this.mainChart) return;

        // Удаляем старые линии
        this.tradeLines.forEach(line => {
            try {
                this.mainChart.removeSeries(line);
            } catch (e) {
                console.warn('Error removing line:', e);
            }
        });
        this.tradeLines = [];

        const showLines = document.getElementById('showTradeLines').checked;
        if (!showLines || !this.trades.length) return;

        // Создаем новые линии
        this.trades.forEach(t => {
            const entryTs = isoToUtcTimestamp(t.entry_time);
            const exitTs = isoToUtcTimestamp(t.exit_time);

            if (entryTs === null || exitTs === null || !t.exit_price) return;

            const lineColor = t.pnl >= 0 ? '#26a69a' : '#ef5350';

            const lineSeries = this.mainChart.addLineSeries({
                color: lineColor,
                lineWidth: 2,
                lineStyle: 2, // пунктирная
                crosshairMarkerVisible: false,
                lastValueVisible: false,
                priceLineVisible: false
            });

            lineSeries.setData([
                { time: entryTs, value: t.entry_price },
                { time: exitTs, value: t.exit_price }
            ]);

            this.tradeLines.push(lineSeries);
        });
    }

    update() {
        this.updateMarkers();
        this.updateLines();
    }
}

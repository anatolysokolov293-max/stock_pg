class ChartPanelManager {
    constructor() {
        this.panels = []; // Все графические панели (график + осцилляторы + equity)
        this.tradesPanel = null; // Панель таблицы сделок
        this.container = null;
        this.isZooming = false;
        this.zoomFactor = 1.1;
        this.defaultPanelHeight = 350;
        this.minPanelHeight = 150;
        this.maxPanelHeight = 800;
        this.timeScaleSyncEnabled = true;
    }

    init() {
        this.container = document.getElementById('charts-container');
        this.setupWheelZoom();
        this.loadPanelSizes();
    }

    setupWheelZoom() {
        this.container.addEventListener('wheel', this.handleWheel.bind(this), { passive: false });
    }

    handleWheel(event) {
        if (!event.ctrlKey && !event.metaKey) return;

        event.preventDefault();
        event.stopPropagation();

        const delta = event.deltaY || event.detail || event.wheelDelta;
        if (!delta) return;

        const targetPanel = this.getPanelAtPoint(event.clientX, event.clientY);
        if (!targetPanel || !targetPanel.chart) return;

        const zoomIn = delta < 0;

        if (window.showZoomIndicator) {
            window.showZoomIndicator(zoomIn);
        }

        this.zoomAllPanels(zoomIn, targetPanel.chart, event.clientX, event.clientY);
    }

    getPanelAtPoint(x, y) {
        const elements = document.elementsFromPoint(x, y);
        for (const element of elements) {
            const panelElement = element.closest('.chart-panel');
            if (panelElement) {
                const panelId = panelElement.id;
                return this.panels.find(p => p.id === panelId);
            }
        }
        return null;
    }

    zoomAllPanels(zoomIn, sourceChart, mouseX, mouseY) {
        if (this.isZooming || !this.timeScaleSyncEnabled) return;
        this.isZooming = true;

        try {
            const timeScale = sourceChart.timeScale();
            const visibleRange = timeScale.getVisibleRange();
            if (!visibleRange) {
                this.isZooming = false;
                return;
            }

            const chartRect = sourceChart.chartElement().getBoundingClientRect();
            const xRelative = mouseX - chartRect.left;
            const timeAtCoordinate = timeScale.coordinateToTime(xRelative);

            if (!timeAtCoordinate) {
                this.isZooming = false;
                return;
            }

            const rangeLength = visibleRange.to - visibleRange.from;
            const focusPosition = (timeAtCoordinate - visibleRange.from) / rangeLength;

            let newRangeLength;
            if (zoomIn) {
                newRangeLength = rangeLength / this.zoomFactor;
            } else {
                newRangeLength = rangeLength * this.zoomFactor;
            }

            const minRange = 60;
            const maxRange = 365 * 24 * 60 * 60;

            if (newRangeLength < minRange || newRangeLength > maxRange) {
                this.isZooming = false;
                return;
            }

            const newFrom = timeAtCoordinate - (newRangeLength * focusPosition);
            const newTo = newFrom + newRangeLength;

            // Применяем ко всем графическим панелям
            this.panels.forEach(panel => {
                if (panel.chart && panel.chart !== sourceChart) {
                    try {
                        panel.chart.timeScale().setVisibleRange({
                            from: newFrom,
                            to: newTo
                        });
                    } catch (e) {
                        console.warn('Error zooming panel:', e);
                    }
                }
            });

            timeScale.setVisibleRange({
                from: newFrom,
                to: newTo
            });

        } catch (e) {
            console.error('Error during zoom:', e);
        } finally {
            setTimeout(() => {
                this.isZooming = false;
            }, 50);
        }
    }

    createChartPanel(title, height = null) {
        const panelId = `panel-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const panelHeight = height || this.defaultPanelHeight;

        const panel = document.createElement('div');
        panel.className = 'chart-panel';
        panel.id = panelId;
        panel.style.height = `${panelHeight}px`;

        const titleDiv = document.createElement('div');
        titleDiv.className = 'chart-panel-title';
        titleDiv.textContent = title;
        panel.appendChild(titleDiv);

        const chartContainer = document.createElement('div');
        chartContainer.className = 'chart-container';
        panel.appendChild(chartContainer);

        const resizeHandle = document.createElement('div');
        resizeHandle.className = 'chart-panel-resize-handle';
        panel.appendChild(resizeHandle);

        const chart = LightweightCharts.createChart(chartContainer, {
            width: chartContainer.clientWidth,
            height: chartContainer.clientHeight,
            layout: {
                background: { color: '#ffffff' },
                textColor: '#333'
            },
            grid: {
                vertLines: { color: '#f0f0f0' },
                horzLines: { color: '#f0f0f0' }
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                borderVisible: false,
                rightOffset: 12,
                barSpacing: 6,
                minBarSpacing: 0.5,
                minBarSpacingMin: 0.1
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    width: 1,
                    color: 'rgba(33, 150, 243, 0.5)',
                    style: 0
                },
                horzLine: {
                    width: 1,
                    color: 'rgba(33, 150, 243, 0.5)',
                    style: 0
                }
            }
        });

        chart.chartElement = () => chartContainer;

        const resizeObserver = new ResizeObserver(entries => {
            for (let entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) {
                    chart.applyOptions({ width: width, height: height });
                }
            }
        });
        resizeObserver.observe(chartContainer);

        this.setupResizeHandle(resizeHandle, panel);

        const panelData = {
            id: panelId,
            element: panel,
            chart: chart,
            title: title,
            series: [],
            container: chartContainer,
            isChart: true
        };

        this.panels.push(panelData);
        this.container.appendChild(panel);

        // Настраиваем синхронизацию временной шкалы
        this.setupTimeScaleSync(panelData);

        return panelData;
    }

    createTradesPanel() {
        const tradesPanel = document.createElement('div');
        tradesPanel.className = 'trades-panel';
        tradesPanel.id = 'trades-panel';

        const header = document.createElement('div');
        header.className = 'trades-panel-header';
        header.innerHTML = '<span>Сделки</span><span id="trades-count">0 сделок</span>';
        tradesPanel.appendChild(header);

        const content = document.createElement('div');
        content.className = 'trades-panel-content';
        content.innerHTML = `
            <table id="trades-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Направление</th>
                        <th>Вход</th>
                        <th>Цена входа</th>
                        <th>Выход</th>
                        <th>Цена выхода</th>
                        <th>Лоты</th>
                        <th>P&L</th>
                        <th>P&L %</th>
                        <th>Капитал</th>
                    </tr>
                </thead>
                <tbody id="trades-table-body"></tbody>
            </table>
        `;
        tradesPanel.appendChild(content);

        this.container.appendChild(tradesPanel);
        this.tradesPanel = {
            element: tradesPanel,
            isChart: false
        };

        this.setupTradesPanelResize(header);

        return tradesPanel;
    }

    setupTradesPanelResize(header) {
        let isResizing = false;
        let startY = 0;
        let startHeight = 0;

        header.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();

            isResizing = true;
            startY = e.clientY;
            startHeight = this.tradesPanel.element.querySelector('.trades-panel-content').offsetHeight;
            header.classList.add('dragging');

            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        });

        const handleMouseMove = (e) => {
            if (!isResizing) return;

            const deltaY = startY - e.clientY;
            let newHeight = Math.max(100, startHeight + deltaY);
            newHeight = Math.min(600, newHeight);

            this.tradesPanel.element.querySelector('.trades-panel-content').style.height = `${newHeight}px`;
        };

        const handleMouseUp = () => {
            if (!isResizing) return;

            isResizing = false;
            header.classList.remove('dragging');

            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);

            this.savePanelSizes();
        };
    }

    setupResizeHandle(handle, panel) {
        let isResizing = false;
        let startY = 0;
        let startHeight = 0;

        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();

            isResizing = true;
            startY = e.clientY;
            startHeight = panel.offsetHeight;
            handle.classList.add('dragging');

            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        });

        const handleMouseMove = (e) => {
            if (!isResizing) return;

            const deltaY = e.clientY - startY;
            let newHeight = Math.max(this.minPanelHeight, startHeight + deltaY);
            newHeight = Math.min(this.maxPanelHeight, newHeight);

            panel.style.height = `${newHeight}px`;

            // Автоматически прокручиваем контейнер к измененной панели
            this.scrollToPanel(panel);
        };

        const handleMouseUp = () => {
            if (!isResizing) return;

            isResizing = false;
            handle.classList.remove('dragging');

            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);

            this.savePanelSizes();
        };
    }

    scrollToPanel(panel) {
        // Прокручиваем контейнер так, чтобы панель была видна
        if (this.container) {
            const panelRect = panel.getBoundingClientRect();
            const containerRect = this.container.getBoundingClientRect();

            if (panelRect.bottom > containerRect.bottom) {
                this.container.scrollTop += (panelRect.bottom - containerRect.bottom);
            }
        }
    }

    setupTimeScaleSync(panelData) {
        let isSyncing = false;

        panelData.chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
            if (isSyncing || !range || !this.timeScaleSyncEnabled) return;

            isSyncing = true;

            // Синхронизируем со всеми другими графическими панелями
            this.panels.forEach(p => {
                if (p.id !== panelData.id && p.chart) {
                    try {
                        const currentRange = p.chart.timeScale().getVisibleRange();
                        if (!this.rangesEqual(range, currentRange)) {
                            p.chart.timeScale().setVisibleRange(range);
                        }
                    } catch (e) {
                        console.warn('Error syncing time scale:', e);
                    }
                }
            });

            setTimeout(() => {
                isSyncing = false;
            }, 50);
        });
    }

    rangesEqual(range1, range2, epsilon = 0.001) {
        if (!range1 || !range2) return false;
        return Math.abs(range1.from - range2.from) <= epsilon &&
               Math.abs(range1.to - range2.to) <= epsilon;
    }

    savePanelSizes() {
        const sizes = {};

        // Сохраняем размеры графических панелей
        this.panels.forEach((panel, index) => {
            sizes[`panel_${index}`] = {
                height: panel.element.offsetHeight,
                title: panel.title
            };
        });

        // Сохраняем размер таблицы сделок
        if (this.tradesPanel && this.tradesPanel.element) {
            sizes.tradesPanel = this.tradesPanel.element.querySelector('.trades-panel-content').offsetHeight;
        }

        localStorage.setItem('chartSizes', JSON.stringify(sizes));
    }

    loadPanelSizes() {
        const savedSizes = localStorage.getItem('chartSizes');
        if (!savedSizes) return;

        try {
            const sizes = JSON.parse(savedSizes);

            Object.entries(sizes).forEach(([key, data], index) => {
                if (key === 'tradesPanel' && this.tradesPanel && this.tradesPanel.element) {
                    const tradesContent = this.tradesPanel.element.querySelector('.trades-panel-content');
                    if (tradesContent) {
                        tradesContent.style.height = `${data}px`;
                    }
                } else if (this.panels[index] && this.panels[index].title === data.title) {
                    let panelHeight = data.height || this.defaultPanelHeight;
                    panelHeight = Math.max(this.minPanelHeight, panelHeight);
                    panelHeight = Math.min(this.maxPanelHeight, panelHeight);
                    this.panels[index].element.style.height = `${panelHeight}px`;
                }
            });
        } catch (e) {
            console.error('Error loading panel sizes:', e);
        }
    }

    syncCrosshair() {
        // Синхронизируем кроссхейр между всеми графическими панелями
        this.panels.forEach(sourcePanel => {
            if (!sourcePanel.chart) return;

            sourcePanel.chart.subscribeCrosshairMove(param => {
                if (!param || !param.time) {
                    this.panels.forEach(p => {
                        if (p.id !== sourcePanel.id && p.chart) {
                            p.chart.clearCrosshairPosition();
                        }
                    });
                    return;
                }

                this.panels.forEach(targetPanel => {
                    if (targetPanel.id !== sourcePanel.id && targetPanel.chart) {
                        try {
                            targetPanel.chart.setCrosshairPosition(param.time, 0, null);
                        } catch (e) {
                            // Игнорируем ошибки
                        }
                    }
                });
            });
        });
    }

    getPanel(title) {
        return this.panels.find(p => p.title === title);
    }

    resetAllHeights() {
        // Сброс размеров графических панелей
        this.panels.forEach((panel, index) => {
            let defaultHeight = this.defaultPanelHeight;
            if (index === 0) defaultHeight = 450; // Основной график выше
            else if (panel.title === 'Equity Curve') defaultHeight = 250;
            else defaultHeight = 200; // Осцилляторы

            panel.element.style.height = `${defaultHeight}px`;
        });

        // Сброс размера таблицы сделок
        if (this.tradesPanel && this.tradesPanel.element) {
            const tradesContent = this.tradesPanel.element.querySelector('.trades-panel-content');
            if (tradesContent) {
                tradesContent.style.height = '300px';
            }
        }

        this.savePanelSizes();

        // Прокручиваем контейнер вниз чтобы показать таблицу
        setTimeout(() => {
            if (this.container) {
                this.container.scrollTop = this.container.scrollHeight;
            }
        }, 100);
    }
}

window.ChartPanelManager = ChartPanelManager;

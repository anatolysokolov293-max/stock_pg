class ChartHotkeys {
    constructor(panelManager) {
        this.panelManager = panelManager;
        this.setupHotkeys();
        console.log('Chart hotkeys initialized');
    }

    setupHotkeys() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Home' && !e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey) {
                e.preventDefault();
                this.resetZoom();
                return;
            }

            if (e.key === 'Home' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.fitAllData();
                return;
            }

            if (e.key === 'F11') {
                e.preventDefault();
                this.toggleFullscreen();
                return;
            }

            if (e.key === 'r' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.resetAll();
                return;
            }
        });
    }

    resetZoom() {
        console.log('Resetting zoom...');
        if (!this.panelManager || !this.panelManager.panels.length) return;

        const mainPanel = this.panelManager.panels[0];
        if (!mainPanel || !mainPanel.chart) return;

        try {
            mainPanel.chart.timeScale().fitContent();
            console.log('Zoom reset completed');
        } catch (e) {
            console.error('Error resetting zoom:', e);
        }
    }

    fitAllData() {
        console.log('Fitting all data...');
        if (!this.panelManager) return;

        this.panelManager.panels.forEach((panel, index) => {
            if (panel.chart) {
                try {
                    panel.chart.timeScale().fitContent();
                } catch (e) {
                    console.warn(`Error fitting data for panel ${index}:`, e);
                }
            }
        });

        console.log('All data fitted');
    }

    toggleFullscreen() {
        console.log('Toggling fullscreen...');
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(err => {
                console.log(`Error attempting to enable fullscreen: ${err.message}`);
            });
        } else {
            document.exitFullscreen();
        }
    }

    resetAll() {
        console.log('Resetting all charts...');
        if (!this.panelManager) return;

        this.fitAllData();

        this.panelManager.panels.forEach(panel => {
            if (panel.chart) {
                panel.chart.clearCrosshairPosition();
            }
        });

        if (this.panelManager.resetAllHeights) {
            this.panelManager.resetAllHeights();
        }

        console.log('All charts reset');
    }
}

window.ChartHotkeys = ChartHotkeys;

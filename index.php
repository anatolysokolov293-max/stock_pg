<?php
header('Content-Type: text/html; charset=utf-8');
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Результаты оптимизации стратегий</title>
    <style>
        body {
            font-family: sans-serif;
            margin: 20px;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid #ccc;
            padding: 4px 6px;
            text-align: center;
        }
        th {
            background: #f0f0f0;
        }
        td.heatcell {
            cursor: pointer;
        }
        td.heatcell.good {
            background: #c8f7c5;
        }
        td.heatcell.bad {
            background: #f7c5c5;
        }
        td.heatcell.neutral {
            background: #f7f7c5;
        }
        #modalOverlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.4);
            display: none;
            align-items: center;
            justify-content: center;
        }
        #modalWindow {
            background: #fff;
            padding: 15px;
            max-width: 900px;
            max-height: 90vh;
            overflow: auto;
            border-radius: 4px;
        }
        #modalClose {
            float: right;
            cursor: pointer;
        }
        .text-left {
            text-align: left;
        }
        .small {
            font-size: 12px;
            color: #555;
        }
    </style>
</head>
<body>
    <div style="margin: 10px 0; padding: 10px; border: 1px solid #ccc; background: #f8f8f8;">
    <strong>Сервисные ссылки:</strong>
    <!-- Здесь потом можно добавить больше служебных действий -->
    <a href="api/universe_ui.php" target="_blank" style="margin-left: 10px;">
        Отбор стратегий в universe (JSON)
    </a>
    </div>
    <h1>Результаты оптимизации стратегий</h1>

    <label for="symbolSelect">Символ:</label>
    <select id="symbolSelect"></select>
    <button id="reloadBtn">Обновить</button>

    <div id="matrix"></div>

    <div id="modalOverlay">
        <div id="modalWindow">
            <span id="modalClose">X</span>
            <div id="modalContent"></div>
        </div>
    </div>

    <script>
        async function apiGet(url) {
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        }

        async function loadSymbols() {
            const data = await apiGet('api/symbols.php');
            const sel = document.getElementById('symbolSelect');
            sel.innerHTML = '';
            data.symbols.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = `${s.ticker}${s.name ? ' - ' + s.name : ''}`;
                sel.appendChild(opt);
            });
        }

        async function loadMatrix() {
            const symbolId = document.getElementById('symbolSelect').value;
            if (!symbolId) return;

            const data = await apiGet(`api/strategy-summary.php?symbol_id=${symbolId}`);
            renderMatrix(data);
        }

        function renderMatrix(data) {
            const rows = data.rows;
            if (!rows.length) {
                document.getElementById('matrix').innerHTML = '<p>Нет данных.</p>';
                return;
            }

            const strategies = [];
            const timeframes = [];
            const cells = {};

            rows.forEach(r => {
                if (!strategies.find(s => s.id === r.strategy_id)) {
                    strategies.push({
                        id: r.strategy_id,
                        code: r.strategy_code,
                        name: r.strategy_name
                    });
                }
                if (!timeframes.includes(r.timeframe_table)) {
                    timeframes.push(r.timeframe_table);
                }
                cells[r.strategy_id] = cells[r.strategy_id] || {};
                cells[r.strategy_id][r.timeframe_table] = r;
            });

            const container = document.getElementById('matrix');
            container.innerHTML = '';

            const table = document.createElement('table');
            const thead = document.createElement('thead');
            const trHead = document.createElement('tr');
            const thEmpty = document.createElement('th');
            thEmpty.textContent = 'Стратегия';
            trHead.appendChild(thEmpty);

            timeframes.forEach(tf => {
                const th = document.createElement('th');
                th.textContent = tf;
                trHead.appendChild(th);
            });

            thead.appendChild(trHead);
            table.appendChild(thead);

            const tbody = document.createElement('tbody');
            strategies.forEach(st => {
                const tr = document.createElement('tr');
                const tdName = document.createElement('td');
                tdName.textContent = `${st.name} (${st.code})`;
                tdName.className = 'text-left';
                tr.appendChild(tdName);

                timeframes.forEach(tf => {
                    const td = document.createElement('td');
                    const cell = cells[st.id]?.[tf];
                    td.classList.add('heatcell');

                    if (cell) {
                        const v = parseFloat(cell.avg_best_value);
                        td.textContent = isNaN(v) ? '-' : v.toFixed(2);

                        if (isNaN(v)) {
                            td.classList.add('neutral');
                        } else if (v > 1.0) {
                            td.classList.add('good');
                        } else if (v < 0.0) {
                            td.classList.add('bad');
                        } else {
                            td.classList.add('neutral');
                        }

                        td.title = `avg: ${v.toFixed(2)}, min: ${parseFloat(cell.min_best_value).toFixed(2)}, max: ${parseFloat(cell.max_best_value).toFixed(2)}, sessions: ${cell.sessions_count}`;
                        td.onclick = () => openSessionsModal(st, tf);
                    } else {
                        td.textContent = '-';
                    }

                    tr.appendChild(td);
                });

                tbody.appendChild(tr);
            });

            table.appendChild(tbody);
            container.appendChild(table);
        }

        async function openSessionsModal(strategy, timeframeTable) {
            const symbolId = document.getElementById('symbolSelect').value;
            const url = `api/strategy-sessions.php?symbol_id=${symbolId}&strategy_id=${strategy.id}&timeframe_table=${encodeURIComponent(timeframeTable)}`;
            const data = await apiGet(url);
            renderSessionsModal(strategy, timeframeTable, data.sessions);
        }

        function showModal(html) {
            document.getElementById('modalContent').innerHTML = html;
            document.getElementById('modalOverlay').style.display = 'flex';
        }

        function hideModal() {
            document.getElementById('modalOverlay').style.display = 'none';
        }

        function renderSessionsModal(strategy, timeframeTable, sessions) {
            let html = `<h2>${strategy.name} (${strategy.code}) - ${timeframeTable}</h2>`;

            if (!sessions.length) {
                html += '<p>Нет сессий.</p>';
                showModal(html);
                return;
            }

            html += '<table><thead><tr><th>ID</th><th>Окно</th><th>Best Value</th><th>Trials</th><th>Статус</th><th>Детали</th></tr></thead><tbody>';

            sessions.forEach(s => {
                const w = `${s.window_start} - ${s.window_end}`;
                html += `<tr>
                    <td>${s.id}</td>
                    <td>${w}</td>
                    <td>${s.best_value != null ? parseFloat(s.best_value).toFixed(2) : '-'}</td>
                    <td>${s.n_trials}</td>
                    <td>${s.status}</td>
                    <td><button onclick="openSessionDetails(${s.id})">Открыть</button></td>
                </tr>`;
            });

            html += '</tbody></table>';
            showModal(html);
        }

        async function openSessionDetails(sessionId) {
            const data = await apiGet(`api/optimization-session.php?id=${sessionId}`);
            const s = data.session;
            const trials = data.trials;

            let html = `<h2>Сессия #${s.id}: ${s.strategy_name} (${s.strategy_code})</h2>`;
            html += `<p>${s.symbol_ticker}, ${s.timeframe_table}</p>`;
            html += `<p>${s.window_start} - ${s.window_end}</p>`;
            html += `<p>Метрика: ${s.target_metric}, Направление: ${s.direction}</p>`;
            html += `<p>Best Value: ${s.best_value != null ? parseFloat(s.best_value).toFixed(3) : '-'}</p>`;

            if (s.best_params) {
                try {
                    const params = JSON.parse(s.best_params);
                    html += '<h3>Лучшие параметры</h3><table><thead><tr><th>Параметр</th><th>Значение</th></tr></thead><tbody>';
                    Object.keys(params).forEach(k => {
                        html += `<tr><td>${k}</td><td>${params[k]}</td></tr>`;
                    });
                    html += '</tbody></table>';
                } catch(e) {}
            }

            html += '<h3>Trials</h3>';
            if (!trials.length) {
                html += '<p>Trials не найдены.</p>';
            } else {
                html += '<table><thead><tr><th>Trial</th><th>Best?</th><th>Target</th><th>Sharpe</th><th>MaxDD</th><th>PF</th><th>Trades</th><th>Cagr</th><th>Параметры</th><th>График</th></tr></thead><tbody>';

                trials.forEach(t => {
                    const params = (() => {
                        try { return JSON.parse(t.params_json); } catch(e) { return null; }
                    })();
                    const paramsStr = params ? Object.entries(params).map(([k,v]) => `${k}=${v}`).join(', ') : '';

                    html += `<tr>
                        <td>${t.trial_number != null ? t.trial_number : '-'}</td>
                        <td>${t.is_best ? '✓' : ''}</td>
                        <td>${t.target_metric_value != null ? parseFloat(t.target_metric_value).toFixed(3) : '-'}</td>

                        <td>${t.sharpe != null ? parseFloat(t.sharpe).toFixed(3) : '-'}</td>
                        <td>${t.max_dd != null ? parseFloat(t.max_dd).toFixed(2) : '-'}</td>
                        <td>${t.cagr != null ? parseFloat(t.cagr).toFixed(4) : '-'}</td>
                        <td>${t.profit_factor != null ? parseFloat(t.profit_factor).toFixed(2) : '-'}</td>
                        <td>${t.trades_count != null ? t.trades_count : '-'}</td>
                        <td class="text-left small">${paramsStr}</td>
                        <td><a href="chart.html?sessionid=${s.id}" target="_blank">График</a></td>
                    </tr>`;
                });

                html += '</tbody></table>';
            }

            showModal(html);
        }

        document.getElementById('reloadBtn').addEventListener('click', loadMatrix);
        document.getElementById('modalClose').addEventListener('click', hideModal);
        document.getElementById('modalOverlay').addEventListener('click', function(e) {
            if (e.target === this) hideModal();
        });

        async function init() {
            await loadSymbols();
            await loadMatrix();
        }

        document.getElementById('symbolSelect').addEventListener('change', loadMatrix);

        init();
    </script>
</body>
</html>

<?php
// universe_ui.php
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Отбор стратегий в universe</title>
    <style>
        body { font-family: Arial, sans-serif; font-size: 14px; }
        .toolbar { margin: 10px 0; padding: 10px; border: 1px solid #ccc; background: #f8f8f8; }
        table { border-collapse: collapse; width: 100%; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 4px 6px; text-align: right; }
        th { background: #eee; }
        td.left { text-align: left; }
        .diff-better { color: green; font-weight: bold; }
        .diff-worse { color: red; }
        .action-insert { background: #e0f0ff; }
        .action-update { background: #f0e0ff; }
    </style>
</head>
<body>

<h2>Отбор стратегий в universe</h2>

<div class="toolbar">
    <form id="filterForm" onsubmit="loadCandidates(); return false;">
        <label>
            Дата от (dd-mm-YYYY):
            <input type="text" id="dateFrom" placeholder="09-12-2025" style="width:110px;">
        </label>
        <label>
            до:
            <input type="text" id="dateTo" placeholder="11-12-2025" style="width:110px;">
        </label>
        &nbsp;&nbsp;
        <label>
            Min Sharpe:
            <input type="number" step="0.1" id="minSharpe" value="1.8" style="width:80px;">
        </label>
        <label>
            Min PF:
            <input type="number" step="0.1" id="minPF" value="1.3" style="width:80px;">
        </label>
        <label>
            Max DD %:
            <input type="number" step="1" id="maxDD" value="30" style="width:80px;">
        </label>
        <label>
            Min Trades:
            <input type="number" step="1" id="minTrades" value="10" style="width:80px;">
        </label>
        <label>
            Min CAGR %:
            <input type="number" step="1" id="minCagr" value="5" style="width:80px;">
        </label>
        &nbsp;&nbsp;
        <label>
            Min Score new:
            <input type="number" step="0.01" id="minScoreNew" value="0.0" style="width:80px;">
        </label>
        <label>
            Min Score old:
            <input type="number" step="0.01" id="minScoreOld" value="0.0" style="width:80px;">
        </label>
        &nbsp;
        <button type="submit">Загрузить кандидатов</button>
        <button type="button" onclick="applySelected()">Применить выбранное</button>
    </form>
</div>

<div id="summary"></div>
<div id="tableContainer"></div>

<script>
let lastLoadedItems = [];

async function loadCandidates() {
    const dateFrom  = document.getElementById('dateFrom').value.trim();
    const dateTo    = document.getElementById('dateTo').value.trim();
    const minSharpe = document.getElementById('minSharpe').value.trim();
    const minPF     = document.getElementById('minPF').value.trim();
    const maxDD     = document.getElementById('maxDD').value.trim();
    const minTrades = document.getElementById('minTrades').value.trim();
    const minCagr   = document.getElementById('minCagr').value.trim();

    const params = new URLSearchParams();
    if (dateFrom)  params.append('date_from', dateFrom);
    if (dateTo)    params.append('date_to', dateTo);
    if (minSharpe) params.append('min_sharpe', minSharpe);
    if (minPF)     params.append('min_pf', minPF);
    if (maxDD)     params.append('max_dd', maxDD);
    if (minTrades) params.append('min_trades', minTrades);
    if (minCagr)   params.append('min_cagr', minCagr);

    const url = 'select_universe.php?' + params.toString();

    document.getElementById('summary').textContent = 'Загрузка...';
    document.getElementById('tableContainer').innerHTML = '';

    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        let data = await resp.json();

        // Дополнительный фронтовый фильтр по Score
        const minScoreNew = parseFloat(document.getElementById('minScoreNew').value.trim() || '0');
        const minScoreOld = parseFloat(document.getElementById('minScoreOld').value.trim() || '0');

        data = data.filter(item => {
            const newM = item.metrics || item.new || {};
            const newScore = parseFloat(newM.final_score || newM.score || 0);

            if (newScore < minScoreNew) return false;

            if (minScoreOld > 0 && item.existing) {
                const oldScore = parseFloat(item.existing.score || 0);
                if (oldScore < minScoreOld) return false;
            }

            return true;
        });

        lastLoadedItems = data;
        renderTable(data);
    } catch (e) {
        document.getElementById('summary').textContent = 'Ошибка загрузки: ' + e.message;
    }
}

function renderTable(items) {
    if (!Array.isArray(items) || items.length === 0) {
        document.getElementById('summary').textContent = 'Кандидаты не найдены.';
        document.getElementById('tableContainer').innerHTML = '';
        return;
    }

    document.getElementById('summary').textContent = 'Найдено кандидатов: ' + items.length;

    let html = '<table>';
    html += '<tr>' +
        '<th></th>' +
        '<th class="left">Symbol</th>' +
        '<th>TF</th>' +
        '<th>Strategy</th>' +
        '<th>Action</th>' +
        '<th>Sharpe (old → new)</th>' +
        '<th>PF (old → new)</th>' +
        '<th>MaxDD% (old → new)</th>' +
        '<th>Trades (old → new)</th>' +
        '<th>CAGR% (old → new)</th>' +
        '<th>Score (old → new)</th>' +
        '</tr>';

    items.forEach((item, idx) => {
        const isInsert = item.action === 'insert';
        const trClass = isInsert ? 'action-insert' : 'action-update';

        let oldM = null;
        if (item.existing) {
            oldM = {
                sharpe: item.existing.sharpe,
                pf:     item.existing.pf,
                max_dd: item.existing.max_dd,
                trades: item.existing.trades,
                cagr:   item.existing.cagr,
                score:  item.existing.score,
            };
        }
        const newM = item.metrics || item.new;

        function diffCell(oldVal, newVal, format = v => v.toFixed(2)) {
            if (oldVal === null || oldVal === undefined || isNaN(oldVal)) {
                return format(newVal);
            }
            const cls = (newVal > oldVal) ? 'diff-better' : (newVal < oldVal ? 'diff-worse' : '');
            return '<span class="' + cls + '">' +
                format(oldVal) + ' → ' + format(newVal) +
                '</span>';
        }

        html += `<tr class="${trClass}">` +
            `<td><input type="checkbox" data-index="${idx}" checked></td>` +
            `<td class="left">${item.symbol}</td>` +
            `<td>${item.timeframe}</td>` +
            `<td>${item.strategy_id}</td>` +
            `<td>${isInsert ? 'INSERT' : 'UPDATE'}</td>` +
            `<td>` + (newM ? diffCell(oldM ? oldM.sharpe : null, newM.sharpe || 0) : '') + `</td>` +
            `<td>` + (newM ? diffCell(oldM ? oldM.pf     : null, newM.pf     || 0) : '') + `</td>` +
            `<td>` + (newM ? diffCell(oldM ? oldM.max_dd : null, newM.max_dd || 0, v => v.toFixed(1)) : '') + `</td>` +
            `<td>` + (newM ? diffCell(oldM ? oldM.trades : null, newM.trades || 0, v => v.toFixed(0)) : '') + `</td>` +
            `<td>` + (newM ? diffCell(oldM ? oldM.cagr   : null, newM.cagr   || 0) : '') + `</td>` +
            `<td>` + (newM ? diffCell(oldM ? oldM.score  : null, newM.final_score || newM.score || 0) : '') + `</td>` +
            `</tr>`;
    });

    html += '</table>';

    document.getElementById('tableContainer').innerHTML = html;
}

async function applySelected() {
    if (!lastLoadedItems || lastLoadedItems.length === 0) {
        alert('Нет загруженных кандидатов.');
        return;
    }

    const checkboxes = document.querySelectorAll('#tableContainer input[type="checkbox"][data-index]');
    const selected = [];

    checkboxes.forEach(cb => {
        if (cb.checked) {
            const idx = parseInt(cb.getAttribute('data-index'), 10);
            if (!isNaN(idx) && lastLoadedItems[idx]) {
                selected.push(lastLoadedItems[idx]);
            }
        }
    });

    if (selected.length === 0) {
        alert('Не выбрано ни одной записи.');
        return;
    }

    if (!confirm('Применить ' + selected.length + ' изменений в strategy_universe?')) {
        return;
    }

    try {
        const resp = await fetch('apply_universe.php', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(selected),
        });
        const res = await resp.json();
        if (!resp.ok || res.error) {
            throw new Error(res.error || ('HTTP ' + resp.status));
        }
        alert('Готово. Inserted: ' + res.inserted + ', Updated: ' + res.updated);
    } catch (e) {
        alert('Ошибка применения: ' + e.message);
    }
}
</script>

</body>
</html>

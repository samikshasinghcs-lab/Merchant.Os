// ======================================================
// MERCHANTOS — AG GRID REFUND MANAGEMENT
// FIXED: PRESERVES LEGACY REFUND LOADER
// AG GRID COMMUNITY 32.3.3
// ======================================================

(async function MerchantOSRefundGrid() {
    'use strict';

    const VERSION = '32.3.3';

    // --------------------------------------------------
    // LOAD AG GRID ASSETS
    // --------------------------------------------------

    const styles = [
        `https://cdn.jsdelivr.net/npm/ag-grid-community@${VERSION}/styles/ag-grid.css`,
        `https://cdn.jsdelivr.net/npm/ag-grid-community@${VERSION}/styles/ag-theme-quartz.css`
    ];

    styles.forEach(href => {
        if (!document.querySelector(`link[href="${href}"]`)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            document.head.appendChild(link);
        }
    });

    if (!window.agGrid) {
        await new Promise((resolve, reject) => {
            const script = document.createElement('script');

            script.src =
                `https://cdn.jsdelivr.net/npm/ag-grid-community@${VERSION}/dist/ag-grid-community.min.js`;

            script.onload = resolve;
            script.onerror = () =>
                reject(new Error('AG Grid failed to load'));

            document.head.appendChild(script);
        });
    }

    // --------------------------------------------------
    // GRID STYLING
    // --------------------------------------------------

    const style = document.createElement('style');

    style.textContent = `
        #refundGrid {
            width: 100%;
            height: 430px;
            margin-top: 18px;
            border-radius: 14px;
            overflow: hidden;
        }

        .ag-theme-quartz {
            --ag-font-family: 'DM Sans', sans-serif;
            --ag-font-size: 13px;
            --ag-background-color: #fbfaf6;
            --ag-foreground-color: #26372f;
            --ag-header-background-color: #edf1e9;
            --ag-header-foreground-color: #26372f;
            --ag-border-color: #dfe5dc;
            --ag-row-border-color: #e8ece5;
            --ag-row-hover-color: #eef4ed;
            --ag-header-height: 48px;
            --ag-row-height: 56px;
            --ag-wrapper-border-radius: 14px;
        }

        .ag-theme-quartz .ag-header-cell-text {
            font-weight: 700;
            letter-spacing: .04em;
        }

        .merchantos-grid-actions {
            display: flex;
            align-items: center;
            gap: 6px;
            height: 100%;
        }

        .merchantos-grid-actions button {
            cursor: pointer;
        }

        #refundGridError {
            padding: 14px;
            color: #a33;
        }
    `;

    document.head.appendChild(style);

    // --------------------------------------------------
    // FIND EXISTING REFUND TABLE
    // IMPORTANT: DO NOT DELETE #refundRows.
    // THE ORIGINAL DASHBOARD LOADER STILL USES IT.
    // --------------------------------------------------

    const refundRows = document.querySelector('#refundRows');

    if (!refundRows) {
        console.error('MerchantOS: #refundRows not found.');
        return;
    }

    const table = refundRows.closest('table');

    if (!table) {
        console.error('MerchantOS: Refund table not found.');
        return;
    }

    const wrapper = document.createElement('div');
    wrapper.id = 'merchantosRefundWrapper';

    const gridContainer = document.createElement('div');
    gridContainer.id = 'refundGrid';
    gridContainer.className = 'ag-theme-quartz';

    // Keep the original table in the DOM, hidden.
    // This prevents the existing load() function from breaking.
    table.hidden = true;

    table.parentNode.insertBefore(wrapper, table);

    wrapper.appendChild(gridContainer);
    wrapper.appendChild(table);

    // --------------------------------------------------
    // GRID CONFIGURATION
    // --------------------------------------------------

    const gridApi = window.agGrid.createGrid(gridContainer, {
        columnDefs: [
            {
                field: 'order_id',
                headerName: 'ORDER ID',
                flex: 1,
                minWidth: 140
            },
            {
                field: 'reason',
                headerName: 'REASON',
                flex: 1,
                minWidth: 140,
                valueFormatter: params =>
                    typeof window.label === 'function'
                        ? window.label(params.value)
                        : params.value || '—'
            },
            {
                headerName: 'AMOUNT',
                flex: 1,
                minWidth: 130,
                valueGetter: params => {
                    const data = params.data || {};

                    return typeof window.money === 'function'
                        ? window.money(data.amount, data.currency)
                        : `${data.currency || ''} ${data.amount ?? 0}`;
                }
            },
            {
                field: 'status',
                headerName: 'STATUS',
                flex: 1,
                minWidth: 130,
                cellRenderer: params => {
                    const badge = document.createElement('span');

                    badge.textContent = params.value || 'UNKNOWN';

                    badge.className =
                        'status s-' +
                        String(params.value || '')
                            .toLowerCase()
                            .replace(/[^a-z0-9_-]/g, '');

                    return badge;
                }
            },
            {
                headerName: 'ACTIONS',
                minWidth: 190,
                sortable: false,
                filter: false,
                cellRenderer: params => {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'merchantos-grid-actions';

                    const data = params.data || {};

                    if (data.status === 'PROPOSED') {
                        const approveButton =
                            document.createElement('button');

                        approveButton.type = 'button';
                        approveButton.textContent = 'Approve';
                        approveButton.className = 'mini';

                        approveButton.addEventListener('click', async event => {
                            event.stopPropagation();

                            if (typeof window.approve === 'function') {
                                approveButton.disabled = true;

                                try {
                                    await window.approve(data.id);
                                } finally {
                                    approveButton.disabled = false;
                                    await refreshRefundGrid();
                                }
                            }
                        });

                        const rejectButton =
                            document.createElement('button');

                        rejectButton.type = 'button';
                        rejectButton.textContent = 'Reject';
                        rejectButton.className = 'mini reject';

                        rejectButton.addEventListener('click', async event => {
                            event.stopPropagation();

                            if (typeof window.reject === 'function') {
                                rejectButton.disabled = true;

                                try {
                                    await window.reject(data.id);
                                } finally {
                                    rejectButton.disabled = false;
                                    await refreshRefundGrid();
                                }
                            }
                        });

                        wrapper.append(
                            approveButton,
                            rejectButton
                        );
                    } else {
                        wrapper.textContent = data.paypal_id || '—';
                    }

                    return wrapper;
                }
            }
        ],

        defaultColDef: {
            sortable: true,
            filter: true,
            resizable: true
        },

        rowData: [],

        pagination: true,
        paginationPageSize: 10,
        paginationPageSizeSelector: [10, 20, 50],
        animateRows: true
    });

    // --------------------------------------------------
    // REFRESH GRID DATA
    // Uses the existing api() helper so authentication
    // behaviour remains consistent with the application.
    // --------------------------------------------------

    let refreshing = false;

    async function refreshRefundGrid() {
        if (refreshing) return;

        refreshing = true;

        try {
            let refunds;

            if (typeof window.api === 'function') {
                refunds = await window.api('/api/refunds');
            } else {
                const response = await fetch('/api/refunds');

                if (!response.ok) {
                    throw new Error(
                        `Refund request failed: ${response.status}`
                    );
                }

                refunds = await response.json();
            }

            if (!Array.isArray(refunds)) {
                throw new Error('Unexpected refunds response format');
            }

            gridApi.setGridOption('rowData', refunds);

        } catch (error) {
            console.error(
                'MerchantOS: Refund grid refresh failed:',
                error
            );
        } finally {
            refreshing = false;
        }
    }

    // --------------------------------------------------
    // INITIAL LOAD
    // --------------------------------------------------

    await refreshRefundGrid();

    // --------------------------------------------------
    // REFRESH AFTER EXISTING ACTIONS
    // --------------------------------------------------

    if (typeof window.approve === 'function') {
        const originalApprove = window.approve;

        window.approve = async function (id) {
            const result = await originalApprove.call(this, id);
            await refreshRefundGrid();
            return result;
        };
    }

    if (typeof window.reject === 'function') {
        const originalReject = window.reject;

        window.reject = async function (id) {
            const result = await originalReject.call(this, id);
            await refreshRefundGrid();
            return result;
        };
    }

    // --------------------------------------------------
    // PERIODIC SYNCHRONIZATION
    // --------------------------------------------------

    window.merchantOSRefreshRefundGrid = refreshRefundGrid;

    setInterval(refreshRefundGrid, 30000);

    console.log(
        'MerchantOS: Refund grid initialized successfully.'
    );

})();

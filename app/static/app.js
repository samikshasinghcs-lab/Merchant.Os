const $ = x => document.getElementById(x);

const money = (n, cur) => {
    cur = cur || 'INR';
    return new Intl.NumberFormat(
        cur === 'INR' ? 'en-IN' : 'en-US',
        {
            style: 'currency',
            currency: cur,
            maximumFractionDigits: cur === 'INR' ? 0 : 2
        }
    ).format(n || 0);
};

const moneyMap = m => {
    let e = Object.entries(m || {}).filter(x => x[1] > 0);
    return e.length
        ? e.map(x => money(x[1], x[0])).join(' + ')
        : money(0);
};

const label = s =>
    (s || '').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());

async function api(path, opt = {}) {
    let r = await fetch('/api' + path, {
        headers: { 'Content-Type': 'application/json' },
        ...opt
    });

    let d;
    try {
        d = await r.json();
    } catch {
        throw Error('The server returned an invalid response.');
    }

    if (!r.ok) {
        throw Error(d.detail || 'Request failed');
    }

    return d;
}

// ==========================================
// DASHBOARD
// ==========================================

async function load() {
    let d = await api('/dashboard');

    $('mode').className = 'notice' + (d.demo ? '' : ' live');

    $('mode').textContent = d.demo
        ? 'DEMO MODE · Approvals are simulated locally; no money moves.'
        : 'PAYPAL MODE · Refunds call the configured PayPal environment.';

    $('metrics').innerHTML = [
        ['Orders', d.orders],
        ['Customer reviews', d.reviews],
        ['Open disputes', d.disputes],
        ['Refunded', moneyMap(d.refund_totals)]
    ].map(x => `
        <div class="metric">
            <span>${x[0]}</span>
            <strong>${x[1]}</strong>
        </div>
    `).join('');

    // Complaint clusters
    let cs = await api('/clusters');
    let max = Math.max(1, ...cs.map(x => x.count));

    $('clusterRows').innerHTML = cs.map(x => `
        <div class="row">
            <b>${label(x.cluster_id)}</b>
            <span style="float:right">${x.count}</span>
            <br>
            <small>
                ${x.high_count} high severity ·
                avg rating ${Number(x.avg_rating || 0).toFixed(1)}
            </small>
            <div class="bar">
                <i style="width:${x.count / max * 100}%"></i>
            </div>
            <br>
            <button class="mini" onclick="inspect('${x.cluster_id}')">
                Inspect & propose
            </button>
        </div>
    `).join('');

    // Refunds
    let rs = await api('/refunds');

    $('refundRows').innerHTML = rs.length
        ? rs.map(x => `
            <tr>
                <td>${x.order_id}</td>
                <td>${label(x.reason)}</td>
                <td>${money(x.amount, x.currency)}</td>
                <td>
                    <span class="status s-${x.status}">
                        ${x.status}
                    </span>
                </td>
                <td>
                    ${
                        x.status === 'PROPOSED'
                        ? `
                            <button class="mini"
                                onclick="approve('${x.id}')">
                                Approve
                            </button>
                            <button class="mini reject"
                                onclick="reject('${x.id}')">
                                Reject
                            </button>
                        `
                        : x.paypal_id || '—'
                    }
                </td>
            </tr>
        `).join('')
        : '<tr><td colspan="5">No proposals yet.</td></tr>';

    // Queue
    $('queue').innerHTML = `
        <div class="row">
            Pending approvals
            <b style="float:right">${d.pending}</b>
        </div>
        <div class="row">
            Refund proposals
            <b style="float:right">${rs.length}</b>
        </div>
        <div class="row">
            Gross order value
            <b style="float:right">${moneyMap(d.gross_totals)}</b>
        </div>
    `;

    // Disputes
    let ds = await api('/disputes');

    $('disputeRows').innerHTML = ds.map(x => `
        <div class="row">
            <b>${x.id}</b> · ${x.reason}
            <button class="mini"
                style="float:right"
                onclick="draft('${x.id}')">
                Draft reply
            </button>
            <br>
            <small>${x.status}</small>
        </div>
    `).join('');

    // Insights
    let ins = await api('/insights');

    $('insightRows').innerHTML =
        ins.findings.map(x => `
            <div class="finding">
                <b>${label(x.category)} · ${x.batch}</b>
                <p>
                    ${x.complaints} linked complaints ·
                    ${x.share_pct}% of all reviews
                </p>
            </div>
        `).join('') + `<p>${ins.caveat}</p>`;

    // Accountability
    let integrity = await api('/accountability');
    let k = integrity.operational_indicators;

    $('accountabilityRows').innerHTML = `
        <div class="row">
            Resolution cases
            <b style="float:right">${k.resolution_cases}</b>
        </div>
        <div class="row">
            Registered evidence items
            <b style="float:right">${k.evidence_items_registered}</b>
        </div>
        <div class="row">
            Orders with evidence
            <b style="float:right">${k.orders_with_registered_evidence}</b>
        </div>
        <div class="row">
            Audit events
            <b style="float:right">${k.audit_events_recorded}</b>
        </div>
        <div class="row">
            Open disputes
            <b style="float:right">${k.open_disputes}</b>
        </div>
        <p>${integrity.trust_methodology.reason}</p>
        <small>${integrity.trust_methodology.evidence_caveat}</small>
    `;

    // Audit
    let logs = await api('/audit');

    $('auditRows').innerHTML = logs.length
        ? logs.slice(0, 8).map(x => `
            <div class="row">
                <b>${x.event}</b> · ${x.entity}
                <br>
                <small>${new Date(x.created_at).toLocaleString()}</small>
            </div>
        `).join('')
        : '<p>No events yet.</p>';
}

// ==========================================
// ANALYZE BUTTON
// ==========================================

async function analyze() {
    const button = $('analyzeButton');
    const mode = $('mode');

    if (button) {
        button.disabled = true;
        button.textContent = 'Analyzing…';
    }

    try {
        await api('/analyze', { method: 'POST' });

        await load();

        if (mode) {
            mode.textContent = 'Analysis completed successfully.';
        }

    } catch (e) {
        if (mode) {
            mode.textContent = 'Analysis failed: ' + e.message;
        } else {
            alert(e.message);
        }

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = 'Analyze feedback';
        }
    }
}

// ==========================================
// CLUSTER INVESTIGATION
// ==========================================

async function inspect(id) {
    try {
        let d = await api('/clusters/' + encodeURIComponent(id));

        let sample = d.reviews
            .slice(0, 3)
            .map(x => '• ' + x.text)
            .join('\n');

        if (!confirm(
            `${label(id)} · ${d.reviews.length} reviews\n` +
            `${sample}\n\n` +
            'Create proposals only for exact order/customer matches?'
        )) return;

        let x = await api('/refunds/propose', {
            method: 'POST',
            body: JSON.stringify({ cluster_id: id })
        });

        alert(
            `${x.proposals.length} proposal(s) created. ${x.note}`
        );

        await load();

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// REFUNDS
// ==========================================

async function approve(id) {
    if (!confirm(
        'Approve this refund? Server-side caps and eligibility checks apply.'
    )) return;

    try {
        let x = await api('/refunds/' + id + '/approve', {
            method: 'POST'
        });

        alert(
            'Result: ' + x.status +
            '\n' + JSON.stringify(x.paypal)
        );

        await load();

    } catch (e) {
        alert(e.message);
    }
}

async function reject(id) {
    try {
        await api('/refunds/' + id + '/reject', {
            method: 'POST'
        });

        await load();

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// DISPUTES
// ==========================================

async function draft(id) {
    try {
        let x = await api('/disputes/' + id + '/draft', {
            method: 'POST'
        });

        $('draft').textContent =
            x.draft + '\n\nWARNING: ' + x.warning;

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// REVIEW IMPORT
// ==========================================

async function uploadReviews() {
    const f = $('reviewFile').files[0];

    if (!f) {
        alert('Choose a CSV file first.');
        return;
    }

    const fd = new FormData();
    fd.append('file', f);

    try {
        let r = await fetch(
            '/api/reviews/import/' + $('reviewSource').value,
            {
                method: 'POST',
                body: fd
            }
        );

        let d = await r.json();

        if (!r.ok) {
            throw Error(d.detail || 'Import failed');
        }

        $('importResult').innerHTML = `
            <div class="finding">
                Imported ${d.rows_imported} reviews ·
                ${d.duplicates_skipped} duplicates skipped ·
                ${d.rows_read} rows read.
            </div>
        `;

        await load();

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// SEMANTIC ANALYSIS
// ==========================================

async function runSemantic() {
    try {
        let d = await api('/reviews/semantic-analysis', {
            method: 'POST'
        });

        $('semanticRows').innerHTML = `
            <div class="finding">
                Analysed ${d.review_count} reviews ·
                method: ${d.method} ·
                threshold: ${d.threshold}
            </div>
        ` + d.clusters.map(c => `
            <div class="row">
                <b>${c.cluster_id}</b> ·
                ${c.count} reviews ·
                ${JSON.stringify(c.sentiment)}
                <br>
                <small>${c.keywords.join(', ')}</small>
                <br>
                <button class="mini"
                    onclick="explainCluster('${c.cluster_id}')">
                    Explain cluster
                </button>
            </div>
        `).join('');

        $('connectorInfo').textContent = d.caveat;

    } catch (e) {
        alert(e.message);
    }
}

async function explainCluster(id) {
    try {
        let d = await api(
            '/reviews/semantic-clusters/' +
            encodeURIComponent(id) +
            '/explanation'
        );

        $('investigationResult').innerHTML = `
            <h3>${id} explanation · ${d.provider}</h3>
            <p>${d.explanation}</p>
            <small>${d.warning || ''}</small>
            <pre>${JSON.stringify(d.facts, null, 2)}</pre>
        `;

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// CUSTOMER INVESTIGATION
// ==========================================

async function lookupCustomer() {
    let id = $('customerLookup').value.trim();

    if (!id) return;

    try {
        let d = await api('/customers/' + encodeURIComponent(id));

        $('investigationResult').innerHTML = `
            <h3>${d.customer_name || id}</h3>
            <p>
                ${d.reviews.length} reviews ·
                ${d.orders.length} orders
            </p>
        ` + d.reviews.map(r => `
            <div class="row">
                <b>${r.id}</b> ·
                ${r.sentiment || 'Not analysed'} ·
                ${r.text}
                <br>
                <small>
                    Order ref: ${r.order_id || 'none'} ·
                    ${r.cluster_id || 'no cluster'}
                </small>
                <br>
                <button class="mini"
                    onclick="showCandidates('${r.id}')">
                    Find order matches
                </button>
            </div>
        `).join('') + `
            <h3>Orders</h3>
        ` + d.orders.map(o => `
            <div class="row">
                ${o.id} · ${o.payment_status} ·
                ${o.currency} ${o.amount}
            </div>
        `).join('');

    } catch (e) {
        alert(e.message);
    }
}

async function showCandidates(reviewId) {
    try {
        let a = await api(
            '/reviews/' + reviewId + '/match-candidates'
        );

        let choices = a.map(x =>
            `${x.id} (${x.suggested_tier})`
        ).join('\n');

        let oid = prompt(
            'Candidate orders:\n' +
            (choices || 'No candidates') +
            '\n\nEnter exact order ID to associate:'
        );

        if (!oid) return;

        let tier = a.find(x => x.id === oid.trim())?.suggested_tier;

        if (!tier) {
            throw Error(
                'Choose an order returned by the candidate list.'
            );
        }

        let confirmMatch =
            tier === 'HIGH' ||
            confirm(
                'This is a MEDIUM customer-only match. ' +
                'Confirm association manually?'
            );

        let d = await api('/reviews/' + reviewId + '/match', {
            method: 'POST',
            body: JSON.stringify({
                order_id: oid.trim(),
                confirm: confirmMatch
            })
        });

        alert(`${d.tier}: ${d.next_step}`);

        lookupCustomer();

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// TRANSACTION INVESTIGATION
// ==========================================

async function lookupTransaction() {
    let id = $('transactionLookup').value.trim();

    if (!id) return;

    try {
        let d = await api(
            '/transactions/' + encodeURIComponent(id)
        );

        $('investigationResult').innerHTML = `
            <h3>Order ${d.order.id}</h3>
            <p>
                ${d.order.product} ·
                ${d.order.currency} ${d.order.amount} ·
                ${d.order.payment_status}
            </p>
            <p>
                PayPal order: ${d.order.paypal_order_id || '—'} ·
                Capture: ${d.order.capture_id || '—'}
            </p>

            <h3>Associated reviews (${d.reviews.length})</h3>
        ` + d.reviews.map(r => `
            <div class="row">
                ${r.id} · ${r.sentiment || 'Unanalysed'} · ${r.text}
            </div>
        `).join('') + `
            <h3>Refunds (${d.refunds.length})</h3>
        ` + d.refunds.map(r => `
            <div class="row">
                ${r.status} · ${r.currency} ${r.amount}
            </div>
        `).join('') + `
            <h3>Disputes (${d.disputes.length})</h3>
        ` + d.disputes.map(x => `
            <div class="row">
                ${x.id} · ${x.status} · ${x.reason}
            </div>
        `).join('') + `
            <h3>Evidence (${d.evidence.length})</h3>
        ` + d.evidence.map(x => `
            <div class="row">
                ${x.evidence_type} · ${x.description}
            </div>
        `).join('');

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// CONNECTOR INFORMATION
// ==========================================

(async () => {
    try {
        let c = await api('/reviews/connectors');

        $('connectorInfo').textContent =
            'Import adapters: ' +
            c.available_adapters.map(
                x => x.name + ' [' + x.status + ']'
            ).join(' · ');

    } catch (e) {
        console.error('Connector information unavailable:', e);
    }
})();

// ==========================================
// EVIDENCE UPLOAD
// ==========================================

async function uploadEvidence() {
    const f = $('evidenceFile').files[0];
    const order = $('evidenceOrder').value.trim();
    const desc = $('evidenceDescription').value.trim();

    if (!f || !order || !desc) {
        alert('Choose a file, enter an order ID and description.');
        return;
    }

    const fd = new FormData();
    fd.append('file', f);

    try {
        const q = new URLSearchParams({
            order_id: order,
            evidence_type: $('evidenceType').value,
            description: desc
        });

        let r = await fetch('/api/evidence/upload?' + q, {
            method: 'POST',
            body: fd
        });

        let d = await r.json();

        if (!r.ok) {
            throw Error(d.detail || 'Upload failed');
        }

        $('evidenceResults').innerHTML = `
            <div class="finding">
                Stored ${d.filename} · ${d.mime_type} ·
                ${d.size_bytes} bytes
                <br>
                SHA-256: ${d.sha256}
                <br>
                Integrity: ${d.integrity_status} ·
                Authenticity: NOT ESTABLISHED
            </div>
            <pre>${JSON.stringify(d.inspection, null, 2)}</pre>
        `;

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// PAYPAL DISPUTES
// ==========================================

async function syncPayPalDisputes() {
    try {
        let d = await api('/paypal/disputes/sync', {
            method: 'POST'
        });

        alert(`Synced ${d.synced} PayPal Sandbox disputes.`);

        let rows = await api('/paypal/disputes');

        $('paypalDisputeRows').innerHTML = rows.map(x => `
            <div class="row">
                <b>${x.dispute_id}</b> ·
                ${x.status} · ${x.deadline_state}
                <br>
                <small>
                    Due: ${x.response_due_at || 'Not supplied'} ·
                    ${x.reason}
                </small>
                <button class="mini"
                    onclick="showPayPalDispute('${x.dispute_id}')">
                    Inspect
                </button>
            </div>
        `).join('') || 'No disputes returned.';

    } catch (e) {
        alert(e.message);
    }
}

async function showPayPalDispute(id) {
    try {
        let d = await api(
            '/paypal/disputes/' + encodeURIComponent(id)
        );

        $('paypalDisputeDetail').textContent =
            JSON.stringify(d.payload, null, 2);

        $('submitDisputeId').value = id;

        let req = (d.payload.evidences || []).find(
            x => x.source === 'REQUESTED_FROM_SELLER'
        );

        if (req) {
            $('submitEvidenceType').value = req.evidence_type;
        }

    } catch (e) {
        alert(e.message);
    }
}

async function submitDisputeEvidence() {
    let id = $('submitDisputeId').value.trim();
    let type = $('submitEvidenceType').value.trim();

    let ids = $('submitEvidenceIds').value
        .split(',')
        .map(x => x.trim())
        .filter(Boolean);

    let notes = $('submitEvidenceNotes').value.trim();

    if (!id || !type || !ids.length) {
        alert(
            'Provide dispute ID, requested evidence type ' +
            'and uploaded evidence file IDs.'
        );
        return;
    }

    if (!confirm(
        'You are about to submit these merchant-selected files ' +
        'to PayPal Sandbox. Confirm that you reviewed the files ' +
        'and the dispute details.'
    )) return;

        let phrase = prompt('Type exactly: SUBMIT TO PAYPAL');

    if (phrase !== 'SUBMIT TO PAYPAL') {
        alert('Submission cancelled.');
        return;
    }

    try {
        let d = await api(
            '/paypal/disputes/' +
            encodeURIComponent(id) +
            '/submit-evidence',
            {
                method: 'POST',
                body: JSON.stringify({
                    human_approved: true,
                    confirmation: phrase,
                    evidence_type: type,
                    file_ids: ids,
                    notes
                })
            }
        );

        alert(
            'PayPal submission response received. Status: ' +
            d.status + '\n' +
            JSON.stringify(d.paypal_response)
        );

        $('paypalDisputeDetail').textContent =
            JSON.stringify(d, null, 2);

    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// PACT AGREEMENTS
// ==========================================

async function createPactAgreement() {
    try {
        let d = await api('/pact/agreements', {
            method: 'POST',
            body: JSON.stringify({
                title: $('pactTitle').value,
                description: $('pactDescription').value,
                currency: $('pactCurrency').value,
                total_amount: $('pactAmount').value,
                freelancer_name: $('pactFreelancer').value,
                customer_name: $('pactCustomer').value,
                milestones: $('pactMilestonesJson').value.trim()
                    ? JSON.parse($('pactMilestonesJson').value)
                    : undefined
            })
        });

        $('pactAgreementId').value = d.id;
        $('pactAgreementDetail').textContent =
            JSON.stringify(d, null, 2);

        await loadPactAgreements();
    } catch (e) {
        alert(e.message);
    }
}

async function loadPactAgreements() {
    try {
        let a = await api('/pact/agreements');

        $('pactAgreementList').innerHTML = a.map(x => `
            <div class="row">
                <b>${x.title}</b> · ${x.status} ·
                ${x.currency} ${x.total_amount}
                <button class="mini"
                    onclick="
                    document.getElementById('pactAgreementId').value='${x.id}';
                    loadPactAgreement()">
                    Open ${x.id}
                </button>
            </div>
        `).join('');
    } catch (e) {
        console.error(e);
    }
}

async function loadPactAgreement() {
    try {
        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value)
        );

        $('pactAgreementDetail').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

async function approvePactAgreement() {
    try {
        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value) +
            '/approve',
            {
                method: 'POST',
                body: JSON.stringify({
                    party_role: $('pactRole').value,
                    party_name: $('pactPartyName').value,
                    decision: $('pactDecision').value
                })
            }
        );

        $('pactAgreementDetail').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

async function createPactChange() {
    try {
        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value) +
            '/scope-changes',
            {
                method: 'POST',
                body: JSON.stringify({
                    requested_by: $('pactRole').value,
                    request_text: $('pactChangeText').value
                })
            }
        );

        $('pactChangeId').value = d.id;
        $('pactChangeDetail').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

async function approvePactChange() {
    try {
        let d = await api(
            '/pact/scope-changes/' +
            encodeURIComponent($('pactChangeId').value) +
            '/approve',
            {
                method: 'POST',
                body: JSON.stringify({
                    party_role: $('pactChangeRole').value,
                    party_name: $('pactChangeName').value,
                    decision: 'APPROVE'
                })
            }
        );

        $('pactChangeDetail').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

async function submitPactMilestoneEvidence() {
    try {
        let ids = $('pactEvidenceIds').value
            .split(',')
            .map(x => x.trim())
            .filter(Boolean);

        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value) +
            '/milestones/' +
            encodeURIComponent($('pactMilestoneId').value) +
            '/evidence',
            {
                method: 'POST',
                body: JSON.stringify({
                    evidence_ids: ids,
                    actor: 'freelancer'
                })
            }
        );

        alert('Evidence submitted for customer review.');

        $('pactAgreementDetail').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

async function reviewPactMilestone() {
    try {
        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value) +
            '/milestones/' +
            encodeURIComponent($('pactMilestoneId').value) +
            '/review',
            {
                method: 'POST',
                body: JSON.stringify({
                    decision: $('pactMilestoneDecision').value,
                    party_name: $('pactMilestoneCustomer').value
                })
            }
        );

        $('pactAgreementDetail').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

async function loadPactIndicators() {
    try {
        $('pactIndicators').textContent =
            JSON.stringify(await api('/pact/indicators'), null, 2);
    } catch (e) {
        console.error(e);
    }
}

// ==========================================
// PACT PAYMENTS
// ==========================================

async function pactCreateAuthorizationOrder() {
    try {
        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value) +
            '/milestones/' +
            encodeURIComponent($('pactMilestoneId').value) +
            '/payment/authorize-order',
            { method: 'POST' }
        );

        $('pactPaymentResult').textContent =
            JSON.stringify(d, null, 2);

        if (d.approval_url) {
            window.open(d.approval_url, '_blank');
        }
    } catch (e) {
        alert(e.message);
    }
}

async function pactAuthorizePayment() {
    try {
        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value) +
            '/milestones/' +
            encodeURIComponent($('pactMilestoneId').value) +
            '/payment/authorize',
            { method: 'POST' }
        );

        $('pactPaymentResult').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

async function pactCaptureMilestone() {
    if (!confirm(
        'Capture funds for a customer-accepted milestone in PayPal Sandbox?'
    )) return;

    try {
        let d = await api(
            '/pact/agreements/' +
            encodeURIComponent($('pactAgreementId').value) +
            '/milestones/' +
            encodeURIComponent($('pactMilestoneId').value) +
            '/payment/capture',
            {
                method: 'POST',
                body: JSON.stringify({})
            }
        );

        $('pactPaymentResult').textContent =
            JSON.stringify(d, null, 2);
    } catch (e) {
        alert(e.message);
    }
}

// ==========================================
// WORKSPACE BUTTONS
// ==========================================

function toggleView() {
    const off = document.body.classList.toggle('adv-off');
    const button = $('viewToggle');

    if (button) {
        button.textContent = off
            ? 'Show all tools'
            : 'Demo view';

        button.setAttribute('aria-expanded', String(!off));
    }
}

// ==========================================
// INITIALIZATION
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    const viewButton = $('viewToggle');
    const analyzeButton = $('analyzeButton');

    if (viewButton) {
        viewButton.addEventListener('click', toggleView);
    }

    if (analyzeButton) {
        analyzeButton.addEventListener('click', analyze);
    }

    loadPactAgreements();
    loadPactIndicators();
});

// Dashboard startup
load().catch(e => {
    console.error('Dashboard loading failed:', e);

    if ($('mode')) {
        $('mode').textContent =
            'Dashboard error: ' + e.message;
    }
});
// ======================================================
// MERCHANTOS — AG GRID REFUND MANAGEMENT
// SAFE INTEGRATION — PRESERVES ORIGINAL WORKSPACE
// AG GRID COMMUNITY 32.3.3
// ======================================================

(async function MerchantOSRefundGrid() {
    'use strict';

    const VERSION = '32.3.3';

    // 1. Load AG Grid CSS
    [
        `https://cdn.jsdelivr.net/npm/ag-grid-community@${VERSION}/styles/ag-grid.css`,
        `https://cdn.jsdelivr.net/npm/ag-grid-community@${VERSION}/styles/ag-theme-quartz.css`
    ].forEach(href => {
        if (!document.querySelector(`link[href="${href}"]`)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            document.head.appendChild(link);
        }
    });

    // 2. Load AG Grid JavaScript
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

    // 3. Find original refund table
    const refundRows = document.getElementById('refundRows');

    if (!refundRows) {
        console.error('AG Grid: refundRows element not found.');
        return;
    }

    const table = refundRows.closest('table');

    if (!table) {
        console.error('AG Grid: original refund table not found.');
        return;
    }

    // Prevent duplicate initialization
    if (document.getElementById('refundGrid')) return;

    // 4. Create grid wrapper
    const wrapper = document.createElement('section');
    wrapper.id = 'merchantosRefundGridSection';

    const heading = document.createElement('h3');
    heading.textContent = 'Refund management';

    const subtitle = document.createElement('p');
    subtitle.textContent =
        'Review, filter and manage refund proposals.';

    const grid = document.createElement('div');
    grid.id = 'refundGrid';
    grid.className = 'ag-theme-quartz';

    wrapper.append(heading, subtitle, grid);

    table.parentNode.insertBefore(wrapper, table);

    // Keep original table hidden, NOT removed.
    table.hidden = true;

    // 5. Grid styling
    const style = document.createElement('style');

    style.textContent = `
        #merchantosRefundGridSection {
            margin: 20px 0;
            padding: 18px;
            border: 1px solid #dfe5dc;
            border-radius: 16px;
            background: #fff;
        }

        #merchantosRefundGridSection h3 {
            margin: 0 0 6px;
        }

        #merchantosRefundGridSection p {
            margin: 0 0 16px;
            color: #68776e;
        }

        #refundGrid {
            width: 100%;
            height: 430px;
        }

        .ag-theme-quartz {
            --ag-font-family: Arial, sans-serif;
            --ag-font-size: 13px;
            --ag-background-color: #ffffff;
            --ag-foreground-color: #26372f;
            --ag-header-background-color: #edf1e9;
            --ag-header-foreground-color: #26372f;
            --ag-border-color: #dfe5dc;
            --ag-row-hover-color: #eef4ed;
            --ag-header-height: 48px;
            --ag-row-height: 56px;
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

        @media (max-width: 600px) {
            #merchantosRefundGridSection {
                padding: 10px;
                overflow: hidden;
            }

            #refundGrid {
                height: 480px;
            }
        }
    `;

    document.head.appendChild(style);

    // 6. Create AG Grid
    const gridApi = window.agGrid.createGrid(grid, {
        columnDefs: [
            {
                field: 'order_id',
                headerName: 'ORDER',
                minWidth: 130,
                flex: 1
            },
            {
                field: 'reason',
                headerName: 'REASON',
                minWidth: 140,
                flex: 1
            },
            {
                headerName: 'AMOUNT',
                minWidth: 120,
                valueGetter: params => {
                    const row = params.data || {};

                    return new Intl.NumberFormat(
                        row.currency === 'INR' ? 'en-IN' : 'en-US',
                        {
                            style: 'currency',
                            currency: row.currency || 'INR',
                            maximumFractionDigits: 2
                        }
                    ).format(Number(row.amount || 0));
                }
            },
            {
                field: 'status',
                headerName: 'STATUS',
                minWidth: 120,
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
                    const actions = document.createElement('div');
                    actions.className = 'merchantos-grid-actions';

                    const row = params.data || {};

                    if (
                        String(row.status).toUpperCase() === 'PROPOSED'
                    ) {
                        const approveButton =
                            document.createElement('button');

                        approveButton.type = 'button';
                        approveButton.className = 'mini';
                        approveButton.textContent = 'Approve';

                        approveButton.addEventListener('click', async () => {
                            approveButton.disabled = true;

                            try {
                                await approve(row.id);
                                await refreshRefundGrid();
                            } finally {
                                approveButton.disabled = false;
                            }
                        });

                        const rejectButton =
                            document.createElement('button');

                        rejectButton.type = 'button';
                        rejectButton.className = 'mini reject';
                        rejectButton.textContent = 'Reject';

                        rejectButton.addEventListener('click', async () => {
                            rejectButton.disabled = true;

                            try {
                                await reject(row.id);
                                await refreshRefundGrid();
                            } finally {
                                rejectButton.disabled = false;
                            }
                        });

                        actions.append(approveButton, rejectButton);
                    } else {
                        actions.textContent = row.paypal_id || '—';
                    }

                    return actions;
                }
            }
        ],

        defaultColDef: {
            sortable: true,
            filter: true,
            resizable: true
        },

        pagination: true,
        paginationPageSize: 10,
        paginationPageSizeSelector: [10, 20, 50],
        animateRows: true,
        rowData: []
    });

    // 7. Fetch refund data using original API helper
    let refreshing = false;

    async function refreshRefundGrid() {
        if (refreshing) return;

        refreshing = true;

        try {
            // IMPORTANT: api() already adds /api.
            const refunds = await api('/refunds');

            if (!Array.isArray(refunds)) {
                throw new Error('Invalid refunds response.');
            }

            gridApi.setGridOption('rowData', refunds);

        } catch (error) {
            console.error('Refund grid refresh failed:', error);
        } finally {
            refreshing = false;
        }
    }

    // 8. Initial refresh
    await refreshRefundGrid();

    // 9. Keep grid synchronized
    window.merchantOSRefreshRefundGrid = refreshRefundGrid;

    setInterval(refreshRefundGrid, 30000);

    console.log('MerchantOS AG Grid initialized.');

})();
// ======================================================
// MERCHANTOS — WORKFLOW REPAIR
// Inline records, automatic milestone selection,
// safer PACT actions and clean feedback.
// ======================================================

(function MerchantOSWorkflowRepair() {
    'use strict';

    const $ = id => document.getElementById(id);

    function escapeHTML(value) {
        return String(value ?? '').replace(/[&<>"']/g, char => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        })[char]);
    }

    function recordArea(id, title) {
        let el = $(id);

        if (!el) {
            el = document.createElement('section');
            el.id = id;
            el.className = 'mos-record';

            const parent = $('pact-workspace') ||
                $('clusters');

            parent.appendChild(el);
        }

        el.innerHTML = `<h3>${escapeHTML(title)}</h3>`;
        return el;
    }

    function showRecord(id, title, message, details = '') {
        const el = recordArea(id, title);

        el.innerHTML += `
            <div class="mos-record-entry">
                <strong>${escapeHTML(message)}</strong>
                ${details ? `<p>${escapeHTML(details)}</p>` : ''}
                <small>${new Date().toLocaleString()}</small>
            </div>
        `;

        el.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
        });
    }

    // --------------------------------------------------
    // 1. INLINE COMPLAINT INVESTIGATION
    // Replaces the native confirm/alert popup.
    // --------------------------------------------------

    window.inspect = async function inspectCluster(id) {
        try {
            const data = await api(
                '/clusters/' + encodeURIComponent(id)
            );

            const reviews = data.reviews || [];

            const panel = recordArea(
                'mos-cluster-review',
                'Complaint investigation'
            );

            panel.innerHTML += `
                <div class="mos-record-entry">
                    <span class="mos-eyebrow">INVESTIGATION</span>
                    <h3>${escapeHTML(label(id))}</h3>
                    <p>${reviews.length} associated reviews</p>

                    <div class="mos-review-list">
                        ${reviews.slice(0, 5).map(review => `
                            <blockquote>
                                ${escapeHTML(review.text)}
                            </blockquote>
                        `).join('')}
                    </div>

                    <p>
                        Refund proposals will only be created
                        where exact order/customer matching
                        passes server-side eligibility checks.
                    </p>

                    <div class="mos-action-row">
                        <button type="button" id="mosCreateProposal">
                            Create eligible proposals
                        </button>

                        <button type="button"
                            class="ghost"
                            id="mosCancelProposal">
                            Cancel
                        </button>
                    </div>

                    <div id="mosProposalResult"
                         aria-live="polite"></div>
                </div>
            `;

            $('mosCancelProposal').onclick = () => {
                panel.remove();
            };

            $('mosCreateProposal').onclick = async event => {
                const button = event.currentTarget;
                button.disabled = true;
                button.textContent = 'Processing...';

                try {
                    const result = await api('/refunds/propose', {
                        method: 'POST',
                        body: JSON.stringify({
                            cluster_id: id
                        })
                    });

                    $('mosProposalResult').innerHTML = `
                        <div class="mos-success">
                            <strong>
                                ${result.proposals.length}
                                proposal(s) created
                            </strong>
                            <p>${escapeHTML(result.note || '')}</p>
                        </div>
                    `;

                    await load();

                } catch (error) {
                    $('mosProposalResult').innerHTML = `
                        <div class="mos-error">
                            ${escapeHTML(error.message)}
                        </div>
                    `;
                } finally {
                    button.disabled = false;
                    button.textContent = 'Create eligible proposals';
                }
            };

            panel.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });

        } catch (error) {
            showRecord(
                'mos-cluster-review',
                'Investigation error',
                'Could not load complaint investigation',
                error.message
            );
        }
    };

    // --------------------------------------------------
    // 2. PACT AGREEMENT LIST
    // --------------------------------------------------

    window.loadPactAgreements = async function() {
        try {
            const agreements = await api('/pact/agreements');

            const list = $('pactAgreementList');

            if (!list) return;

            list.innerHTML = agreements.length
                ? agreements.map(a => `
                    <article class="mos-agreement">
                        <div>
                            <strong>${escapeHTML(a.title)}</strong>
                            <span class="status">
                                ${escapeHTML(a.status)}
                            </span>
                        </div>

                        <small>
                            ${escapeHTML(a.id)} ·
                            ${escapeHTML(a.currency)}
                            ${escapeHTML(a.total_amount)}
                        </small>

                        <button type="button"
                            class="mini"
                            data-agreement-id="${escapeHTML(a.id)}">
                            Open agreement
                        </button>
                    </article>
                `).join('')
                : '<p>No agreements created yet.</p>';

            list.querySelectorAll('[data-agreement-id]')
                .forEach(button => {
                    button.addEventListener('click', () => {
                        $('pactAgreementId').value =
                            button.dataset.agreementId;

                        window.loadPactAgreement();
                    });
                });

        } catch (error) {
            console.error('PACT agreement list:', error);
        }
    };

    // --------------------------------------------------
    // 3. LOAD AGREEMENT + AUTOMATIC MILESTONE SELECTION
    // --------------------------------------------------

    window.loadPactAgreement = async function() {
        const agreementId = $('pactAgreementId').value.trim();

        if (!agreementId) {
            showRecord(
                'mos-pact-record',
                'Agreement record',
                'Select an agreement first.'
            );
            return;
        }

        try {
            const agreement = await api(
                '/pact/agreements/' +
                encodeURIComponent(agreementId)
            );

            const milestones = agreement.milestones || [];

            const panel = recordArea(
                'mos-pact-record',
                'Agreement record'
            );

            panel.innerHTML += `
                <div class="mos-record-entry">
                    <span class="mos-eyebrow">
                        ${escapeHTML(agreement.status)}
                    </span>

                    <h3>${escapeHTML(agreement.title)}</h3>

                    <p>
                        ${escapeHTML(agreement.freelancer_name)}
                        ↔
                        ${escapeHTML(agreement.customer_name)}
                    </p>

                    <p>
                        ${escapeHTML(agreement.currency)}
                        ${escapeHTML(agreement.total_amount)}
                    </p>

                    <h4>Milestones (${milestones.length})</h4>

                    <div class="mos-milestone-list">
                        ${milestones.map(m => `
                            <button type="button"
                                class="mos-milestone"
                                data-milestone-id="${escapeHTML(m.id)}">

                                <strong>${escapeHTML(m.title)}</strong>

                                <span>
                                    ${escapeHTML(m.status)}
                                </span>

                                <small>
                                    ${escapeHTML(m.id)}
                                    · ${escapeHTML(m.currency)}
                                    ${escapeHTML(m.amount)}
                                </small>
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;

            $('pactAgreementDetail').textContent =
                JSON.stringify(agreement, null, 2);

            panel.querySelectorAll('[data-milestone-id]')
                .forEach(button => {
                    button.addEventListener('click', () => {
                        $('pactMilestoneId').value =
                            button.dataset.milestoneId;

                        button.classList.add('selected');

                        showRecord(
                            'mos-pact-selection',
                            'Selected milestone',
                            button.querySelector('strong').textContent,
                            button.dataset.milestoneId
                        );
                    });
                });

            if (milestones.length === 1) {
                $('pactMilestoneId').value = milestones[0].id;
            }

            showRecord(
                'mos-pact-selection',
                'Agreement loaded',
                agreement.title,
                `${milestones.length} milestones available.`
            );

        } catch (error) {
            showRecord(
                'mos-pact-record',
                'Agreement loading failed',
                'Could not load agreement',
                error.message
            );
        }
    };

    // --------------------------------------------------
    // 4. VALIDATE AGREEMENT + MILESTONE BEFORE ACTIONS
    // --------------------------------------------------

    async function selectedMilestone() {
        const agreementId = $('pactAgreementId').value.trim();
        const milestoneId = $('pactMilestoneId').value.trim();

        if (!agreementId) {
            throw Error('Load an agreement first.');
        }

        if (!milestoneId) {
            throw Error('Select a milestone first.');
        }

        const agreement = await api(
            '/pact/agreements/' +
            encodeURIComponent(agreementId)
        );

        const milestone = (agreement.milestones || [])
            .find(item => item.id === milestoneId);

        if (!milestone) {
            throw Error(
                'Selected milestone does not belong to this agreement.'
            );
        }

        return { agreement, milestone };
    }

    // --------------------------------------------------
    // 5. MILESTONE EVIDENCE
    // --------------------------------------------------

    window.submitPactMilestoneEvidence = async function() {
        try {
            const { agreement, milestone } =
                await selectedMilestone();

            const evidenceIds = $('pactEvidenceIds').value
                .split(',')
                .map(x => x.trim())
                .filter(Boolean);

            if (!evidenceIds.length) {
                throw Error('Enter at least one evidence ID.');
            }

            const result = await api(
                '/pact/agreements/' +
                encodeURIComponent(agreement.id) +
                '/milestones/' +
                encodeURIComponent(milestone.id) +
                '/evidence',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        evidence_ids: evidenceIds,
                        actor: 'freelancer'
                    })
                }
            );

            showRecord(
                'mos-pact-actions',
                'Evidence submission',
                'Evidence submitted for customer review',
                JSON.stringify(result)
            );

            await loadPactAgreement();

        } catch (error) {
            showRecord(
                'mos-pact-actions',
                'Evidence submission',
                'Action unsuccessful',
                error.message
            );
        }
    };

    // --------------------------------------------------
    // 6. CUSTOMER MILESTONE REVIEW
    // --------------------------------------------------

    window.reviewPactMilestone = async function() {
        try {
            const { agreement, milestone } =
                await selectedMilestone();

            const partyName =
                $('pactMilestoneCustomer').value.trim();

            if (!partyName) {
                throw Error('Enter the named customer.');
            }

            if (milestone.status !== 'SUBMITTED') {
                throw Error(
                    'Only submitted milestones can be reviewed.'
                );
            }

            const result = await api(
                '/pact/agreements/' +
                encodeURIComponent(agreement.id) +
                '/milestones/' +
                encodeURIComponent(milestone.id) +
                '/review',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        decision: $('pactMilestoneDecision').value,
                        party_name: partyName
                    })
                }
            );

            $('pactAgreementDetail').textContent =
                JSON.stringify(result, null, 2);

            showRecord(
                'mos-pact-actions',
                'Customer review',
                'Decision recorded',
                `${milestone.title}: ${$('pactMilestoneDecision').value}`
            );

            await loadPactAgreement();

        } catch (error) {
            showRecord(
                'mos-pact-actions',
                'Customer review',
                'Action unsuccessful',
                error.message
            );
        }
    };

    // --------------------------------------------------
    // 7. CREATE PAYPAL AUTHORIZATION ORDER
    // --------------------------------------------------

    window.pactCreateAuthorizationOrder = async function() {
        try {
            const { agreement, milestone } =
                await selectedMilestone();

            if (agreement.status !== 'ACTIVE') {
                throw Error(
                    'Both parties must approve the agreement first.'
                );
            }

            if (Number(milestone.amount) <= 0) {
                throw Error(
                    'This milestone needs an explicit positive amount.'
                );
            }

            const result = await api(
                '/pact/agreements/' +
                encodeURIComponent(agreement.id) +
                '/milestones/' +
                encodeURIComponent(milestone.id) +
                '/payment/authorize-order',
                { method: 'POST' }
            );

            $('pactPaymentResult').textContent =
                JSON.stringify(result, null, 2);

            showRecord(
                'mos-pact-actions',
                'PayPal authorization',
                'Authorization order created',
                result.note || result.paypal_order_id
            );

            if (result.approval_url) {
                const link = document.createElement('a');
                link.href = result.approval_url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = 'Open PayPal buyer approval';

                $('mos-pact-actions').appendChild(link);
            }

            await loadPactAgreement();

        } catch (error) {
            showRecord(
                'mos-pact-actions',
                'PayPal authorization',
                'Action unsuccessful',
                error.message
            );
        }
    };

    // --------------------------------------------------
    // 8. RECORD BUYER AUTHORIZATION
    // --------------------------------------------------

    window.pactAuthorizePayment = async function() {
        try {
            const { agreement, milestone } =
                await selectedMilestone();

            if (
                milestone.status !== 'AUTHORIZATION_ORDER_CREATED'
            ) {
                throw Error(
                    'Create the authorization order and complete buyer approval first.'
                );
            }

            const result = await api(
                '/pact/agreements/' +
                encodeURIComponent(agreement.id) +
                '/milestones/' +
                encodeURIComponent(milestone.id) +
                '/payment/authorize',
                { method: 'POST' }
            );

            $('pactPaymentResult').textContent =
                JSON.stringify(result, null, 2);

            showRecord(
                'mos-pact-actions',
                'Buyer authorization',
                'Authorization result received',
                result.note || result.status
            );

            await loadPactAgreement();

        } catch (error) {
            showRecord(
                'mos-pact-actions',
                'Buyer authorization',
                'Action unsuccessful',
                error.message
            );
        }
    };

    // --------------------------------------------------
    // 9. CAPTURE — ONLY AFTER CUSTOMER ACCEPTANCE
    // --------------------------------------------------

    window.pactCaptureMilestone = async function() {
        try {
            const { agreement, milestone } =
                await selectedMilestone();

            if (milestone.status !== 'ACCEPTED') {
                throw Error(
                    'Customer must accept the milestone before capture.'
                );
            }

            if (!confirm(
                'Capture the accepted milestone amount through PayPal Sandbox?'
            )) return;

            const result = await api(
                '/pact/agreements/' +
                encodeURIComponent(agreement.id) +
                '/milestones/' +
                encodeURIComponent(milestone.id) +
                '/payment/capture',
                {
                    method: 'POST',
                    body: JSON.stringify({})
                }
            );

            $('pactPaymentResult').textContent =
                JSON.stringify(result, null, 2);

            showRecord(
                'mos-pact-actions',
                'Payment capture',
                result.local_status || 'Capture response received',
                result.note || ''
            );

            await loadPactAgreement();

                } catch (error) {
            showRecord(
                'mos-pact-actions',
                'Payment capture',
                'Action unsuccessful',
                error.message
            );
        }
    };

    console.log('MerchantOS workflow repair loaded.');

})();
// ==================================================
// MERCHANTOS — QUICK TOOL NAVIGATION
// ==================================================

(function () {
    const tools = [
        ['Complaints', 'clusters'],
        ['Review Lab', 'reviewlab'],
        ['Investigations', 'investigation'],
        ['Refunds', 'refunds'],
        ['Disputes', 'disputes'],
        ['Evidence', 'evidence-workspace'],
        ['PayPal', 'paypal-disputes'],
        ['PACT', 'pact-workspace'],
        ['Integrity', 'accountability'],
        ['Insights', 'insights'],
        ['Audit', 'audit']
    ];

    function initToolNavigation() {
        const header = document.querySelector('main > header');
        const main = document.querySelector('main');

        if (!header || !main) return;

        const bar = document.createElement('nav');
        bar.id = 'mosQuickTools';
        bar.setAttribute('aria-label', 'Quick tool navigation');

        bar.innerHTML = `
            <span class="mos-tools-label">JUMP TO</span>
            ${tools.map(([name, id]) => `
                <button type="button"
                    data-target="${id}">
                    ${name}
                </button>
            `).join('')}
        `;

        header.insertAdjacentElement('afterend', bar);

        bar.addEventListener('click', event => {
            const button = event.target.closest('[data-target]');
            if (!button) return;

            const target = document.getElementById(
                button.dataset.target
            );

            if (!target) return;

            if (document.body.classList.contains('adv-off')) {
                document.body.classList.remove('adv-off');

                const toggle = document.getElementById('viewToggle');
                if (toggle) toggle.textContent = 'Hide advanced tools';
            }

            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        });

        const toggle = document.getElementById('viewToggle');

        if (toggle) {
            toggle.addEventListener('click', () => {
                setTimeout(() => {
                    const visible =
                        !document.body.classList.contains('adv-off');

                    bar.classList.toggle('visible', visible);

                    if (visible) {
                        bar.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }, 50);
            });
        }

        bar.querySelectorAll('button').forEach(button => {
            button.addEventListener('click', () => {
                bar.querySelectorAll('button').forEach(b =>
                    b.classList.remove('active')
                );

                button.classList.add('active');
            });
        });

        bar.classList.toggle(
            'visible',
            !document.body.classList.contains('adv-off')
        );
    }

    if (document.readyState === 'loading') {
        document.addEventListener(
            'DOMContentLoaded',
            initToolNavigation
        );
    } else {
        initToolNavigation();
    }
})();

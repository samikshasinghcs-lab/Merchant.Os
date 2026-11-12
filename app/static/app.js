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
                                onclick="investigateRefund('${x.id}')">
                                ✦ AI Investigate
                            </button>

                            <button class="mini"
                                onclick="approve('${x.id}')">
                                Human Approve
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
async function investigateRefund(id) {
    const button = event?.currentTarget;

    if (button) {
        button.disabled = true;
        button.textContent = 'Investigating…';
    }

    try {
        const result = await api(
            '/refunds/' + id + '/ai-analysis'
        );

        const facts = result.facts;
        const ai = result.ai;

        alert(
            'MERCHANTOS AI REFUND INVESTIGATION\n\n' +
            'Provider: ' + ai.provider + '\n\n' +
            'Risk: ' + facts.risk_severity + '\n' +
            'Risk score: ' + (facts.risk_score ?? 'Insufficient data') + '\n' +
            'Evidence items: ' + facts.evidence_count + '\n\n' +
            'AI ANALYSIS:\n' + ai.explanation + '\n\n' +
            'HUMAN APPROVAL REQUIRED.'
        );

    } catch (e) {
        alert('AI investigation failed: ' + e.message);

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = '✦ AI Investigate';
        }
    }
}
async function approve(id) {
    const confirmed = confirm(
        'You are authorizing a refund. Continue?'
    );

    if (!confirmed) return;

    const phrase = prompt(
        'Type AUTHORIZE REFUND to confirm:'
    );

    if (phrase !== 'AUTHORIZE REFUND') {
        alert('Authorization cancelled.');
        return;
    }

    try {
        const x = await api('/refunds/' + id + '/approve', {
            method: 'POST',
            body: JSON.stringify({
                human_approved: true,
                confirmation: phrase
            })
        });

        alert('Refund result: ' + x.status);

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
// MERCHANTOS — AG GRID FINANCIAL OPERATIONS WORKSPACE
// AG GRID COMMUNITY 32.3.3 — CDN / SERVER-RENDERED WORKSPACE
// ======================================================

(async function MerchantOSRefundGrid() {
    'use strict';

    const VERSION = '32.3.3';
    const PREF_KEY = 'merchantos.aggrid.refunds.v2';

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

    if (!window.agGrid) {
        await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = `https://cdn.jsdelivr.net/npm/ag-grid-community@${VERSION}/dist/ag-grid-community.min.js`;
            script.onload = resolve;
            script.onerror = () => reject(new Error('AG Grid failed to load'));
            document.head.appendChild(script);
        });
    }

    const refundRows = document.getElementById('refundRows');
    const table = refundRows && refundRows.closest('table');
    if (!refundRows || !table || document.getElementById('refundGrid')) return;

    const wrapper = document.createElement('section');
    wrapper.id = 'merchantosRefundGridSection';
    wrapper.innerHTML = `
        <div class="mos-grid-heading">
            <div>
                <span class="mos-grid-eyebrow">AG GRID COMMUNITY · FINANCIAL OPERATIONS</span>
                <h3>Refund operations grid</h3>
                <p>Investigate, filter and export refund records. Provider state remains authoritative; actions require human approval.</p>
            </div>
            <span id="mosGridRefreshState" aria-live="polite">Connecting…</span>
        </div>
        <div class="mos-grid-metrics" id="mosGridMetrics">
            <div><small>ALL RECORDS</small><b id="mosGridTotal">—</b></div>
            <div><small>AWAITING REVIEW</small><b id="mosGridPending">—</b></div>
            <div><small>APPROVED / SETTLED</small><b id="mosGridResolved">—</b></div>
            <div><small>SELECTED ROWS</small><b id="mosGridSelected">0</b></div>
        </div>
        <div class="mos-grid-toolbar">
            <label class="mos-grid-search">Search all columns
                <input id="mosGridSearch" type="search" placeholder="Order, reason, status, amount…">
            </label>
            <button type="button" data-mos-status="ALL">All</button>
            <button type="button" data-mos-status="PROPOSED">Proposed</button>
            <button type="button" data-mos-status="APPROVED">Approved</button>
            <button type="button" data-mos-status="REJECTED">Rejected</button>
            <button type="button" id="mosGridClear">Clear filters</button>
            <button type="button" id="mosGridExport">Export filtered CSV</button>
            <button type="button" id="mosGridExportSelected" disabled>Export selected</button>
            <button type="button" id="mosGridSave">Save view</button>
            <button type="button" id="mosGridReset">Reset view</button>
            <button type="button" id="mosGridRefresh">Refresh</button>
        </div>
        <div id="refundGrid" class="ag-theme-quartz" aria-label="Refund operations data grid"></div>
        <div id="mosGridFeedback" role="status" aria-live="polite"></div>
    `;

    table.parentNode.insertBefore(wrapper, table);
    table.hidden = true;

    const style = document.createElement('style');
    style.textContent = `
        #merchantosRefundGridSection{margin:20px 0;padding:18px;border:1px solid #dfe5dc;border-radius:16px;background:#fff;box-shadow:0 8px 24px rgba(30,50,35,.05)}
        #merchantosRefundGridSection .mos-grid-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}
        #merchantosRefundGridSection h3{margin:5px 0}
        #merchantosRefundGridSection p{margin:0 0 14px;color:#68776e;font-size:13px}
        #merchantosRefundGridSection .mos-grid-eyebrow{font-size:10px;font-weight:800;letter-spacing:1.2px;color:#26734b}
        #merchantosRefundGridSection .mos-grid-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:14px 0}
        #merchantosRefundGridSection .mos-grid-metrics>div{padding:12px;border:1px solid #e3e9e1;border-radius:10px;background:#f8faf7}
        #merchantosRefundGridSection .mos-grid-metrics small{display:block;color:#68776e;font-size:9px;font-weight:800;letter-spacing:.6px}
        #merchantosRefundGridSection .mos-grid-metrics b{display:block;margin-top:5px;font-size:21px;color:#203b2b}
        #merchantosRefundGridSection .mos-grid-toolbar{display:flex;align-items:end;gap:7px;flex-wrap:wrap;margin:14px 0}
        #merchantosRefundGridSection .mos-grid-toolbar button{padding:8px 10px;border:1px solid #dfe5dc;border-radius:8px;background:#f7f9f6;color:#31483a;font-size:11px;font-weight:700;cursor:pointer}
        #merchantosRefundGridSection .mos-grid-toolbar button:hover:not(:disabled){border-color:#26734b;background:#edf5ed}
        #merchantosRefundGridSection .mos-grid-toolbar button:disabled{opacity:.45;cursor:not-allowed}
        #merchantosRefundGridSection .mos-grid-search{display:grid;gap:4px;min-width:190px;flex:1;color:#68776e;font-size:10px;font-weight:700}
        #merchantosRefundGridSection .mos-grid-search input{min-height:34px;padding:7px 10px;border:1px solid #dfe5dc;border-radius:8px}
        #merchantosRefundGridSection #refundGrid{width:100%;height:490px}
        #merchantosRefundGridSection #mosGridFeedback{min-height:18px;margin-top:8px;color:#68776e;font-size:11px}
        #merchantosRefundGridSection .ag-theme-quartz{--ag-font-family:Arial,sans-serif;--ag-font-size:12px;--ag-background-color:#fff;--ag-foreground-color:#26372f;--ag-header-background-color:#edf1e9;--ag-header-foreground-color:#26372f;--ag-border-color:#dfe5dc;--ag-row-hover-color:#eef4ed;--ag-header-height:44px;--ag-row-height:52px}
        #merchantosRefundGridSection .merchantos-grid-actions{display:flex;align-items:center;gap:5px;height:100%}
        #merchantosRefundGridSection .merchantos-grid-actions button{cursor:pointer}
        @media(max-width:700px){#merchantosRefundGridSection{padding:10px}#merchantosRefundGridSection .mos-grid-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}#merchantosRefundGridSection #refundGrid{height:520px}#merchantosRefundGridSection .mos-grid-heading{display:block}}
    `;
    document.head.appendChild(style);

    let refunds = [];
    let refreshing = false;
    let saveTimer = null;

    function savePreferences() {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
            try {
                localStorage.setItem(PREF_KEY, JSON.stringify({
                    columns: gridApi.getColumnState(),
                    filters: gridApi.getFilterModel(),
                    quickSearch: document.getElementById('mosGridSearch').value
                }));
                feedback('View preferences saved on this device.');
            } catch (_) {
                feedback('Browser storage unavailable; current grid view remains active.');
            }
        }, 250);
    }

    function feedback(message) {
        const el = document.getElementById('mosGridFeedback');
        if (el) el.textContent = message;
    }

    function updateMetrics(rows) {
        const count = status => rows.filter(row => String(row.status || '').toUpperCase() === status).length;
        document.getElementById('mosGridTotal').textContent = rows.length;
        document.getElementById('mosGridPending').textContent = count('PROPOSED');
        document.getElementById('mosGridResolved').textContent =
            rows.filter(row => ['APPROVED', 'COMPLETED', 'REFUNDED'].includes(String(row.status || '').toUpperCase())).length;
    }

    const currencyFormatter = params => {
        const row = params.data || {};
        try {
            return new Intl.NumberFormat(row.currency === 'INR' ? 'en-IN' : 'en-US', {
                style: 'currency', currency: row.currency || 'INR', maximumFractionDigits: 2
            }).format(Number(params.value || 0));
        } catch (_) { return String(params.value ?? '—'); }
    };

    const gridOptions = {
        columnDefs: [
            { field: 'order_id', headerName: 'ORDER', pinned: 'left', minWidth: 140 },
            { field: 'reason', headerName: 'REASON', minWidth: 160, flex: 1 },
            { field: 'amount', headerName: 'AMOUNT', type: 'rightAligned', minWidth: 125, valueFormatter: currencyFormatter, filter: 'agNumberColumnFilter' },
            { field: 'currency', headerName: 'CURRENCY', width: 100 },
            { field: 'status', headerName: 'STATUS', minWidth: 125, cellRenderer: params => {
                const badge = document.createElement('span');
                badge.textContent = params.value || 'UNKNOWN';
                badge.className = 'status s-' + String(params.value || '').toLowerCase().replace(/[^a-z0-9_-]/g, '');
                return badge;
            }},
            { field: 'risk_severity', headerName: 'RISK', minWidth: 115, cellRenderer: params => {
                const badge = document.createElement('span');
                badge.textContent = params.value || 'UNASSESSED';
                badge.className = 'status s-' + String(params.value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]/g, '');
                return badge;
            }},
            { field: 'risk_score', headerName: 'RISK SCORE', minWidth: 110, filter: 'agNumberColumnFilter', valueFormatter: p => p.value == null ? '—' : Number(p.value).toFixed(2) },
            { field: 'risk_baseline_orders', headerName: 'BASELINE N', minWidth: 115, filter: 'agNumberColumnFilter' },
            { field: 'paypal_status', headerName: 'PAYPAL STATUS', minWidth: 135 },
            { field: 'created_at', headerName: 'CREATED', minWidth: 165 },
            { field: 'risk_signals', headerName: 'RISK SIGNALS', minWidth: 220, valueFormatter: p => Array.isArray(p.value) ? p.value.join(' · ') : '' },
            { field: 'id', headerName: 'PROPOSAL ID', minWidth: 170 },
            { headerName: 'ACTIONS', pinned: 'right', minWidth: 205, sortable: false, filter: false, cellRenderer: params => {
                const actions = document.createElement('div');
                actions.className = 'merchantos-grid-actions';
                const row = params.data || {};
                const addButton = (text, className, handler) => {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = className;
                    button.textContent = text;
                    button.addEventListener('click', async event => {
                        event.stopPropagation();
                        button.disabled = true;
                        try { await handler(); }
                        catch (error) { feedback(error.message || 'Action failed.'); }
                        finally { button.disabled = false; }
                    });
                    actions.appendChild(button);
                };
                if (String(row.status || '').toUpperCase() === 'PROPOSED') {
                    addButton('Investigate', 'mini', async () => { await investigateRefund(row.id); });
                    addButton('Approve', 'mini', async () => { await approve(row.id); await refreshRefundGrid(); });
                    addButton('Reject', 'mini reject', async () => { await reject(row.id); await refreshRefundGrid(); });
                } else {
                    actions.textContent = row.paypal_id || row.paypal_status || '—';
                }
                return actions;
            }}
        ],
        defaultColDef: { sortable: true, filter: true, floatingFilter: true, resizable: true, minWidth: 100 },
        rowSelection: 'multiple',
        suppressRowClickSelection: true,
        pagination: true,
        paginationPageSize: 10,
        paginationPageSizeSelector: [10, 25, 50, 100],
        animateRows: true,
        getRowId: params => String(params.data.id),
        onSelectionChanged: event => {
            const count = event.api.getSelectedRows().length;
            document.getElementById('mosGridSelected').textContent = count;
            document.getElementById('mosGridExportSelected').disabled = count === 0;
        },
        onFilterChanged: savePreferences,
        onSortChanged: savePreferences,
        onColumnMoved: savePreferences,
        onColumnVisible: savePreferences,
        onColumnResized: event => { if (event.finished) savePreferences(); },
        onRowClicked: event => {
            if (event.data && typeof window.investigateRefund === 'function') {
                window.investigateRefund(event.data.id);
            }
        },
        rowData: []
    };

    const grid = document.getElementById('refundGrid');
    const gridApi = window.agGrid.createGrid(grid, gridOptions);

    function applyStatus(status) {
        const filters = status === 'ALL' ? null : {
            status: { filterType: 'text', type: 'equals', filter: status }
        };
        gridApi.setFilterModel(filters);
    }

    document.getElementById('mosGridSearch').addEventListener('input', event => {
        gridApi.setGridOption('quickFilterText', event.target.value);
        savePreferences();
    });
    document.querySelectorAll('[data-mos-status]').forEach(button => {
        button.addEventListener('click', () => applyStatus(button.dataset.mosStatus));
    });
    document.getElementById('mosGridClear').addEventListener('click', () => {
        gridApi.setFilterModel(null);
        document.getElementById('mosGridSearch').value = '';
        gridApi.setGridOption('quickFilterText', '');
        feedback('All grid filters cleared.');
    });
    document.getElementById('mosGridExport').addEventListener('click', () => {
        gridApi.exportDataAsCsv({ fileName: 'merchantos-refund-operations.csv' });
    });
    document.getElementById('mosGridExportSelected').addEventListener('click', () => {
        gridApi.exportDataAsCsv({ onlySelected: true, fileName: 'merchantos-selected-refunds.csv' });
    });
    document.getElementById('mosGridSave').addEventListener('click', savePreferences);
    document.getElementById('mosGridReset').addEventListener('click', () => {
        gridApi.resetColumnState();
        gridApi.setFilterModel(null);
        gridApi.deselectAll();
        document.getElementById('mosGridSearch').value = '';
        gridApi.setGridOption('quickFilterText', '');
        try { localStorage.removeItem(PREF_KEY); } catch (_) {}
        feedback('Grid layout reset.');
    });
    document.getElementById('mosGridRefresh').addEventListener('click', refreshRefundGrid);

    function refreshRefundGrid() {
        if (refreshing) return;
        refreshing = true;
        document.getElementById('mosGridRefreshState').textContent = 'Refreshing…';
        return api('/refunds').then(data => {
            if (!Array.isArray(data)) throw new Error('Invalid refunds response.');
            refunds = data;
            gridApi.setGridOption('rowData', refunds);
            updateMetrics(refunds);
            document.getElementById('mosGridRefreshState').textContent =
                'Updated ' + new Date().toLocaleTimeString();
        }).catch(error => {
            document.getElementById('mosGridRefreshState').textContent = 'Refresh failed';
            feedback(error.message || 'Could not refresh refund data.');
            console.error('Refund grid refresh failed:', error);
        }).finally(() => { refreshing = false; });
    }

    try {
        const saved = JSON.parse(localStorage.getItem(PREF_KEY) || 'null');
        if (saved) {
            if (Array.isArray(saved.columns)) gridApi.applyColumnState({ state: saved.columns, applyOrder: true });
            if (saved.filters) gridApi.setFilterModel(saved.filters);
            if (typeof saved.quickSearch === 'string') {
                document.getElementById('mosGridSearch').value = saved.quickSearch;
                gridApi.setGridOption('quickFilterText', saved.quickSearch);
            }
        }
    } catch (_) { /* ignore invalid stored preferences */ }

    await refreshRefundGrid();
    window.merchantOSRefreshRefundGrid = refreshRefundGrid;
    setInterval(refreshRefundGrid, 30000);
    console.log('MerchantOS AG Grid financial operations workspace initialized.');
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
// ==========================================
// DEEPTECH — MERCHANTOS WORKSPACE
// ==========================================
(() => {
    const button = document.getElementById('refreshDeepTech');
    const status = document.getElementById('deeptechStatus');
    const results = document.getElementById('deeptechResults');

    if (!button || !status || !results) return;

    const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({
        '&':'&amp;', '<':'&lt;', '>':'&gt;',
        '"':'&quot;', "'":'&#39;'
    }[c]));

    const row = (name, value) =>
        `<div class="row"><span>${esc(name)}</span><b>${esc(value)}</b></div>`;

    async function refresh() {
        button.disabled = true;
        button.textContent = 'Analysing...';
        status.textContent = 'Analysing MerchantOS records...';

        try {
            const response = await fetch('/api/deeptech/lab', {
                cache: 'no-store'
            });

            const d = await response.json();

            if (!response.ok) {
                throw new Error(d.detail || 'Analysis failed');
            }

            const a = d.anomaly || {};
            const g = d.graph;
            const s = d.simulation;
            const c = d.audit_chain;

            let html = '<div class="cols">';

            html += `<section class="card">
                <h3>1. Anomaly Detection</h3>
                ${row('Orders analysed', d.orders)}
                ${row('Method', a.method || 'Robust statistics')}
                ${(a.top || []).map(x => `
                    <div class="row">
                        <b>${esc(x.order_id)}</b>
                        ${row('Score', x.score)}
                        ${row('Severity', x.severity)}
                        <small>${esc((x.signals || []).join(', '))}</small>
                    </div>
                `).join('') || '<p>No anomaly findings.</p>'}
            </section>`;

            html += `<section class="card">
                <h3>2. Transaction Graph</h3>
                ${g ? row('Nodes', g.nodes) +
                    row('Edges', g.edges) +
                    row('Connected groups', g.components)
                    : '<p>Unavailable</p>'}
            </section>`;

            html += `<section class="card">
                <h3>3. Monte Carlo Simulation</h3>
                ${s ? row('Scenario', s.scenario) +
                    row('5th–95th percentile', s.p05 + ' – ' + s.p95) +
                    row('Median', s.median) +
                    row('Chance of loss', (s.probability_of_loss * 100).toFixed(1) + '%') +
                    row('Refund rate assumption', (s.refund_rate * 100).toFixed(1) + '%') +
                    `<p>${esc(s.assumptions)}</p>`
                    : '<p>Unavailable</p>'}
            </section>`;

            html += `<section class="card">
                <h3>4. Audit Integrity</h3>
                ${c ? row('Events', c.events) +
                    row('Chain valid', c.valid ? 'YES' : 'NO') +
                    row('Tamper detected', c.tamper_test.detected ? 'YES' : 'NO')
                    : '<p>Unavailable</p>'}
            </section>`;

            html += '</div>';

            results.innerHTML = html;
            status.textContent = 'Analysis refreshed successfully.';
        } catch (e) {
            status.textContent = 'Error: ' + e.message;
        } finally {
            button.disabled = false;
            button.textContent = 'Refresh Analysis';
        }
    }

    button.addEventListener('click', refresh);
    refresh();
})();

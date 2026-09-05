// Financial Clarity — wires the manual-entry form to the real "Offer Decoder"
// backend (backend/app/main.py). No arithmetic happens here: every number
// shown comes straight from POST /breakdown, and every rule explanation
// comes straight from GET /rule/{rule_id}. This file only shapes the
// request, renders the response, and manages the audit-trail disclosure.

const form = document.getElementById("offer-form");
const formNote = document.getElementById("form-note");
const emptyState = document.getElementById("empty-state");
const result = document.getElementById("result");
const inHandAmountEl = document.getElementById("in-hand-amount");
const updatingBadge = document.getElementById("updating-badge");
const ledgerTableBody = document.querySelector("#ledger-table tbody");
const flagsBlock = document.getElementById("flags");
const flagsList = document.getElementById("flags-list");
const scopeNote = document.getElementById("scope-note");
const scopeCoveredEl = document.getElementById("scope-covered");
const scopeNotCoveredEl = document.getElementById("scope-not-covered");
const apiBaseInput = document.getElementById("api-base");
const apiStatusEl = document.getElementById("api-status");
const oldOnlyRows = document.querySelectorAll(".old-only");

let hasResult = false;              // a breakdown has been shown at least once
let displayedInHand = 0;            // for the count-up animation baseline
let previousRowAmounts = new Map(); // key -> last-rendered amount, for change marks
let debounceTimer = null;
let countUpFrame = null;

// --- scroll-triggered reveal for .reveal elements (flags, scope note) ---

const revealObserver = "IntersectionObserver" in window
  ? new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 })
  : null;

function revealWhenVisible(el) {
  if (!el) return;
  if (!revealObserver) {
    el.classList.add("is-visible");
    return;
  }
  el.classList.remove("is-visible");
  revealObserver.observe(el);
}

function apiBase() {
  return apiBaseInput.value.replace(/\/+$/, "");
}

function formatInr(amount) {
  const rounded = Math.round(Number(amount) || 0);
  return "₹" + rounded.toLocaleString("en-IN");
}

function requiredFieldsPresent() {
  return Boolean(form.basic.value) && Boolean(form.hra.value);
}

// --- inline required-field feedback, live as the person types -----------

[form.basic, form.hra].forEach((input) => {
  input.addEventListener("blur", () => {
    input.classList.toggle("field-missing", input.value === "");
  });
  input.addEventListener("input", () => input.classList.remove("field-missing"));
});

// --- city -> metro/non-metro classification ------------------------------
// The HRA rule only cares about metro vs. non-metro, but making someone
// pick that label themselves means they have to already know the rule.
// Instead they type their actual city and we classify it, same "show your
// work" principle as the rule-lookup chips: the classification is always
// visible, never a silent guess baked into a hidden field.

const METRO_CITIES = new Set([
  "mumbai", "bombay",
  "delhi", "new delhi", "delhi ncr",
  "kolkata", "calcutta",
  "chennai", "madras",
]);

function classifyCity(cityName) {
  return METRO_CITIES.has((cityName || "").trim().toLowerCase());
}

const cityNameInput = document.getElementById("city_name");
const cityClassificationEl = document.getElementById("city-classification");

function updateCityHint() {
  const value = cityNameInput.value.trim();
  if (!value) {
    cityClassificationEl.textContent = "";
    cityClassificationEl.classList.remove("is-metro");
    return;
  }
  const isMetro = classifyCity(value);
  cityClassificationEl.textContent = isMetro
    ? "→ Metro city: the 50% HRA exemption limb applies."
    : "→ Non-metro: the 40% HRA exemption limb applies.";
  cityClassificationEl.classList.toggle("is-metro", isMetro);
}

cityNameInput.addEventListener("input", updateCityHint);

// --- regime toggle: shows/hides old-regime fields, recomputes live ------

form.querySelectorAll('input[name="regime"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const isOld = form.querySelector('input[name="regime"]:checked').value === "old";
    oldOnlyRows.forEach((row) => { row.hidden = !isOld; });
    if (hasResult) runBreakdown({ silent: true });
  });
});

// --- any other field: debounced live recompute once a result exists -----

form.querySelectorAll("input, select").forEach((el) => {
  if (el.name === "regime") return; // handled above, immediately
  el.addEventListener("input", () => {
    if (!hasResult || !requiredFieldsPresent()) return;
    clearTimeout(debounceTimer);
    updatingBadge.hidden = false;
    debounceTimer = setTimeout(() => runBreakdown({ silent: true }), 450);
  });
});

// --- build the CTCBreakup payload the backend expects ------------------

function buildPayload() {
  const data = new FormData(form);
  const num = (key) => {
    const v = data.get(key);
    return v === null || v === "" ? undefined : Number(v);
  };
  const regime = data.get("regime") || "new";

  const ctc_breakup = {
    basic: num("basic"),
    hra: num("hra"),
    special_allowance: num("special_allowance") ?? 0,
    bonus: num("bonus") ?? 0,
    employer_pf: num("employer_pf"),
    is_metro: classifyCity(data.get("city_name")),
    notice_period_days: num("notice_period_days"),
    gratuity_clause_present: data.get("gratuity_clause_present") === "on",
    has_service_bond: data.get("has_service_bond") === "on",
    joining_bonus_has_clawback: data.get("joining_bonus_has_clawback") === "on",
  };

  if (regime === "old") {
    ctc_breakup.rent_paid = num("rent_paid") ?? 0;
    ctc_breakup.deductions_claimed = {
      "80C": num("ded_80c") ?? 0,
      "80D": num("ded_80d") ?? 0,
    };
  }

  return { ctc_breakup, regime };
}

// --- rendering -----------------------------------------------------------

function renderBreakdown(payload) {
  const b = payload.breakdown;
  animateInHand(b.in_hand_monthly);

  const rows = [
    { key: "gross", label: "Gross salary, per year", amount: b.gross_salary_annual, ruleId: null },
  ];
  b.deductions.forEach((d) => {
    rows.push({ key: `ded:${d.rule_id}:${d.name}`, label: d.name, amount: -d.amount, ruleId: d.rule_id, negative: true });
  });
  if (b.hra_exemption_amount) {
    rows.push({ key: "hra_exemption", label: "HRA exemption (old regime)", amount: b.hra_exemption_amount, ruleId: "HRA_METRO_PCT" });
  }
  rows.push({ key: "std_deduction", label: `Standard deduction (${b.std_deduction_rule_id})`, amount: b.std_deduction_amount, ruleId: b.std_deduction_rule_id });
  rows.push({ key: "in_hand_annual", label: "In hand, per year", amount: b.in_hand_annual, ruleId: null, emphasis: true });

  const nextAmounts = new Map();
  ledgerTableBody.innerHTML = "";
  rows.forEach((row) => {
    nextAmounts.set(row.key, row.amount);
    appendLedgerRow(row, previousRowAmounts.get(row.key));
  });
  previousRowAmounts = nextAmounts;

  renderFlags(payload.red_flags || []);

  latestBreakdown = b;
  updateBudget();

  const firstResult = !hasResult;
  emptyState.hidden = true;
  result.hidden = false;
  hasResult = true;

  if (firstResult && window.innerWidth <= 704) {
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function animateInHand(target) {
  if (prefersReducedMotion) {
    inHandAmountEl.textContent = formatInr(target);
    displayedInHand = target;
    return;
  }
  cancelAnimationFrame(countUpFrame);
  const start = displayedInHand;
  const delta = target - start;
  const duration = 500;
  const startTime = performance.now();

  function step(now) {
    const t = Math.min(1, (now - startTime) / duration);
    const eased = 1 - Math.pow(1 - t, 3); // ease-out
    inHandAmountEl.textContent = formatInr(start + delta * eased);
    if (t < 1) {
      countUpFrame = requestAnimationFrame(step);
    } else {
      displayedInHand = target;
    }
  }
  countUpFrame = requestAnimationFrame(step);
}

function appendLedgerRow({ label, amount, ruleId, negative, emphasis }, previousAmount) {
  const tr = document.createElement("tr");
  tr.className = "entry-row";
  if (emphasis) tr.classList.add("entry-row--emphasis");

  const changed = previousAmount !== undefined && Math.round(previousAmount) !== Math.round(amount);
  if (changed) tr.classList.add("row-changed");

  const labelTd = document.createElement("td");
  labelTd.className = "entry-label";
  labelTd.textContent = label;

  if (ruleId) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "rule-chip";
    chip.textContent = "▸ why?";
    chip.setAttribute("aria-expanded", "false");
    chip.addEventListener("click", () => toggleRuleDetail(tr, ruleId, chip));
    labelTd.appendChild(chip);
  }

  const amountTd = document.createElement("td");
  amountTd.className = "entry-amount" + (negative ? " negative" : "");
  amountTd.textContent = (negative ? "−" : "") + formatInr(Math.abs(amount));

  if (changed) {
    const delta = amount - previousAmount;
    const badge = document.createElement("span");
    badge.className = "delta-badge";
    badge.textContent = (delta > 0 ? "▲ " : "▼ ") + formatInr(Math.abs(delta));
    amountTd.appendChild(badge);
  }

  tr.appendChild(labelTd);
  tr.appendChild(amountTd);
  ledgerTableBody.appendChild(tr);

  if (changed) {
    tr.addEventListener("animationend", () => tr.classList.remove("row-changed"), { once: true });
  }
}

async function toggleRuleDetail(row, ruleId, chip) {
  const next = row.nextElementSibling;
  if (next && next.classList.contains("rule-detail")) {
    next.remove();
    chip.textContent = "▸ why?";
    chip.setAttribute("aria-expanded", "false");
    return;
  }
  ledgerTableBody.querySelectorAll(".rule-detail").forEach((el) => el.remove());
  ledgerTableBody.querySelectorAll('.rule-chip[aria-expanded="true"]').forEach((el) => {
    el.textContent = "▸ why?";
    el.setAttribute("aria-expanded", "false");
  });

  chip.textContent = "▾ why?";
  chip.setAttribute("aria-expanded", "true");

  const detailRow = document.createElement("tr");
  detailRow.className = "rule-detail";
  const td = document.createElement("td");
  td.colSpan = 2;
  td.textContent = "Looking up the rule…";
  detailRow.appendChild(td);
  row.after(detailRow);

  try {
    const res = await fetch(`${apiBase()}/rule/${encodeURIComponent(ruleId)}`);
    if (!res.ok) throw new Error(`Rule lookup failed (${res.status})`);
    const rule = await res.json();
    td.textContent = rule.description || JSON.stringify(rule.value);
    const source = document.createElement("span");
    source.className = "rule-source";
    source.textContent = rule.source ? `Source: ${rule.source}` : `Rule ID: ${ruleId}`;
    td.appendChild(source);
  } catch (err) {
    td.textContent = `Couldn't look up ${ruleId} — ${err.message}`;
  }
}

function renderFlags(flags) {
  flagsList.innerHTML = "";
  if (!flags.length) {
    flagsBlock.hidden = true;
    return;
  }
  flags.forEach((flag) => {
    const li = document.createElement("li");
    li.className = `severity-${flag.severity}`;
    li.textContent = flag.message;
    flagsList.appendChild(li);
  });
  flagsBlock.hidden = false;
  revealWhenVisible(flagsBlock);
}

// --- shared fetch path for both explicit submit and live recompute ------

async function runBreakdown({ silent }) {
  if (!silent) formNote.textContent = "";

  const submitButton = form.querySelector(".cta");
  if (!silent) {
    submitButton.disabled = true;
    submitButton.textContent = "Working it out…";
  }

  try {
    const { ctc_breakup, regime } = buildPayload();
    const res = await fetch(`${apiBase()}/breakdown`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ctc_breakup, regime }),
    });

    if (res.status === 422) {
      const detail = await res.json();
      const missing = (detail.missing_fields || []).join(", ");
      if (!silent) {
        formNote.textContent = missing
          ? `Missing: ${missing}. Fill these in and try again.`
          : "Some fields don't look right — check the highlighted values.";
      }
      return;
    }
    if (!res.ok) throw new Error(`Backend returned ${res.status}`);

    const payload = await res.json();
    renderBreakdown(payload);
    setApiStatus(true);
  } catch (err) {
    if (!silent) {
      formNote.textContent = `Couldn't reach the backend at ${apiBase()} — ${err.message}. ` +
        `Make sure it's running (uvicorn app.main:app --reload).`;
    }
    setApiStatus(false);
  } finally {
    if (!silent) {
      submitButton.disabled = false;
      submitButton.textContent = "See my breakdown";
    }
    updatingBadge.hidden = true;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!requiredFieldsPresent()) {
    form.basic.classList.toggle("field-missing", !form.basic.value);
    form.hra.classList.toggle("field-missing", !form.hra.value);
    formNote.textContent = "Basic and HRA are required — the calculation can't start without them.";
    return;
  }
  runBreakdown({ silent: false });
});

function setApiStatus(ok) {
  apiStatusEl.textContent = ok ? "reachable" : "unreachable";
  apiStatusEl.className = "api-status " + (ok ? "ok" : "error");
}

// --- scope note, loaded once on page load --------------------------------

async function loadScope() {
  try {
    const res = await fetch(`${apiBase()}/completeness-scope`);
    if (!res.ok) throw new Error();
    const scope = await res.json();
    scopeCoveredEl.innerHTML = scope.covered.map((item) => `<li>${item}</li>`).join("");
    scopeNotCoveredEl.innerHTML = scope.not_covered.map((item) => `<li>${item}</li>`).join("");
    scopeNote.hidden = false;
    revealWhenVisible(scopeNote);
    setApiStatus(true);
  } catch {
    setApiStatus(false);
  }
}

loadScope();

// --- sample offers: pre-built payloads for demo reliability -------------
// Field keys match the offer-form's input names/ids directly, so loading a
// sample is just "set these form fields, then submit" — no separate parsing.

const SAMPLE_OFFERS = {
  clean: {
    regime: "new",
    fields: {
      basic: 400000, hra: 200000, special_allowance: 150000, bonus: 40000,
      employer_pf: 48000, city_name: "Mumbai", notice_period_days: 60,
      gratuity_clause_present: true, has_service_bond: false, joining_bonus_has_clawback: false,
    },
  },
  redflags: {
    regime: "new",
    fields: {
      basic: 200000, hra: 100000, special_allowance: 200000, bonus: 500000,
      employer_pf: "", city_name: "Mumbai", notice_period_days: 120,
      gratuity_clause_present: false, has_service_bond: true, joining_bonus_has_clawback: true,
    },
  },
  senior: {
    regime: "old",
    fields: {
      basic: 900000, hra: 450000, special_allowance: 300000, bonus: 150000,
      employer_pf: 108000, city_name: "Mumbai", rent_paid: 360000, ded_80c: 150000, ded_80d: 25000,
      notice_period_days: 90, gratuity_clause_present: true, has_service_bond: false,
      joining_bonus_has_clawback: false,
    },
  },
};

function loadSample(key) {
  const sample = SAMPLE_OFFERS[key];
  if (!sample) return;

  form.reset(); // clear any stale values (e.g. rent_paid) left from a previously loaded sample
  form.querySelector(`input[name="regime"][value="${sample.regime}"]`).checked = true;
  const isOld = sample.regime === "old";
  oldOnlyRows.forEach((row) => { row.hidden = !isOld; });

  Object.entries(sample.fields).forEach(([name, value]) => {
    const el = form.elements.namedItem(name);
    if (!el) return;
    if (el.type === "checkbox") el.checked = Boolean(value);
    else el.value = value;
  });
  updateCityHint();

  form.basic.classList.remove("field-missing");
  form.hra.classList.remove("field-missing");
  runBreakdown({ silent: false });
}

document.querySelectorAll(".sample-chip").forEach((btn) => {
  btn.addEventListener("click", () => loadSample(btn.dataset.sample));
});

// --- budgeting: salary -> deductions -> essentials -> spendable ----------
// Essentials are plain user-entered recurring costs, not tax/PF rule
// outputs, so subtracting them client-side doesn't break the "backend owns
// every rupee" rule — there's no rule_id to trace here, just arithmetic on
// numbers the user typed in.

const budgetBlock = document.getElementById("budget");
const budgetInputs = document.querySelectorAll("#budget-inputs input");
const budgetWarning = document.getElementById("budget-warning");
const flowSalaryEl = document.getElementById("flow-salary");
const flowInHandEl = document.getElementById("flow-in-hand");
const flowSpendableEl = document.getElementById("flow-spendable");
const flowSpendableStep = document.getElementById("flow-spendable-step");
const flowDeductionsNote = document.getElementById("flow-deductions-note");
const flowEssentialsNote = document.getElementById("flow-essentials-note");

let latestBreakdown = null;

function essentialsTotal() {
  let total = 0;
  budgetInputs.forEach((input) => { total += Number(input.value) || 0; });
  return total;
}

function updateBudget() {
  if (!latestBreakdown) {
    budgetBlock.hidden = true;
    return;
  }
  const b = latestBreakdown;
  const salaryMonthly = b.gross_salary_annual / 12;
  const deductionsMonthly = salaryMonthly - b.in_hand_monthly;
  const essentials = essentialsTotal();
  const spendable = b.in_hand_monthly - essentials;

  flowSalaryEl.textContent = formatInr(salaryMonthly);
  flowDeductionsNote.textContent = `− deductions ${formatInr(deductionsMonthly)}`;
  flowInHandEl.textContent = formatInr(b.in_hand_monthly);
  flowEssentialsNote.textContent = `− essentials ${formatInr(essentials)}`;
  flowSpendableEl.textContent = formatInr(spendable);

  const overspending = spendable < 0;
  flowSpendableStep.classList.toggle("flow-step--negative", overspending);
  budgetWarning.hidden = !overspending;
  if (overspending) {
    budgetWarning.textContent = `These recurring costs exceed your in-hand pay by ${formatInr(Math.abs(spendable))}/month.`;
  }

  budgetBlock.hidden = false;
  revealWhenVisible(budgetBlock);
}

budgetInputs.forEach((input) => {
  input.addEventListener("input", updateBudget);
});

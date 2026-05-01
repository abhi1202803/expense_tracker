const PENDING_SUBMISSION_KEY = "expense-tracker.pending-submission";
const DEFAULT_CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Health", "Entertainment", "Education"];

const elements = {
  expenseForm: document.getElementById("expenseForm"),
  amount: document.getElementById("amount"),
  category: document.getElementById("category"),
  customCategoryField: document.getElementById("customCategoryField"),
  customCategory: document.getElementById("customCategory"),
  date: document.getElementById("date"),
  description: document.getElementById("description"),
  submitButton: document.getElementById("submitButton"),
  retryPendingButton: document.getElementById("retryPendingButton"),
  discardPendingButton: document.getElementById("discardPendingButton"),
  categoryFilter: document.getElementById("categoryFilter"),
  sortSelect: document.getElementById("sortSelect"),
  expensesTableBody: document.getElementById("expensesTableBody"),
  totalAmount: document.getElementById("totalAmount"),
  categorySummary: document.getElementById("categorySummary"),
  statusMessage: document.getElementById("statusMessage"),
  errorBanner: document.getElementById("errorBanner"),
  loadingBanner: document.getElementById("loadingBanner"),
};

const state = {
  expenses: [],
  allKnownCategories: [],
  isSubmitting: false,
};

function generateSubmissionKey() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }

  return `fallback-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatMoney(amount) {
  const numeric = Number(amount);
  return `INR ${numeric.toFixed(2)}`;
}

function getPendingSubmission() {
  const raw = window.localStorage.getItem(PENDING_SUBMISSION_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    window.localStorage.removeItem(PENDING_SUBMISSION_KEY);
    return null;
  }
}

function setPendingSubmission(entry) {
  window.localStorage.setItem(PENDING_SUBMISSION_KEY, JSON.stringify(entry));
  syncPendingControls();
}

function clearPendingSubmission() {
  window.localStorage.removeItem(PENDING_SUBMISSION_KEY);
  syncPendingControls();
}

function setStatus(message, isError = false) {
  elements.statusMessage.textContent = message;
  elements.statusMessage.style.color = isError ? "var(--error)" : "";
}

function setLoading(isLoading) {
  elements.loadingBanner.hidden = !isLoading;
}

function setError(message = "") {
  elements.errorBanner.hidden = !message;
  elements.errorBanner.textContent = message;
}

function syncPendingControls() {
  const pending = getPendingSubmission();
  const shouldShow = Boolean(pending);
  elements.retryPendingButton.hidden = !shouldShow;
  elements.discardPendingButton.hidden = !shouldShow;
}

function currentFilters() {
  return {
    category: elements.categoryFilter.value.trim(),
    sort: elements.sortSelect.value,
  };
}

function syncCategoryMode() {
  const isOther = elements.category.value === "Other";
  elements.customCategoryField.hidden = !isOther;
  elements.customCategory.required = isOther;

  if (!isOther) {
    elements.customCategory.value = "";
  }
}

async function loadExpenses() {
  setLoading(true);
  setError("");

  const filters = currentFilters();
  const params = new URLSearchParams();
  if (filters.category) {
    params.set("category", filters.category);
  }
  if (filters.sort) {
    params.set("sort", filters.sort);
  }

  try {
    const response = await fetch(`/api/expenses?${params.toString()}`);
    const body = await response.json();

    if (!response.ok) {
      throw new Error(body.error || "Failed to load expenses.");
    }

    state.expenses = body.expenses;
    state.allKnownCategories = [...new Set([...state.allKnownCategories, ...body.expenses.map((expense) => expense.category)])];
    renderExpenses();
    hydrateCategoryChoices();
    setStatus("Expenses loaded.");
  } catch (error) {
    setError(error.message || "Failed to load expenses.");
    setStatus("Unable to load expenses.", true);
  } finally {
    setLoading(false);
  }
}

function hydrateCategoryChoices() {
  const categories = [...new Set([...DEFAULT_CATEGORIES, ...state.allKnownCategories, ...state.expenses.map((expense) => expense.category)])].sort(
    (left, right) => left.localeCompare(right),
  );

  const previousFilter = elements.categoryFilter.value;
  elements.categoryFilter.innerHTML = '<option value="">All categories</option>';

  for (const category of categories) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    elements.categoryFilter.appendChild(option);
  }

  if (categories.includes(previousFilter)) {
    elements.categoryFilter.value = previousFilter;
  }
}

function renderExpenses() {
  if (state.expenses.length === 0) {
    elements.expensesTableBody.innerHTML = '<tr><td colspan="5" class="empty-row">No expenses match the current view.</td></tr>';
    elements.totalAmount.textContent = "INR 0.00";
    renderCategorySummary();
    return;
  }

  const total = state.expenses.reduce((sum, expense) => sum + Number(expense.amount), 0);
  elements.totalAmount.textContent = formatMoney(total);

  elements.expensesTableBody.innerHTML = state.expenses
    .map(
      (expense) => `
        <tr>
          <td>${expense.date}</td>
          <td>${escapeHtml(expense.category)}</td>
          <td>${escapeHtml(expense.description || "-")}</td>
          <td class="amount-column">${formatMoney(expense.amount)}</td>
          <td class="actions-column">
            <button class="inline-delete-button" type="button" data-expense-id="${expense.id}">Delete</button>
          </td>
        </tr>
      `,
    )
    .join("");

  renderCategorySummary();
}

function renderCategorySummary() {
  if (state.expenses.length === 0) {
    elements.categorySummary.innerHTML = '<p class="empty-row">No category summary yet.</p>';
    return;
  }

  const totals = new Map();
  for (const expense of state.expenses) {
    const current = totals.get(expense.category) || 0;
    totals.set(expense.category, current + Number(expense.amount));
  }

  elements.categorySummary.innerHTML = [...totals.entries()]
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(
      ([category, amount]) => `
        <article class="summary-card">
          <p class="summary-card-label">${escapeHtml(category)}</p>
          <p class="summary-card-value">${formatMoney(amount)}</p>
        </article>
      `,
    )
    .join("");
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function readFormData() {
  const selectedCategory = elements.category.value.trim();
  const customCategory = elements.customCategory.value.trim();

  return {
    amount: elements.amount.value.trim(),
    category: selectedCategory === "Other" ? customCategory : selectedCategory,
    description: elements.description.value.trim(),
    date: elements.date.value,
  };
}

function fillForm(data) {
  elements.amount.value = data.amount || "";
  if (DEFAULT_CATEGORIES.includes(data.category)) {
    elements.category.value = data.category;
    elements.customCategory.value = "";
  } else if (data.category) {
    elements.category.value = "Other";
    elements.customCategory.value = data.category;
  } else {
    elements.category.value = "";
    elements.customCategory.value = "";
  }
  elements.description.value = data.description || "";
  elements.date.value = data.date || "";
  syncCategoryMode();
}

function setSubmitting(isSubmitting) {
  state.isSubmitting = isSubmitting;
  elements.submitButton.disabled = isSubmitting;
  elements.submitButton.textContent = isSubmitting ? "Saving..." : "Save expense";
}

async function submitExpense(payload, submissionKey) {
  setSubmitting(true);
  setError("");
  setPendingSubmission({ key: submissionKey, payload });
  setStatus("Saving expense...");

  try {
    const response = await fetch("/api/expenses", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": submissionKey,
      },
      body: JSON.stringify(payload),
    });

    const body = await response.json();

    if (!response.ok) {
      throw new Error(body.error || "Failed to save expense.");
    }

    clearPendingSubmission();
    elements.expenseForm.reset();
    syncCategoryMode();
    elements.date.valueAsDate = new Date();
    await loadExpenses();
    setStatus(body.idempotency_replay ? "Recovered a previous submission safely." : "Expense saved.");
  } catch (error) {
    setError(error.message || "Failed to save expense.");
    setStatus("Expense not confirmed yet. Retry will reuse the same submission key.", true);
  } finally {
    setSubmitting(false);
  }
}

async function retryPendingSubmission() {
  const pending = getPendingSubmission();
  if (!pending) {
    return;
  }

  fillForm(pending.payload);
  await submitExpense(pending.payload, pending.key);
}

function discardPendingSubmission() {
  clearPendingSubmission();
  setError("");
  setStatus("Cleared the pending submission.");
}

async function deleteExpense(expenseId) {
  const confirmed = window.confirm("Delete this expense entry?");
  if (!confirmed) {
    return;
  }

  setError("");
  setStatus("Deleting expense...");

  try {
    const response = await fetch(`/api/expenses/${expenseId}`, {
      method: "DELETE",
    });
    const body = await response.json();

    if (!response.ok) {
      throw new Error(body.error || "Failed to delete expense.");
    }

    await loadExpenses();
    setStatus("Expense deleted.");
  } catch (error) {
    setError(error.message || "Failed to delete expense.");
    setStatus("Unable to delete expense.", true);
  }
}

function registerEventHandlers() {
  elements.expenseForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.isSubmitting) {
      return;
    }

    const payload = readFormData();
    const submissionKey = generateSubmissionKey();
    await submitExpense(payload, submissionKey);
  });

  elements.retryPendingButton.addEventListener("click", retryPendingSubmission);
  elements.discardPendingButton.addEventListener("click", discardPendingSubmission);
  elements.category.addEventListener("change", syncCategoryMode);
  elements.categoryFilter.addEventListener("change", loadExpenses);
  elements.sortSelect.addEventListener("change", loadExpenses);
  elements.expensesTableBody.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }

    const deleteButton = target.closest("[data-expense-id]");
    if (!deleteButton) {
      return;
    }

    const expenseId = deleteButton.getAttribute("data-expense-id");
    if (!expenseId) {
      return;
    }

    await deleteExpense(expenseId);
  });
}

async function bootstrap() {
  elements.date.valueAsDate = new Date();
  syncCategoryMode();
  registerEventHandlers();
  syncPendingControls();
  await loadExpenses();

  const pending = getPendingSubmission();
  if (pending) {
    fillForm(pending.payload);
    setStatus("Recovered a pending submission from local storage.");
  }
}

bootstrap();

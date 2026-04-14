const boardEl = document.getElementById("kanbanBoard");
const detailDrawerEl = document.getElementById("detailDrawer");
const detailContentEl = document.getElementById("detailContent");
let draggedCardId = null;

const STATUSES = [
  "\u53d7\u6ce8\u756a\u53f7\u672a\u63a1\u756a",
  "\u8a2d\u8a08\u30ea\u30b9\u30c8\u4f5c\u6210\u4e2d",
  "\u624b\u914d\u524d\u51e6\u7406",
  "\u8cfc\u8cb7\u624b\u914d\u4e2d",
  "\u624b\u914d\u5b8c\u4e86",
];

async function fetchKanban() {
  const response = await fetch("/kanban");
  return response.json();
}

async function refreshBoard() {
  const data = await fetchKanban();
  renderBoard(data.columns);
}

function renderBoard(columns) {
  boardEl.innerHTML = "";

  STATUSES.forEach((status, index) => {
    const column = document.createElement("section");
    column.className = "kanban-column";
    column.dataset.status = status;

    const header = document.createElement("div");
    header.className = "column-header";
    header.innerHTML = `<h3>${status}</h3><span>${(columns[status] || []).length}\u4ef6</span>`;
    column.appendChild(header);

    const dropZone = document.createElement("div");
    dropZone.className = "column-dropzone";
    dropZone.dataset.status = status;
    attachDropzoneEvents(dropZone);

    (columns[status] || []).forEach((item) => {
      const card = document.createElement("button");
      card.className = "kanban-card";
      card.draggable = true;
      card.dataset.id = String(item.id);
      card.innerHTML = `
        <strong>${escapeHtml(item.order_number || item.original_filename || "\u672a\u63a1\u756a")}</strong>
        <span>\u6a5f\u68b0\u756a\u53f7: ${escapeHtml(item.machine_number || "\u672a\u8a2d\u5b9a")}</span>
        <span>\u578b\u5f0f: ${escapeHtml(item.model || "\u672a\u8a2d\u5b9a")}</span>
        <span>\u5ba2\u5148\u540d: ${escapeHtml(item.customer_name || "\u672a\u8a2d\u5b9a")}</span>
        <span>\u5e0c\u671b\u6240\u8981\u65e5\u6570: ${escapeHtml(item.requested_lead_days || "\u672a\u8a2d\u5b9a")}</span>
      `;
      card.addEventListener("dragstart", (event) => {
        draggedCardId = item.id;
        card.classList.add("dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(item.id));
      });
      card.addEventListener("dragend", () => {
        draggedCardId = null;
        card.classList.remove("dragging");
        document.querySelectorAll(".column-dropzone").forEach((zone) => zone.classList.remove("drop-active"));
      });
      card.addEventListener("click", () => openDetail(item.id));
      dropZone.appendChild(card);
    });

    if (index === 0) {
      const addCardBox = document.createElement("div");
      addCardBox.className = "add-card-box";
      addCardBox.innerHTML = `
        <input id="newCardTitle" class="add-card-input" type="text" placeholder="\u53d7\u6ce8\u756a\u53f7\u3092\u5165\u529b" />
        <button id="addCardButton" class="add-card-button">+ \u30ab\u30fc\u30c9\u3092\u8ffd\u52a0</button>
      `;
      dropZone.appendChild(addCardBox);

      addCardBox.querySelector("#addCardButton").addEventListener("click", async () => {
        const input = addCardBox.querySelector("#newCardTitle");
        const title = input.value.trim();
        if (!title) return;

        const formData = new FormData();
        formData.append("title", title);
        await fetch("/cards", { method: "POST", body: formData });
        input.value = "";
        await refreshBoard();
      });
    }

    column.appendChild(dropZone);
    boardEl.appendChild(column);
  });
}

function attachDropzoneEvents(dropZone) {
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("drop-active");
  });

  dropZone.addEventListener("dragleave", (event) => {
    if (!dropZone.contains(event.relatedTarget)) {
      dropZone.classList.remove("drop-active");
    }
  });

  dropZone.addEventListener("drop", async (event) => {
    event.preventDefault();
    dropZone.classList.remove("drop-active");

    const droppedId = draggedCardId || Number(event.dataTransfer.getData("text/plain"));
    const nextStatus = dropZone.dataset.status;
    if (!droppedId || !nextStatus) return;

    const formData = new FormData();
    formData.append("document_id", String(droppedId));
    formData.append("status", nextStatus);

    await fetch("/update-status", { method: "POST", body: formData });
    await refreshBoard();
  });
}

async function openDetail(documentId) {
  const response = await fetch(`/documents/${documentId}`);
  const doc = await response.json();
  const attachments = doc.attachments || {};

  detailDrawerEl.classList.remove("hidden");

  const statusOptions = STATUSES.map((status) => {
    const selected = status === doc.status ? "selected" : "";
    return `<option value="${status}" ${selected}>${status}</option>`;
  }).join("");

  detailContentEl.innerHTML = `
    <div class="detail-block">
      <h3>${escapeHtml(doc.order_number || doc.original_filename || "\u672a\u63a1\u756a")}</h3>
      <p><strong>\u73fe\u5728\u30b9\u30c6\u30fc\u30bf\u30b9:</strong> ${escapeHtml(doc.status)}</p>
      <div class="inline-form">
        <select id="statusSelect">${statusOptions}</select>
        <button class="detail-action" id="statusUpdateButton">\u66f4\u65b0</button>
      </div>
      <div class="inline-form top-gap">
        <button class="detail-action primary" id="approveButton">\u627f\u8a8d</button>
      </div>
    </div>

    <div class="detail-block">
      <h4>\u30ab\u30fc\u30c9\u60c5\u5831</h4>
      <div class="detail-grid">
        <label>\u53d7\u6ce8\u756a\u53f7<input id="orderNumberInput" type="text" value="${escapeAttribute(doc.order_number || "")}" /></label>
        <label>\u6a5f\u68b0\u756a\u53f7<input id="machineNumberInput" type="text" value="${escapeAttribute(doc.machine_number || "")}" /></label>
        <label>\u578b\u5f0f<input id="modelInput" type="text" value="${escapeAttribute(doc.model || "")}" /></label>
        <label>\u5ba2\u5148\u540d<input id="customerNameInput" type="text" value="${escapeAttribute(doc.customer_name || "")}" /></label>
        <label>\u5e0c\u671b\u6240\u8981\u65e5\u6570<input id="requestedLeadDaysInput" type="text" value="${escapeAttribute(doc.requested_lead_days || "")}" /></label>
      </div>
      <div class="inline-form top-gap">
        <button class="detail-action" id="saveCardInfoButton">\u30ab\u30fc\u30c9\u60c5\u5831\u3092\u4fdd\u5b58</button>
      </div>
    </div>

    <div class="detail-block">
      <h4>\u6dfb\u4ed8\u30d5\u30a1\u30a4\u30eb</h4>
      ${renderAttachmentSlot(1, "\u6ce8\u6587\u60c5\u5831", attachments["1"])}
      ${renderAttachmentSlot(2, "\u8a2d\u8a08\u30ea\u30b9\u30c8", attachments["2"])}
      ${renderAttachmentSlot(3, "\u6dfb\u4ed8\u66f8\u985e", attachments["3"])}
      ${renderAttachmentSlot(4, "\u7dca\u6025\u4f5c\u696d\u6307\u793a\u66f8", attachments["4"])}
      ${renderAttachmentSlot(5, "\u56f3\u9762", attachments["5"])}
      ${renderAttachmentSlot(6, "AP\u304b\u3089\u306e\u8cc7\u6599", attachments["6"])}
      <p id="uploadStatusText" class="inline-note"></p>
    </div>

    <div class="detail-block">
      <h4>OCR \u30c6\u30ad\u30b9\u30c8</h4>
      <pre>${escapeHtml(doc.ocr_text || "OCR\u672a\u5b9f\u884c")}</pre>
    </div>

    <div class="detail-block">
      <h4>\u30d7\u30ec\u30d3\u30e5\u30fc</h4>
      ${renderPreview(doc.file_url)}
    </div>
  `;

  document.getElementById("statusUpdateButton").addEventListener("click", async () => {
    const formData = new FormData();
    formData.append("document_id", doc.id);
    formData.append("status", document.getElementById("statusSelect").value);
    await fetch("/update-status", { method: "POST", body: formData });
    await refreshBoard();
    await openDetail(doc.id);
  });

  document.getElementById("approveButton").addEventListener("click", async () => {
    await approveOrder(doc.id);
    await openDetail(doc.id);
  });

  document.getElementById("saveCardInfoButton").addEventListener("click", async () => {
    const formData = new FormData();
    formData.append("document_id", String(doc.id));
    formData.append("order_number", document.getElementById("orderNumberInput").value);
    formData.append("machine_number", document.getElementById("machineNumberInput").value);
    formData.append("model", document.getElementById("modelInput").value);
    formData.append("customer_name", document.getElementById("customerNameInput").value);
    formData.append("requested_lead_days", document.getElementById("requestedLeadDaysInput").value);

    await fetch("/cards/update", { method: "POST", body: formData });
    await refreshBoard();
    await openDetail(doc.id);
  });

  document.querySelectorAll("[data-upload-slot]").forEach((button) => {
    button.addEventListener("click", async () => {
      const slot = button.dataset.uploadSlot;
      const input = document.getElementById(`attachmentInput${slot}`);
      const statusText = document.getElementById("uploadStatusText");
      if (!input.files || !input.files.length) {
        statusText.textContent = "\u30d5\u30a1\u30a4\u30eb\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044\u3002";
        return;
      }

      const formData = new FormData();
      formData.append("document_id", String(doc.id));
      formData.append("attachment_slot", slot);
      formData.append("file", input.files[0]);

      const uploadResponse = await fetch("/upload", {
        method: "POST",
        body: formData,
      });

      if (!uploadResponse.ok) {
        statusText.textContent = "\u30a2\u30c3\u30d7\u30ed\u30fc\u30c9\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002";
        return;
      }

      statusText.textContent = `\u6dfb\u4ed8\u30d5\u30a1\u30a4\u30eb${slot}\u3092\u66f4\u65b0\u3057\u307e\u3057\u305f\u3002`;
      await refreshBoard();
      await openDetail(doc.id);
    });
  });
}

function renderAttachmentSlot(slot, label, attachment) {
  return `
    <div class="attachment-slot">
      <div>
        <strong>${label}</strong>
        <p>${escapeHtml(attachment?.original_filename || "\u672a\u6dfb\u4ed8")}</p>
      </div>
      <div class="attachment-actions">
        <input id="attachmentInput${slot}" type="file" accept=".pdf,.png,.jpg,.jpeg,.bmp,.tif,.tiff" />
        <button class="detail-action" data-upload-slot="${slot}">\u6dfb\u4ed8</button>
      </div>
    </div>
  `;
}

async function approveOrder(documentId) {
  const formData = new FormData();
  formData.append("document_id", documentId);
  await fetch("/approve-order", { method: "POST", body: formData });
  await refreshBoard();
}

function renderPreview(fileUrl) {
  if (!fileUrl) {
    return `<div class="empty-preview">\u30d5\u30a1\u30a4\u30eb\u306f\u307e\u3060\u7d10\u3065\u3044\u3066\u3044\u307e\u305b\u3093\u3002</div>`;
  }
  if (fileUrl.toLowerCase().endsWith(".pdf")) {
    return `<iframe src="${fileUrl}" class="file-preview"></iframe>`;
  }
  return `<img src="${fileUrl}" class="image-preview" alt="preview" />`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttribute(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

document.getElementById("refreshButton").addEventListener("click", refreshBoard);
document.getElementById("closeDrawerButton").addEventListener("click", () => {
  detailDrawerEl.classList.add("hidden");
});

refreshBoard();

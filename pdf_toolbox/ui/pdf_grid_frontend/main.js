"use strict";

const root = document.getElementById("root");
let currentItems = [];
let draggedCard = null;
let pointerDrag = null;

function eventId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function orderedIds(grid) {
  return Array.from(grid.querySelectorAll(".pdf-card")).map(
    (card) => card.dataset.itemId
  );
}

function report(action, details) {
  StreamlitProtocol.setComponentValue(
    Object.assign({ action, event_id: eventId() }, details)
  );
}

function rowsFor(cards) {
  const rows = [];
  for (const card of cards) {
    const rect = card.getBoundingClientRect();
    let row = rows[rows.length - 1];
    if (!row || Math.abs(row.top - rect.top) > 8) {
      row = { top: rect.top, bottom: rect.bottom, cards: [] };
      rows.push(row);
    }
    row.bottom = Math.max(row.bottom, rect.bottom);
    row.cards.push(card);
  }
  return rows;
}

function insertionReference(grid, x, y) {
  const cards = Array.from(grid.querySelectorAll(".pdf-card:not(.dragging)"));
  if (!cards.length) return null;

  const rows = rowsFor(cards);
  let row = rows[0];
  let bestDistance = Number.POSITIVE_INFINITY;
  for (const candidate of rows) {
    const center = (candidate.top + candidate.bottom) / 2;
    const distance = Math.abs(y - center);
    if (distance < bestDistance) {
      bestDistance = distance;
      row = candidate;
    }
  }

  for (const card of row.cards) {
    const rect = card.getBoundingClientRect();
    if (x < rect.left + rect.width / 2) return card;
  }

  const lastInRow = row.cards[row.cards.length - 1];
  const lastIndex = cards.indexOf(lastInRow);
  return cards[lastIndex + 1] || null;
}

function resizeFrame(grid) {
  requestAnimationFrame(() => {
    const parentHeight = Math.max(520, window.parent.innerHeight || 720);
    const maximum = Math.min(720, Math.round(parentHeight * 0.7));
    grid.style.maxHeight = `${maximum}px`;
    const height = Math.min(grid.scrollHeight, maximum);
    StreamlitProtocol.setFrameHeight(Math.max(128, height + 12));
  });
}

function commitKeyboardMove(card, offset) {
  const grid = card.parentElement;
  const cards = Array.from(grid.querySelectorAll(".pdf-card"));
  const current = cards.indexOf(card);
  const target = Math.max(0, Math.min(cards.length - 1, current + offset));
  if (target === current) return;

  if (target > current) {
    grid.insertBefore(card, cards[target].nextSibling);
  } else {
    grid.insertBefore(card, cards[target]);
  }
  report("reorder", { ordered_ids: orderedIds(grid) });
}

function beginPointerDrag(card, event) {
  if (!event.isPrimary || event.button !== 0) return;
  if (event.target.closest(".remove-button")) return;
  pointerDrag = {
    card,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    active: false,
  };
  card.setPointerCapture(event.pointerId);
}

function movePointerDrag(event) {
  if (!pointerDrag || pointerDrag.pointerId !== event.pointerId) return;
  const distance = Math.hypot(
    event.clientX - pointerDrag.startX,
    event.clientY - pointerDrag.startY
  );
  if (!pointerDrag.active && distance < 6) return;
  if (!pointerDrag.active) {
    pointerDrag.active = true;
    draggedCard = pointerDrag.card;
    draggedCard.classList.add("dragging");
  }

  event.preventDefault();
  const grid = draggedCard.parentElement;
  const reference = insertionReference(grid, event.clientX, event.clientY);
  if (reference !== draggedCard) grid.insertBefore(draggedCard, reference);
}

function finishPointerDrag(event, cancelled = false) {
  if (!pointerDrag || pointerDrag.pointerId !== event.pointerId) return;
  const { card, active } = pointerDrag;
  if (card.hasPointerCapture(event.pointerId)) {
    card.releasePointerCapture(event.pointerId);
  }
  pointerDrag = null;
  card.classList.remove("dragging");
  draggedCard = null;

  if (!active) return;
  if (cancelled) {
    render(currentItems);
    return;
  }
  report("reorder", { ordered_ids: orderedIds(card.parentElement) });
}

function makeCard(item, index) {
  const card = document.createElement("article");
  card.className = "pdf-card";
  card.dataset.itemId = item.id;
  card.tabIndex = 0;
  card.setAttribute(
    "aria-label",
    `第 ${index + 1} 份，${item.name}。可拖曳排序；Alt 加方向鍵也可移動。`
  );

  const order = document.createElement("span");
  order.className = "order-badge";
  order.textContent = String(index + 1);
  card.appendChild(order);

  const dragMark = document.createElement("span");
  dragMark.className = "drag-mark";
  dragMark.textContent = "⠿";
  dragMark.setAttribute("aria-hidden", "true");
  card.appendChild(dragMark);

  const remove = document.createElement("button");
  remove.className = "remove-button";
  remove.type = "button";
  remove.textContent = "×";
  remove.title = `移除 ${item.name}`;
  remove.setAttribute("aria-label", `移除 ${item.name}`);
  remove.addEventListener("pointerdown", (event) => event.stopPropagation());
  remove.addEventListener("dragstart", (event) => event.preventDefault());
  remove.addEventListener("click", (event) => {
    event.stopPropagation();
    report("remove", { item_id: item.id });
  });
  card.appendChild(remove);

  const preview = document.createElement("div");
  preview.className = "preview";
  if (item.thumbnail_url) {
    const image = document.createElement("img");
    image.src = item.thumbnail_url;
    image.alt = `${item.name} 第一頁預覽`;
    image.draggable = false;
    preview.appendChild(image);
  } else {
    const empty = document.createElement("div");
    empty.className = "preview-empty";
    empty.textContent = "無法顯示預覽";
    preview.appendChild(empty);
  }
  card.appendChild(preview);

  const body = document.createElement("div");
  body.className = "card-body";
  const filename = document.createElement("div");
  filename.className = "filename";
  filename.textContent = item.name;
  filename.title = item.name;
  body.appendChild(filename);

  const metadata = document.createElement("div");
  metadata.className = "metadata";
  const pages = item.page_count === null ? "無法讀取" : `${item.page_count} 頁`;
  metadata.textContent = `${pages} · ${item.size_mb.toFixed(1)} MB`;
  body.appendChild(metadata);

  if (item.error) {
    const error = document.createElement("div");
    error.className = "error";
    error.textContent = item.error;
    body.appendChild(error);
  }
  card.appendChild(body);

  card.addEventListener("pointerdown", (event) => beginPointerDrag(card, event));
  card.addEventListener("pointermove", movePointerDrag);
  card.addEventListener("pointerup", (event) => finishPointerDrag(event));
  card.addEventListener("pointercancel", (event) =>
    finishPointerDrag(event, true)
  );

  card.addEventListener("keydown", (event) => {
    if (!event.altKey) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      commitKeyboardMove(card, -1);
    } else if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      commitKeyboardMove(card, 1);
    }
  });

  return card;
}

function render(items) {
  currentItems = Array.isArray(items) ? items : [];
  root.replaceChildren();

  const grid = document.createElement("section");
  grid.className = "pdf-grid";
  grid.setAttribute("aria-label", "PDF 合併順序");
  currentItems.forEach((item, index) => grid.appendChild(makeCard(item, index)));

  root.appendChild(grid);
  resizeFrame(grid);
}

StreamlitProtocol.onRender((args) => render(args.items));
window.addEventListener("resize", () => {
  const grid = root.querySelector(".pdf-grid");
  if (grid) resizeFrame(grid);
});
StreamlitProtocol.ready();

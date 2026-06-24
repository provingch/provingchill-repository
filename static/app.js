const appContext = window.__APP_CONTEXT__ ?? {};
const authUser = appContext?.authenticated ? appContext.user ?? null : null;
const appTimezone = appContext?.timezone || "America/Asuncion";

const statusNode = document.getElementById("status");
const pagesListNode = document.getElementById("pages-list");
const emptyStateNode = document.getElementById("empty-state");
const originTimeCaptionNode = document.getElementById("origin-time-caption");
const originTimeChartNode = document.getElementById("origin-time-chart");
const originTimeLegendNode = document.getElementById("origin-time-legend");
const pagesPlaneCaptionNode = document.getElementById("pages-plane-caption");
const pagesPlaneChartNode = document.getElementById("pages-plane-chart");
const pagesPlaneLegendNode = document.getElementById("pages-plane-legend");
const chatStatusNode = document.getElementById("chat-status");
const chatListNode = document.getElementById("chat-list");
const chatFormNode = document.getElementById("chat-form");
const chatMessageInputNode = document.getElementById("chat-message");
const chatSubmitNode = document.getElementById("chat-submit");
const chatLiveBadgeNode = document.getElementById("chat-live-badge");
const chatSummaryCountNode = document.getElementById("chat-summary-count");
const ratingsAverageNode = document.getElementById("ratings-average");
const ratingsAverageStarsNode = document.getElementById("ratings-average-stars");
const ratingInputNodes = Array.from(document.querySelectorAll('input[name="rating"]'));
const profileUsernameInputNode = document.getElementById("profile-username");
const profileAvatarInputNode = document.getElementById("profile-avatar");
const profileAvatarRemoveInputNode = document.getElementById("profile-avatar-remove");
const accountNamePreviewNode = document.getElementById("account-name-preview");
const accountAvatarPreviewNode = document.getElementById("account-avatar-preview");
const navLinkNodes = Array.from(document.querySelectorAll("[data-nav-link]"));
const navSectionNodes = Array.from(document.querySelectorAll("[data-nav-section]"));
const currentPage = document.body?.dataset.page || "";

let liveSocket = null;
let visitsFallbackIntervalId = null;
let pagesRefreshIntervalId = null;
let chatFallbackIntervalId = null;
let chatMessages = [];
let ratingSummary = { total_ratings: 0, average_rating: 0 };

const VISITS_FALLBACK_POLL_MS = 10000;
const PAGES_POLL_MS = 30000;
const CHAT_POLL_MS = 5000;
const CHAT_HISTORY_LIMIT = 80;
const hasPagesPanel = Boolean(pagesListNode && emptyStateNode);
const hasVisitsPanel = Boolean(
  originTimeCaptionNode &&
    originTimeChartNode &&
    originTimeLegendNode &&
    pagesPlaneCaptionNode &&
    pagesPlaneChartNode &&
    pagesPlaneLegendNode
);
const hasChatPanel = Boolean(chatListNode);
const SOURCE_COLOR_PALETTE = [
  "#f6d365",
  "#ff8fab",
  "#7bdff2",
  "#b8f2e6",
  "#cdb4db",
  "#ffd6a5",
];
const PAGE_COLOR_PALETTE = ["#7bdff2", "#f6d365", "#ff8fab", "#b8f2e6", "#ffd6a5", "#cdb4db"];
const PROJECT_CATEGORY_CONFIG = [
  {
    key: "musical",
    title: "Paginas musicales",
    description: "Clips, lyrics pages y experiencias pensadas alrededor de una cancion.",
    badge: "Musical",
    emptyMessage: "Todavia no hay paginas musicales en esta carpeta.",
  },
  {
    key: "interactive",
    title: "Paginas interactivas",
    description: "Interfaces tocables, utilidades visuales y experimentos raros como la consola Linux.",
    badge: "Interactiva",
    emptyMessage: "Todavia no hay paginas interactivas cargadas.",
  },
];
const PROJECT_CATEGORY_MAP = Object.fromEntries(
  PROJECT_CATEGORY_CONFIG.map((category) => [category.key, category])
);
const SOURCE_COLOR_MAP = {
  direct: "#f6d365",
  link: "#7bdff2",
  instagram: "#ff8fab",
  discord: "#b8f2e6",
  whatsapp: "#7ae582",
  facebook: "#8fb8ff",
  messenger: "#8bbcff",
  telegram: "#89d2ff",
  threads: "#f7a072",
  x: "#cdb4db",
  reddit: "#ffb38a",
  linkedin: "#73c2fb",
  tiktok: "#9bf6ff",
  youtube: "#ff6b6b",
  slack: "#bdb2ff",
};
const SVG_NS = "http://www.w3.org/2000/svg";
const profilePreviewState = {
  username: authUser?.username || "",
  avatarUrl: authUser?.avatar_url || "",
  originalAvatarUrl: authUser?.avatar_url || "",
};

function setStatus(message = "", type = "") {
  if (!statusNode) {
    return;
  }
  statusNode.textContent = message;
  statusNode.className = `status ${type}`.trim();
}

function setChatStatus(message = "", type = "") {
  if (!chatStatusNode) {
    return;
  }
  chatStatusNode.textContent = message;
  chatStatusNode.className = `status ${type}`.trim();
  updateChatState(message, type);
}

function formatDate(isoDate) {
  try {
    return new Date(isoDate).toLocaleString("es-PY", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: appTimezone,
    });
  } catch {
    return isoDate;
  }
}

function formatChatTime(isoDate) {
  try {
    return new Date(isoDate).toLocaleString("es-PY", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: appTimezone,
    });
  } catch {
    return isoDate;
  }
}

function toNumber(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return 0;
  }
  return Math.floor(parsed);
}

function formatCount(value) {
  return toNumber(value).toLocaleString("es-ES");
}

function formatPercent(value, total) {
  if (!total) {
    return "0%";
  }
  return `${Math.round((toNumber(value) / total) * 100)}%`;
}

function getSeriesColor(label, index = 0, palette = "source") {
  if (palette === "source") {
    const normalizedLabel = String(label || "")
      .trim()
      .toLowerCase();
    return SOURCE_COLOR_MAP[normalizedLabel] || SOURCE_COLOR_PALETTE[index % SOURCE_COLOR_PALETTE.length];
  }

  return PAGE_COLOR_PALETTE[index % PAGE_COLOR_PALETTE.length];
}

function resolveTimelineSeriesColor(item, index = 0, palette = "source") {
  if (item?.color && typeof item.color === "string") {
    return item.color;
  }

  return getSeriesColor(item?.label || "", index, palette);
}

function getUserInitial(label) {
  const normalized = String(label || "?").trim();
  return normalized ? normalized.charAt(0).toUpperCase() : "?";
}

function renderStars(value, max = 5) {
  const rating = Math.max(0, Math.min(max, toNumber(value)));
  return `${"★".repeat(rating)}${"☆".repeat(Math.max(max - rating, 0))}`;
}

function updateChatState(message = "", type = "") {
  let badgeLabel = "Valoraciones";

  if (type === "ok") {
    badgeLabel = "Actualizado";
  } else if (type === "error") {
    badgeLabel = "Auto";
  }

  if (chatLiveBadgeNode) {
    chatLiveBadgeNode.textContent = badgeLabel;
    chatLiveBadgeNode.className = `chat-live-badge ${type}`.trim();
  }
}

function updateChatSummary() {
  if (chatSummaryCountNode) {
    chatSummaryCountNode.textContent = formatCount(ratingSummary.total_ratings || 0);
  }
}

function updateRatingSummary(summary = {}) {
  ratingSummary = {
    total_ratings: toNumber(summary?.total_ratings),
    average_rating: Number(summary?.average_rating || 0),
  };

  updateChatSummary();

  if (ratingsAverageNode) {
    ratingsAverageNode.textContent = ratingSummary.total_ratings
      ? ratingSummary.average_rating.toFixed(1)
      : "0.0";
  }

  if (ratingsAverageStarsNode) {
    const roundedAverage = Math.round(ratingSummary.average_rating || 0);
    ratingsAverageStarsNode.textContent = renderStars(roundedAverage);
  }
}

function getSelectedRating() {
  const selectedNode = ratingInputNodes.find((node) => node.checked);
  return selectedNode ? toNumber(selectedNode.value) : 5;
}

function resetRatingInputs() {
  ratingInputNodes.forEach((node) => {
    node.checked = node.value === "5";
  });
}

function createAvatarNode(user, className = "avatar-shell avatar-shell-xs") {
  const node = document.createElement("div");
  node.className = className;

  if (user?.avatar_url) {
    node.classList.add("has-image");
    const image = document.createElement("img");
    image.src = user.avatar_url;
    image.alt = user?.username ? `Foto de ${user.username}` : "Foto de perfil";
    image.loading = "lazy";
    image.decoding = "async";
    node.appendChild(image);
    return node;
  }

  const fallback = document.createElement("span");
  fallback.textContent = getUserInitial(user?.username);
  node.appendChild(fallback);
  return node;
}

function updateAccountAvatarPreview() {
  if (!accountAvatarPreviewNode) {
    return;
  }

  const username = profilePreviewState.username || authUser?.username || "?";
  const avatarUrl = profilePreviewState.avatarUrl || "";
  const fallback = getUserInitial(username);

  accountAvatarPreviewNode.classList.toggle("has-image", Boolean(avatarUrl));
  accountAvatarPreviewNode.innerHTML = "";

  if (avatarUrl) {
    const image = document.createElement("img");
    image.src = avatarUrl;
    image.alt = `Foto de ${username}`;
    accountAvatarPreviewNode.appendChild(image);
    return;
  }

  const span = document.createElement("span");
  span.textContent = fallback;
  accountAvatarPreviewNode.appendChild(span);
}

function createSvgNode(tagName) {
  return document.createElementNS(SVG_NS, tagName);
}

function appendChartEmptyState(
  container,
  legendNode,
  captionNode,
  chartMessage,
  captionMessage = "Sin datos en este rango."
) {
  if (container) {
    container.innerHTML = "";
    const emptyState = document.createElement("div");
    emptyState.className = "chart-empty-state";

    const emptyNode = document.createElement("p");
    emptyNode.className = "empty-inline";
    emptyNode.textContent = chartMessage;

    emptyState.appendChild(emptyNode);
    container.appendChild(emptyState);
  }
  if (legendNode) {
    legendNode.innerHTML = "";
  }
  if (captionNode) {
    captionNode.textContent = captionMessage;
  }
}

function renderTimelinePlane(
  chartNode,
  legendNode,
  captionNode,
  timeline = {},
  total = 0,
  options = {}
) {
  if (!chartNode || !legendNode || !captionNode) {
    return;
  }

  const {
    palette = "source",
    ariaLabel = "Plano cartesiano de visitas por tiempo",
    emptyLegendMessage = "Todavia no hay series con visitas.",
    emptyChartMessage = emptyLegendMessage,
    emptyCaptionMessage = "Sin datos en este rango.",
    captionBuilder = null,
  } = options;

  chartNode.innerHTML = "";
  legendNode.innerHTML = "";

  const labels = Array.isArray(timeline?.labels)
    ? timeline.labels.map((label) => String(label || "").trim()).filter(Boolean)
    : [];
  const series = Array.isArray(timeline?.series)
    ? timeline.series
        .map((item) => ({
          label: String(item?.label || "").trim() || "Serie",
          values: Array.isArray(item?.values) ? item.values.map((value) => toNumber(value)) : [],
          total: toNumber(item?.total),
          color: typeof item?.color === "string" ? item.color : "",
          favicon_url: typeof item?.favicon_url === "string" ? item.favicon_url : "",
        }))
        .filter((item) => item.values.length)
    : [];

  if (!labels.length || !series.length) {
    appendChartEmptyState(chartNode, legendNode, captionNode, emptyChartMessage, emptyCaptionMessage);
    return;
  }

  const maxValue = Math.max(1, ...series.flatMap((item) => item.values), 0);
  const width = Math.max(720, labels.length * 88);
  const height = 344;
  const margin = { top: 18, right: 18, bottom: 74, left: 62 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const gridSteps = 4;
  const frame = document.createElement("div");
  frame.className = "timeline-plane-frame";

  const svg = createSvgNode("svg");
  svg.classList.add("timeline-plane-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", ariaLabel);

  const xForIndex = (index) => {
    if (labels.length <= 1) {
      return innerWidth / 2;
    }
    return (innerWidth / (labels.length - 1)) * index;
  };
  const yForValue = (value) => innerHeight - (toNumber(value) / Math.max(maxValue, 1)) * innerHeight;

  for (let step = 0; step <= gridSteps; step += 1) {
    const y = margin.top + (innerHeight / gridSteps) * step;
    const value = Math.round((maxValue * (gridSteps - step)) / gridSteps);

    const gridLine = createSvgNode("line");
    gridLine.setAttribute("x1", String(margin.left));
    gridLine.setAttribute("x2", String(width - margin.right));
    gridLine.setAttribute("y1", String(y));
    gridLine.setAttribute("y2", String(y));
    gridLine.setAttribute("class", "timeline-plane-grid");
    svg.appendChild(gridLine);

    const yLabel = createSvgNode("text");
    yLabel.setAttribute("x", String(margin.left - 10));
    yLabel.setAttribute("y", String(y + 4));
    yLabel.setAttribute("text-anchor", "end");
    yLabel.setAttribute("class", "timeline-plane-axis-label");
    yLabel.textContent = formatCount(value);
    svg.appendChild(yLabel);
  }

  labels.forEach((label, index) => {
    const x = margin.left + xForIndex(index);

    const gridLine = createSvgNode("line");
    gridLine.setAttribute("x1", String(x));
    gridLine.setAttribute("x2", String(x));
    gridLine.setAttribute("y1", String(margin.top));
    gridLine.setAttribute("y2", String(height - margin.bottom));
    gridLine.setAttribute("class", "timeline-plane-grid timeline-plane-grid-vertical");
    svg.appendChild(gridLine);

    const xLabel = createSvgNode("text");
    xLabel.setAttribute("x", String(x));
    xLabel.setAttribute("y", String(height - margin.bottom + 24));
    xLabel.setAttribute("text-anchor", "middle");
    xLabel.setAttribute("class", "timeline-plane-axis-label");
    xLabel.textContent = label;
    svg.appendChild(xLabel);
  });

  const axisX = createSvgNode("line");
  axisX.setAttribute("x1", String(margin.left));
  axisX.setAttribute("x2", String(width - margin.right));
  axisX.setAttribute("y1", String(height - margin.bottom));
  axisX.setAttribute("y2", String(height - margin.bottom));
  axisX.setAttribute("class", "timeline-plane-axis");
  svg.appendChild(axisX);

  const axisY = createSvgNode("line");
  axisY.setAttribute("x1", String(margin.left));
  axisY.setAttribute("x2", String(margin.left));
  axisY.setAttribute("y1", String(margin.top));
  axisY.setAttribute("y2", String(height - margin.bottom));
  axisY.setAttribute("class", "timeline-plane-axis");
  svg.appendChild(axisY);

  const xAxisTitle = createSvgNode("text");
  xAxisTitle.setAttribute("x", String(margin.left + innerWidth / 2));
  xAxisTitle.setAttribute("y", String(height - 16));
  xAxisTitle.setAttribute("text-anchor", "middle");
  xAxisTitle.setAttribute("class", "timeline-plane-axis-title");
  xAxisTitle.textContent = "Dia";
  svg.appendChild(xAxisTitle);

  const yAxisTitle = createSvgNode("text");
  yAxisTitle.setAttribute("x", String(18));
  yAxisTitle.setAttribute("y", String(margin.top + innerHeight / 2));
  yAxisTitle.setAttribute("text-anchor", "middle");
  yAxisTitle.setAttribute("transform", `rotate(-90 18 ${margin.top + innerHeight / 2})`);
  yAxisTitle.setAttribute("class", "timeline-plane-axis-title");
  yAxisTitle.textContent = "Numero de visitas";
  svg.appendChild(yAxisTitle);

  series.forEach((item, index) => {
    const color = resolveTimelineSeriesColor(item, index, palette);
    const points = item.values
      .map((value, valueIndex) => `${margin.left + xForIndex(valueIndex)},${margin.top + yForValue(value)}`)
      .join(" ");

    const polyline = createSvgNode("polyline");
    polyline.setAttribute("points", points);
    polyline.setAttribute("fill", "none");
    polyline.setAttribute("stroke", color);
    polyline.setAttribute("stroke-width", "3");
    polyline.setAttribute("stroke-linejoin", "round");
    polyline.setAttribute("stroke-linecap", "round");
    polyline.setAttribute("class", "timeline-plane-line");
    svg.appendChild(polyline);

    item.values.forEach((value, valueIndex) => {
      const dot = createSvgNode("circle");
      dot.setAttribute("cx", String(margin.left + xForIndex(valueIndex)));
      dot.setAttribute("cy", String(margin.top + yForValue(value)));
      dot.setAttribute("r", "5");
      dot.setAttribute("fill", color);
      dot.setAttribute("class", "timeline-plane-dot");

      const title = createSvgNode("title");
      title.textContent = `${item.label} · ${labels[valueIndex]}: ${formatCount(value)} vistas`;
      dot.appendChild(title);
      svg.appendChild(dot);
    });
  });

  frame.appendChild(svg);
  chartNode.appendChild(frame);

  if (typeof captionBuilder === "function") {
    captionNode.textContent = captionBuilder({ labels, total, series });
  } else {
    captionNode.textContent = `Ultimos ${labels.length} dias · ${formatCount(total)} vistas totales`;
  }

  series.forEach((item, index) => {
    const color = resolveTimelineSeriesColor(item, index, palette);
    const legendItem = document.createElement("div");
    legendItem.className = "source-legend-item";

    const labelWrap = document.createElement("div");
    labelWrap.className = "source-legend-label";

    const dot = document.createElement("span");
    dot.className = "source-legend-dot";
    dot.style.background = color;

    const text = document.createElement("span");
    text.textContent = item.label;

    const value = document.createElement("strong");
    value.textContent = `${formatCount(item.total)} vistas`;

    labelWrap.append(dot, text);
    legendItem.append(labelWrap, value);
    legendNode.appendChild(legendItem);
  });
}

function renderVisitStats(payload) {
  if (!hasVisitsPanel) {
    return;
  }

  const total = toNumber(payload?.total);
  const originTimeline = payload?.origin_timeline ?? {};
  const pageTimeline = payload?.page_timeline ?? {};
  const topProject =
    payload?.top_project && typeof payload.top_project === "object" ? payload.top_project : null;

  renderTimelinePlane(originTimeChartNode, originTimeLegendNode, originTimeCaptionNode, originTimeline, total, {
    palette: "source",
    ariaLabel: "Plano cartesiano de vistas por dia y origen",
    emptyLegendMessage: "Todavia no hay origenes con visitas en este rango.",
    emptyChartMessage: "Todavia no hay origenes con visitas para dibujar este plano.",
    emptyCaptionMessage: "Sin origenes en este rango.",
  });
  renderTimelinePlane(pagesPlaneChartNode, pagesPlaneLegendNode, pagesPlaneCaptionNode, pageTimeline, total, {
    total,
    palette: "page",
    ariaLabel: "Plano cartesiano de vistas por dia y proyecto",
    emptyLegendMessage: "Todavia no hay proyectos con vistas en este rango.",
    emptyChartMessage: "Todavia no hay proyectos con vistas para dibujar este plano.",
    emptyCaptionMessage: "Sin proyectos en este rango.",
    captionBuilder: ({ labels, total: totalInRange }) =>
      topProject?.label && toNumber(topProject?.count) > 0
        ? `${topProject.label} va primero con ${formatCount(topProject.count)} vistas en ${labels.length} dias`
        : `Ultimos ${labels.length} dias · ${formatCount(totalInRange)} vistas totales`,
  });
}

function getPageInitial(page) {
  const label = String(page?.title || page?.slug || "?").trim();
  if (!label) {
    return "?";
  }
  return label.charAt(0).toUpperCase();
}

function createFaviconNode(page) {
  const faviconNode = document.createElement("div");
  faviconNode.className = "page-favicon";

  const initial = getPageInitial(page);
  const faviconUrl = page?.favicon_url;

  if (!faviconUrl) {
    faviconNode.classList.add("fallback");
    faviconNode.textContent = initial;
    return faviconNode;
  }

  const image = document.createElement("img");
  image.src = faviconUrl;
  image.alt = `Favicon de ${page?.title || page?.slug || "proyecto"}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.addEventListener("error", () => {
    faviconNode.classList.add("fallback");
    faviconNode.textContent = initial;
  });

  faviconNode.appendChild(image);
  return faviconNode;
}

function getProjectCategory(page) {
  return PROJECT_CATEGORY_MAP[page?.category] || PROJECT_CATEGORY_MAP.musical;
}

function applyPageLikeState(page, button, countNode, card = null) {
  const hasLiked = Boolean(page?.viewer_has_liked);
  const likeCount = toNumber(page?.like_count);

  if (button) {
    button.classList.toggle("is-liked", hasLiked);
    button.setAttribute("aria-pressed", hasLiked ? "true" : "false");
    button.textContent = hasLiked ? "Te gusta" : "Dar like";
  }

  if (countNode) {
    countNode.textContent = `${formatCount(likeCount)} likes`;
  }

  if (card) {
    card.classList.toggle("page-item-emphasis", likeCount > 0);
  }
}

async function handlePageLikeToggle(page, button, countNode, card = null) {
  if (!page?.slug || !button) {
    return;
  }

  if (!authUser) {
    setStatus("Inicia sesion para dejar likes en los proyectos.", "error");
    return;
  }

  button.disabled = true;

  try {
    const nextMethod = page.viewer_has_liked ? "DELETE" : "POST";
    const payload = await fetchJson(`/api/pages/${encodeURIComponent(page.slug)}/like`, {
      method: nextMethod,
    });

    page.like_count = toNumber(payload?.like_count);
    page.viewer_has_liked = Boolean(payload?.viewer_has_liked);
    applyPageLikeState(page, button, countNode, card);
    setStatus(page.viewer_has_liked ? "Like guardado." : "Like quitado.", "ok");
  } catch (error) {
    setStatus(error?.message || "No pude actualizar el like.", "error");
  } finally {
    button.disabled = false;
  }
}

function createPageCard(page) {
  const category = getProjectCategory(page);
  const card = document.createElement("article");
  card.className = "page-item";

  const header = document.createElement("div");
  header.className = "page-head";

  const faviconNode = createFaviconNode(page);
  const headText = document.createElement("div");
  headText.className = "page-head-text";

  const badgeRow = document.createElement("div");
  badgeRow.className = "page-badge-row";

  const badge = document.createElement("span");
  badge.className = `page-badge page-badge-${category.key}`;
  badge.textContent = category.badge;

  badgeRow.appendChild(badge);

  if (page?.version) {
    const versionBadge = document.createElement("span");
    versionBadge.className = "page-badge page-badge-version";
    versionBadge.textContent = String(page.version);
    badgeRow.appendChild(versionBadge);
  }

  const titleLink = document.createElement("a");
  titleLink.className = "page-title-link";
  titleLink.href = page.url;
  titleLink.setAttribute("aria-label", `Abrir proyecto ${page.title || page.slug}`);

  const title = document.createElement("h3");
  title.textContent = page.title || page.slug;
  titleLink.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "page-meta";

  const visitCount = document.createElement("span");
  visitCount.className = "page-meta-pill";
  visitCount.textContent = `${formatCount(page.visit_count)} vistas`;

  const likeCount = document.createElement("span");
  likeCount.className = "page-meta-pill";

  const actions = document.createElement("div");
  actions.className = "page-actions";

  const openLink = document.createElement("a");
  openLink.className = "page-action-link page-action-primary";
  openLink.href = page.url;
  openLink.textContent = "Abrir proyecto";

  const changelogLink = document.createElement("a");
  changelogLink.className = "page-action-link";
  changelogLink.href = page.changelog_url || "#";
  changelogLink.textContent = page?.has_changelog ? "Ver changelog" : "Changelog";

  const likeButton = document.createElement("button");
  likeButton.type = "button";
  likeButton.className = "page-like-button";
  likeButton.addEventListener("click", () => {
    handlePageLikeToggle(page, likeButton, likeCount, card);
  });

  headText.append(badgeRow, titleLink);
  header.append(faviconNode, headText);
  meta.append(visitCount, likeCount);
  actions.append(openLink, changelogLink, likeButton);
  card.append(header, meta, actions);
  applyPageLikeState(page, likeButton, likeCount, card);
  return card;
}

function createProjectGroup(category, pages) {
  const group = document.createElement("section");
  group.className = "project-group";

  const header = document.createElement("div");
  header.className = "project-group-head";

  const copy = document.createElement("div");
  copy.className = "project-group-copy";

  const kicker = document.createElement("p");
  kicker.className = "project-group-kicker";
  kicker.textContent = "Coleccion";

  const title = document.createElement("h2");
  title.textContent = category.title;

  const description = document.createElement("p");
  description.className = "project-group-description";
  description.textContent = category.description;

  const grid = document.createElement("div");
  grid.className = "project-group-grid";

  if (!pages.length) {
    const empty = document.createElement("div");
    empty.className = "project-group-empty";
    empty.textContent = category.emptyMessage;
    grid.appendChild(empty);
  } else {
    pages.forEach((page) => {
      grid.appendChild(createPageCard(page));
    });
  }

  copy.append(kicker, title, description);
  header.appendChild(copy);
  group.append(header, grid);
  return group;
}

function renderPages(pages) {
  if (!hasPagesPanel) {
    return;
  }

  pagesListNode.innerHTML = "";

  if (!pages.length) {
    emptyStateNode.hidden = false;
    return;
  }

  emptyStateNode.hidden = true;

  const sortedPages = [...pages].sort((a, b) => {
    const likeDelta = toNumber(b?.like_count) - toNumber(a?.like_count);
    if (likeDelta !== 0) {
      return likeDelta;
    }
    const visitDelta = toNumber(b?.visit_count) - toNumber(a?.visit_count);
    if (visitDelta !== 0) {
      return visitDelta;
    }
    const dateA = Date.parse(a?.updated_at || "");
    const dateB = Date.parse(b?.updated_at || "");
    return (Number.isFinite(dateB) ? dateB : 0) - (Number.isFinite(dateA) ? dateA : 0);
  });
  const groupedPages = Object.fromEntries(PROJECT_CATEGORY_CONFIG.map((category) => [category.key, []]));

  sortedPages.forEach((page) => {
    const category = getProjectCategory(page);
    groupedPages[category.key].push(page);
  });

  PROJECT_CATEGORY_CONFIG.forEach((category) => {
    pagesListNode.appendChild(createProjectGroup(category, groupedPages[category.key] || []));
  });
}

function renderChatMessages(messages) {
  if (!hasChatPanel) {
    return;
  }

  chatListNode.innerHTML = "";
  updateChatSummary();

  if (!messages.length) {
    const emptyNode = document.createElement("p");
    emptyNode.className = "chat-empty";
    emptyNode.textContent = "Todavia no hay valoraciones. Deja la primera.";
    chatListNode.appendChild(emptyNode);
    return;
  }

  messages.forEach((item) => {
    const isOwn = Boolean(authUser && item.username === authUser.username);
    const row = document.createElement("article");
    row.className = "chat-entry";
    if (isOwn) {
      row.classList.add("is-own");
    }

    const avatar = createAvatarNode(item, "avatar-shell avatar-shell-sm");

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";

    const head = document.createElement("div");
    head.className = "chat-entry-head";

    const author = document.createElement("div");
    author.className = "chat-entry-author";

    const username = document.createElement("strong");
    username.textContent = item.username || "usuario";

    const role = document.createElement("span");
    role.className = `role-pill ${item.role || "user"}`;
    role.textContent = item.role || "user";

    const time = document.createElement("time");
    time.className = "chat-entry-time";
    time.dateTime = item.created_at || "";
    time.textContent = formatChatTime(item.created_at || "");

    const stars = document.createElement("p");
    stars.className = "rating-entry-stars";
    stars.textContent = renderStars(item.rating || 0);

    const body = document.createElement("p");
    body.className = "chat-entry-message";
    body.textContent = item.message || "";

    author.append(username, role);
    head.append(author, time);
    bubble.append(head, stars, body);

    row.append(avatar, bubble);
    chatListNode.appendChild(row);
  });
}

function syncChatMessages(messages) {
  chatMessages = [...messages]
    .sort((a, b) => toNumber(b.id) - toNumber(a.id))
    .slice(0, CHAT_HISTORY_LIMIT);
  renderChatMessages(chatMessages);
}

function mergeChatMessage(message) {
  if (!message || typeof message !== "object") {
    return;
  }

  const existingIndex = chatMessages.findIndex(
    (entry) => toNumber(entry.id) === toNumber(message.id)
  );
  const nextMessages = [...chatMessages];

  if (existingIndex >= 0) {
    nextMessages[existingIndex] = {
      ...nextMessages[existingIndex],
      ...message,
    };
  } else {
    nextMessages.push(message);
  }

  chatMessages = nextMessages
    .sort((a, b) => toNumber(b.id) - toNumber(a.id))
    .slice(0, CHAT_HISTORY_LIMIT);
  renderChatMessages(chatMessages);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const error = new Error(payload?.error || `Request failed for ${url} (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return payload;
}

async function loadPages() {
  if (!hasPagesPanel) {
    return;
  }

  const payload = await fetchJson("/api/pages");
  renderPages(Array.isArray(payload.pages) ? payload.pages : []);
}

async function loadVisitStats() {
  if (!hasVisitsPanel) {
    return;
  }

  const payload = await fetchJson("/api/visits");
  renderVisitStats(payload);
}

async function loadChatMessages() {
  if (!authUser || !hasChatPanel) {
    return;
  }

  const payload = await fetchJson("/api/ratings");
  syncChatMessages(Array.isArray(payload.messages) ? payload.messages : []);
  updateRatingSummary(payload.summary || {});
}

async function loadDashboardInitial() {
  const tasks = [];

  if (hasPagesPanel) {
    tasks.push({ key: "pages", promise: loadPages() });
  }

  if (hasVisitsPanel) {
    tasks.push({ key: "visits", promise: loadVisitStats() });
  }

  if (authUser && hasChatPanel) {
    tasks.push({ key: "chat", promise: loadChatMessages() });
  }

  if (!tasks.length) {
    return;
  }

  const results = await Promise.allSettled(tasks.map((task) => task.promise));
  const failures = tasks
    .filter((task, index) => results[index]?.status === "rejected")
    .map((task) => task.key);

  if (failures.includes("chat")) {
    setChatStatus("No pude cargar las valoraciones.", "error");
  } else if (authUser && hasChatPanel) {
    setChatStatus("Valoraciones listas.", "ok");
  }

  if (!hasPagesPanel && !hasVisitsPanel) {
    return;
  }

  if (failures.includes("pages") && failures.includes("visits")) {
    setStatus("No pude cargar proyectos ni estadisticas.", "error");
    return;
  }

  if (failures.includes("pages")) {
    setStatus("Estadisticas listas; falló la lista de proyectos.", "error");
    return;
  }

  if (failures.includes("visits")) {
    setStatus("Proyectos listos; falló el panel de visitas.", "error");
    return;
  }

  setStatus("Proyectos listos con vistas y likes.", "ok");
}

function stopVisitsFallbackPolling() {
  if (visitsFallbackIntervalId !== null) {
    clearInterval(visitsFallbackIntervalId);
    visitsFallbackIntervalId = null;
  }
}

function startVisitsFallbackPolling() {
  if (!hasVisitsPanel || visitsFallbackIntervalId !== null) {
    return;
  }

  visitsFallbackIntervalId = window.setInterval(async () => {
    try {
      await loadVisitStats();
    } catch {
      // Keep quiet to avoid spamming status when backend is temporarily unavailable.
    }
  }, VISITS_FALLBACK_POLL_MS);
}

function stopChatFallbackPolling() {
  if (chatFallbackIntervalId !== null) {
    clearInterval(chatFallbackIntervalId);
    chatFallbackIntervalId = null;
  }
}

function startChatFallbackPolling() {
  if (!authUser || !hasChatPanel || chatFallbackIntervalId !== null) {
    return;
  }

  chatFallbackIntervalId = window.setInterval(async () => {
    try {
      await loadChatMessages();
    } catch {
      // Chat will retry automatically on next interval.
    }
  }, CHAT_POLL_MS);
}

function startPagesAutoRefresh() {
  if (!hasPagesPanel || pagesRefreshIntervalId !== null) {
    return;
  }

  pagesRefreshIntervalId = window.setInterval(async () => {
    try {
      await loadPages();
    } catch {
      // Project list will retry automatically on next interval.
    }
  }, PAGES_POLL_MS);
}

function setupLiveSocket() {
  if (!hasVisitsPanel && !hasChatPanel) {
    return;
  }

  if (typeof window.io !== "function") {
    setStatus("Socket no disponible. Uso refresco automatico.", "error");
    startVisitsFallbackPolling();
    startChatFallbackPolling();
    return;
  }

  liveSocket = window.io({
    path: "/socket.io",
    transports: ["polling"],
    upgrade: false,
  });

  liveSocket.on("connect", () => {
    console.info(`Socket.IO connected: ${liveSocket.id}`);
    stopVisitsFallbackPolling();
    stopChatFallbackPolling();
    setStatus("Visitas en vivo conectadas.", "ok");
    if (authUser && hasChatPanel) {
      setChatStatus("Valoraciones sincronizadas.", "ok");
    }
  });

  liveSocket.on("connect_error", () => {
    console.warn("Socket.IO connection failed, using fallback polling.");
    setStatus("Socket caido. Uso refresco automatico.", "error");
    startVisitsFallbackPolling();
    startChatFallbackPolling();
    if (authUser && hasChatPanel) {
      setChatStatus("Socket caido. Refrescando valoraciones automaticamente.", "error");
    }
  });

  liveSocket.on("disconnect", () => {
    console.info("Socket.IO disconnected.");
    setStatus("Socket desconectado. Reintentando...", "error");
    startVisitsFallbackPolling();
    startChatFallbackPolling();
    if (authUser && hasChatPanel) {
      setChatStatus("Valoraciones desconectadas. Reintentando...", "error");
    }
  });

  liveSocket.on("visits:update", (payload) => {
    if (!payload || typeof payload !== "object") {
      return;
    }

    if (payload.stats) {
      renderVisitStats(payload.stats);
    } else {
      renderVisitStats(payload);
    }
    setStatus("Visitas en vivo conectadas.", "ok");
  });

  liveSocket.on("chat:update", (payload) => {
    if (!authUser || !hasChatPanel || !payload || typeof payload !== "object") {
      return;
    }

    if (Array.isArray(payload.messages)) {
      syncChatMessages(payload.messages);
    } else if (payload.message) {
      mergeChatMessage(payload.message);
    }

    if (payload.summary) {
      updateRatingSummary(payload.summary);
    }

    setChatStatus("Valoraciones sincronizadas.", "ok");
  });
}

async function handleChatSubmit(event) {
  event.preventDefault();

  if (!chatMessageInputNode || !chatSubmitNode) {
    return;
  }

  const message = chatMessageInputNode.value.trim();
  if (!message) {
    setChatStatus("Escribe un comentario antes de publicarlo.", "error");
    return;
  }

  chatSubmitNode.disabled = true;

  try {
    const payload = await fetchJson("/api/ratings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, rating: getSelectedRating() }),
    });

    if (payload?.message) {
      mergeChatMessage(payload.message);
    }

    if (payload?.summary) {
      updateRatingSummary(payload.summary);
    }

    try {
      await loadChatMessages();
    } catch {
      // If the refresh fails, we still keep the message already merged locally.
    }

    chatMessageInputNode.value = "";
    resetRatingInputs();
    setChatStatus("Valoracion publicada.", "ok");
  } catch (error) {
    setChatStatus(error?.message || "No pude publicar la valoracion.", "error");
  } finally {
    chatSubmitNode.disabled = false;
    if (chatMessageInputNode) {
      chatMessageInputNode.focus();
    }
  }
}

function setupChatForm() {
  if (!authUser || !chatFormNode) {
    return;
  }

  resetRatingInputs();
  chatFormNode.addEventListener("submit", handleChatSubmit);
}

function refreshProfilePreview() {
  if (accountNamePreviewNode) {
    accountNamePreviewNode.textContent = profilePreviewState.username || authUser?.username || "";
  }
  updateAccountAvatarPreview();
}

function setupProfilePreview() {
  if (!authUser) {
    return;
  }

  refreshProfilePreview();

  if (profileUsernameInputNode) {
    profileUsernameInputNode.addEventListener("input", () => {
      profilePreviewState.username = profileUsernameInputNode.value.trim() || authUser.username || "";
      refreshProfilePreview();
    });
  }

  if (profileAvatarRemoveInputNode) {
    profileAvatarRemoveInputNode.addEventListener("change", () => {
      if (profileAvatarRemoveInputNode.checked) {
        profilePreviewState.avatarUrl = "";
      } else {
        profilePreviewState.avatarUrl = profilePreviewState.originalAvatarUrl;
      }
      refreshProfilePreview();
    });
  }

  if (profileAvatarInputNode) {
    profileAvatarInputNode.addEventListener("change", () => {
      const [file] = profileAvatarInputNode.files || [];
      if (!file) {
        if (profileAvatarRemoveInputNode?.checked) {
          profilePreviewState.avatarUrl = "";
        } else {
          profilePreviewState.avatarUrl = profilePreviewState.originalAvatarUrl;
        }
        refreshProfilePreview();
        return;
      }

      if (profileAvatarRemoveInputNode) {
        profileAvatarRemoveInputNode.checked = false;
      }

      const reader = new FileReader();
      reader.addEventListener("load", () => {
        profilePreviewState.avatarUrl = typeof reader.result === "string" ? reader.result : "";
        refreshProfilePreview();
      });
      reader.readAsDataURL(file);
    });
  }
}

function setActiveNavLink(sectionId) {
  if (currentPage !== "home" || !navLinkNodes.length) {
    return;
  }

  navLinkNodes.forEach((link) => {
    const linkTarget = link.dataset.navLink || "";
    const isActive = link.getAttribute("href")?.startsWith("#") && linkTarget === sectionId;
    link.classList.toggle("is-active", isActive);

    if (isActive) {
      link.setAttribute("aria-current", "location");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function setupNavTracker() {
  if (currentPage !== "home" || !navLinkNodes.length || !navSectionNodes.length) {
    return;
  }

  const initialSection = window.location.hash ? decodeURIComponent(window.location.hash.slice(1)) : "inicio";
  setActiveNavLink(initialSection);

  navLinkNodes.forEach((link) => {
    if (!link.getAttribute("href")?.startsWith("#")) {
      return;
    }

    link.addEventListener("click", () => {
      setActiveNavLink(link.dataset.navLink || "inicio");
    });
  });

  if (!("IntersectionObserver" in window)) {
    return;
  }

  const observedEntries = new Map();
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        observedEntries.set(entry.target.id, entry);
      });

      const visibleEntries = Array.from(observedEntries.values())
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

      if (!visibleEntries.length) {
        return;
      }

      const nextSection = visibleEntries[0].target.id;
      if (nextSection) {
        setActiveNavLink(nextSection);
      }
    },
    {
      threshold: [0.35, 0.6, 0.85],
      rootMargin: "-24% 0px -52% 0px",
    }
  );

  navSectionNodes.forEach((node) => observer.observe(node));

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash ? decodeURIComponent(window.location.hash.slice(1)) : "inicio";
    setActiveNavLink(hash || "inicio");
  });
}

updateChatState();
updateChatSummary();
loadDashboardInitial();
startPagesAutoRefresh();
setupLiveSocket();
setupChatForm();
setupProfilePreview();
setupNavTracker();

const statusNode = document.getElementById("status");
const pagesListNode = document.getElementById("pages-list");
const emptyStateNode = document.getElementById("empty-state");
const navLinkNodes = Array.from(document.querySelectorAll("[data-nav-link]"));
const navSectionNodes = Array.from(document.querySelectorAll("[data-nav-section]"));
const currentPage = document.body?.dataset.page || "";

const PAGES_POLL_MS = 30000;
const hasPagesPanel = Boolean(pagesListNode && emptyStateNode);

const PROJECT_CATEGORY_CONFIG = [
  {
    key: "musical",
    title: "Páginas musicales",
    description: "Clips, lyric pages y experiencias pensadas alrededor de una canción.",
    badge: "Musical",
    emptyMessage: "Todavía no hay páginas musicales en esta carpeta.",
  },
  {
    key: "interactive",
    title: "Páginas interactivas",
    description: "Interfaces tocables, utilidades visuales y experimentos como la consola Linux.",
    badge: "Interactiva",
    emptyMessage: "Todavía no hay páginas interactivas cargadas.",
  },
];
const PROJECT_CATEGORY_MAP = Object.fromEntries(
  PROJECT_CATEGORY_CONFIG.map((category) => [category.key, category])
);

let pagesRefreshIntervalId = null;

function setStatus(message = "", type = "") {
  if (!statusNode) {
    return;
  }
  statusNode.textContent = message;
  statusNode.className = `status ${type}`.trim();
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

function getPageInitial(page) {
  const label = String(page?.title || page?.slug || "?").trim();
  return label ? label.charAt(0).toUpperCase() : "?";
}

function createFaviconNode(page) {
  const faviconNode = document.createElement("div");
  faviconNode.className = "page-favicon";

  const initial = getPageInitial(page);
  const faviconUrl = page?.favicon_url;

  if (!faviconUrl) {
    faviconNode.textContent = initial;
    return faviconNode;
  }

  const image = document.createElement("img");
  image.src = faviconUrl;
  image.alt = `Favicon de ${page?.title || page?.slug || "proyecto"}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.addEventListener("error", () => {
    faviconNode.innerHTML = "";
    faviconNode.textContent = initial;
  });

  faviconNode.appendChild(image);
  return faviconNode;
}

function getProjectCategory(page) {
  return PROJECT_CATEGORY_MAP[page?.category] || PROJECT_CATEGORY_MAP.musical;
}

function createPageCard(page) {
  const category = getProjectCategory(page);
  const card = document.createElement("article");
  card.className = "page-item";

  const header = document.createElement("div");
  header.className = "page-item-head";

  const faviconNode = createFaviconNode(page);
  const headText = document.createElement("div");
  headText.className = "page-head-text";

  const badgeRow = document.createElement("div");
  badgeRow.className = "page-badge-row";

  const badge = document.createElement("span");
  badge.className = "page-badge";
  badge.textContent = category.badge;
  badgeRow.appendChild(badge);

  if (page?.version) {
    const versionBadge = document.createElement("span");
    versionBadge.className = "page-badge";
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

  headText.append(badgeRow, titleLink);
  header.append(faviconNode, headText);

  const meta = document.createElement("div");
  meta.className = "page-meta";

  const visitCount = document.createElement("span");
  visitCount.className = "page-meta-pill";
  visitCount.textContent = `${formatCount(page.visit_count)} vistas`;
  meta.appendChild(visitCount);

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

  actions.append(openLink, changelogLink);
  card.append(header, meta, actions);
  return card;
}

function createProjectGroup(category, pages) {
  const group = document.createElement("section");
  group.className = "project-group";

  const header = document.createElement("div");
  header.className = "project-group-head";

  const num = document.createElement("span");
  num.className = "project-group-num";
  num.textContent = category.key === "musical" ? "01" : "02";

  const copy = document.createElement("div");

  const title = document.createElement("h2");
  title.className = "project-group-title";
  title.textContent = category.title;

  const description = document.createElement("p");
  description.className = "project-group-description";
  description.textContent = category.description;

  copy.append(title, description);
  header.append(num, copy);

  const grid = document.createElement("div");
  grid.className = "project-group-grid";

  if (!pages.length) {
    const empty = document.createElement("div");
    empty.className = "project-group-empty";
    empty.textContent = category.emptyMessage;
    grid.appendChild(empty);
  } else {
    pages.forEach((page) => grid.appendChild(createPageCard(page)));
  }

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

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: { Accept: "application/json", ...(options.headers || {}) },
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

async function loadDashboardInitial() {
  if (!hasPagesPanel) {
    return;
  }

  try {
    await loadPages();
    setStatus("Proyectos listos.", "ok");
  } catch {
    setStatus("No pude cargar la lista de proyectos.", "error");
  }
}

function startPagesAutoRefresh() {
  if (!hasPagesPanel || pagesRefreshIntervalId !== null) {
    return;
  }

  pagesRefreshIntervalId = window.setInterval(async () => {
    try {
      await loadPages();
    } catch {
      // Reintenta automáticamente en el próximo intervalo.
    }
  }, PAGES_POLL_MS);
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
      entries.forEach((entry) => observedEntries.set(entry.target.id, entry));

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
    { threshold: [0.35, 0.6, 0.85], rootMargin: "-24% 0px -52% 0px" }
  );

  navSectionNodes.forEach((node) => observer.observe(node));

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash ? decodeURIComponent(window.location.hash.slice(1)) : "inicio";
    setActiveNavLink(hash || "inicio");
  });
}

loadDashboardInitial();
startPagesAutoRefresh();
setupNavTracker();
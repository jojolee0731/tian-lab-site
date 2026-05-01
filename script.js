const SUPPORTED_LANGUAGES = ["en", "zh", "es"];

const state = {
  data: null,
  lang: SUPPORTED_LANGUAGES.includes(localStorage.getItem("tian-lab-language"))
    ? localStorage.getItem("tian-lab-language")
    : "en",
};

const header = document.querySelector(".site-header");
const canvas = document.getElementById("rhythm-canvas");
const ctx = canvas.getContext("2d");
const languageButtons = document.querySelectorAll(".language-option");
const navToggle = document.querySelector(".nav-toggle");
const nav = document.getElementById("site-nav");

const rhythm = {
  points: [],
  width: 0,
  height: 0,
  beat: 0,
};

const pick = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return value ?? "";
  return value[state.lang] || value.en || "";
};

const setText = (slot, value) => {
  document.querySelectorAll(`[data-slot="${slot}"]`).forEach((element) => {
    element.textContent = value;
  });
};

const linkLabel = (type) => {
  const labels = state.data.labels;
  return pick(labels[type] || labels.link);
};

const externalIcon = `<svg aria-hidden="true" viewBox="0 0 16 16"><path d="M5.1 3h7.9v7.9h-1.6V5.8l-7 7-1.1-1.1 7-7H5.1V3Z"/></svg>`;

const disciplineIcons = {
  clinical: `<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M10.5 4h3v6h6v3h-6v6h-3v-6h-6v-3h6z"/></svg>`,
  chemistry: `<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M9 3h6v2l-1.5 2.4v3.5l4.8 7.6A2 2 0 0 1 16.6 21H7.4a2 2 0 0 1-1.7-3.1l4.8-7.6V7.4L9 5z"/></svg>`,
  imaging: `<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 5c4.8 0 8.9 2.9 10.6 7-1.7 4.1-5.8 7-10.6 7S3.1 16.1 1.4 12C3.1 7.9 7.2 5 12 5zm0 3.2A3.8 3.8 0 1 0 12 15.8 3.8 3.8 0 0 0 12 8.2z"/></svg>`,
  engineering: `<svg aria-hidden="true" viewBox="0 0 24 24"><path d="m13.7 2 .7 2.3 2 .8 2.1-1.2 2.1 2.1-1.2 2.1.8 2 .3.1 2.2.6v3l-2.3.7-.8 2 1.2 2.1-2.1 2.1-2.1-1.2-2 .8-.7 2.3h-3l-.7-2.3-2-.8-2.1 1.2-2.1-2.1 1.2-2.1-.8-2L2 13.7v-3l2.3-.7.8-2L3.9 5.9 6 3.8l2.1 1.2 2-.8.7-2.3zM12 8.4A3.6 3.6 0 1 0 12 15.6 3.6 3.6 0 0 0 12 8.4z"/></svg>`,
  pharmacy: `<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M8.5 4h7a3.5 3.5 0 0 1 0 7h-7a3.5 3.5 0 1 1 0-7zm1.2 9h4.6l5.2 5.2a3.3 3.3 0 1 1-4.7 4.7z"/></svg>`,
  biology: `<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3c4 0 7 3 7 7 0 5.1-4.2 8.7-7 11-2.8-2.3-7-5.9-7-11 0-4 3-7 7-7zm0 3.4c-1.6 0-2.9 1.3-2.9 2.9S10.4 12.2 12 12.2s2.9-1.3 2.9-2.9S13.6 6.4 12 6.4z"/></svg>`,
  computing: `<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 5h16v10H4zm2 2v6h12V7zm3 10h6v2H9z"/></svg>`,
};

const disciplineMap = [
  {
    key: "clinical",
    match: /(临床|精神病学|神经外科|烧伤整形|超声|医学检验|放射影像学$)/i,
    label: { en: "Clinical Medicine", zh: "临床医学", es: "Medicina clínica" },
  },
  {
    key: "chemistry",
    match: /(化学|配合物|荧光探针|有机化学)/i,
    label: { en: "Chemistry", zh: "化学", es: "Química" },
  },
  {
    key: "pharmacy",
    match: /(药学|药物化学|药物递送)/i,
    label: { en: "Pharmacy", zh: "药学", es: "Farmacia" },
  },
  {
    key: "imaging",
    match: /(影像|磁共振|MRI|PET|放射|成像)/i,
    label: { en: "Imaging", zh: "影像", es: "Imagen" },
  },
  {
    key: "engineering",
    match: /(机械|工程|流体力学|纳米材料|材料)/i,
    label: { en: "Engineering", zh: "工程", es: "Ingeniería" },
  },
  {
    key: "computing",
    match: /(计算|AI|精神影像.*预测|计算生物学)/i,
    label: { en: "Computing", zh: "计算", es: "Computación" },
  },
  {
    key: "biology",
    match: /(生物|类淋巴|阿尔兹海默|抑郁|衰老|炎症|器官)/i,
    label: { en: "Biology", zh: "生物", es: "Biología" },
  },
];

function getDiscipline(person) {
  const haystack = `${person.affiliation || ""} ${pick(person.focus) || ""} ${pick(person.role) || ""}`;
  const matched = disciplineMap.find((item) => item.match.test(haystack));
  return matched || { key: "biology", label: { en: "Biology", zh: "生物", es: "Biología" } };
}

function getMemberTier(person) {
  const tierMap = {
    "Postdoctoral Fellows": {
      key: "postdoc",
      label: { en: "Postdoc", zh: "博后", es: "Postdoc" },
    },
    "PhD Students": {
      key: "phd",
      label: { en: "PhD", zh: "博士", es: "PhD" },
    },
    "Master Students": {
      key: "master",
      label: { en: "Master", zh: "硕士", es: "Máster" },
    },
    "Undergraduate Students": {
      key: "undergrad",
      label: { en: "UG", zh: "本科", es: "Grado" },
    },
    "Research Staff": {
      key: "staff",
      label: { en: "Staff", zh: "技术", es: "Staff" },
    },
  };

  return (
    tierMap[person.group] || {
      key: "member",
      label: { en: "Member", zh: "成员", es: "Miembro" },
    }
  );
}

function renderNav() {
  nav.innerHTML = state.data.nav
    .map((item) => `<a href="${item.href}">${pick(item.label)}</a>`)
    .join("");
}

function renderSlots() {
  const copy = state.data.copy;
  Object.entries(copy).forEach(([slot, value]) => setText(slot, pick(value)));

  document.title = pick(state.data.meta.title);
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : state.lang;
  document.querySelector('meta[name="description"]').setAttribute("content", pick(state.data.meta.description));

  const heroImage = document.querySelector('[data-slot="heroImage"]');
  heroImage.src = state.data.hero.image;
  heroImage.alt = pick(state.data.hero.alt);
}

function updateLanguageButtons() {
  languageButtons.forEach((button) => {
    const isActive = button.dataset.lang === state.lang;
    button.dataset.active = String(isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function renderMetrics() {
  const metrics = document.getElementById("hero-metrics");
  metrics.innerHTML = state.data.hero.metrics
    .map(
      (metric) => `
        <div>
          <dt>${metric.value}</dt>
          <dd>${pick(metric.label)}</dd>
        </div>
      `,
    )
    .join("");
}

function renderSignals() {
  const strip = document.getElementById("signal-strip");
  strip.innerHTML = state.data.signals.map((signal) => `<span>${pick(signal)}</span>`).join("");
}

function renderNews() {
  const rack = document.getElementById("news-rack");
  rack.innerHTML = state.data.news
    .slice(0, 3)
    .map(
      (item) => `
        <article class="news-item">
          <span>${item.date}</span>
          <p>${pick(item.title)}</p>
        </article>
      `,
    )
    .join("");
}

function renderTracks() {
  const grid = document.getElementById("track-grid");
  grid.innerHTML = state.data.researchTracks
    .map(
      (track, index) => `
        <article class="track-card" style="--track-image: url('${track.image}')">
          <div class="track-index">
            <span>${String(index + 1).padStart(2, "0")}</span>
            <i></i>
          </div>
          <h3>${pick(track.title)}</h3>
          <p>${pick(track.claim)}</p>
          <ul>
            ${pick(track.points)
              .map((point) => `<li>${point}</li>`)
              .join("")}
          </ul>
        </article>
      `,
    )
    .join("");
}

function renderResearchMap() {
  const map = document.getElementById("research-map");
  map.innerHTML = `
    <div class="research-map-heading">
      <span>${state.lang === "zh" ? "研究逻辑" : state.lang === "es" ? "Lógica" : "Logic"}</span>
      <strong>${
        state.lang === "zh"
          ? "从屏障识别到影像读出，再到转化干预"
          : state.lang === "es"
            ? "Del reconocimiento de barrera a la lectura por imagen y la intervención"
            : "From barrier recognition to imaging readout and translational intervention"
      }</strong>
    </div>
    <ol>
      ${state.data.researchTracks
        .map(
          (track, index) => `
            <li>
              <span>${String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>${pick(track.title)}</strong>
                <p>${pick(track.claim)}</p>
              </div>
            </li>
          `,
        )
        .join("")}
    </ol>
  `;
}

function renderPublications() {
  const list = document.getElementById("publication-list");
  list.innerHTML = state.data.publications
    .map(
      (publication) => `
        <article class="publication-item">
          <span class="pub-year">${publication.year}</span>
          <div class="pub-main">
            <h3>${publication.title}</h3>
            <p class="pub-authors">${publication.authors}</p>
            <p class="pub-journal">${publication.journal}</p>
            <p>${pick(publication.note)}</p>
            <div class="pub-links">
              <a href="${publication.url}" target="_blank" rel="noopener noreferrer">
                DOI ${publication.doi} ${externalIcon}
              </a>
              <span>${publication.track}</span>
            </div>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderRecentPublications() {
  const list = document.getElementById("recent-publication-list");
  if (!list) return;

  list.innerHTML = state.data.recentPublications
    .map((publication) => {
      const source = [publication.journal, publication.volume, publication.article].filter(Boolean).join(" · ");
      const link = publication.url
        ? `<a href="${publication.url}" target="_blank" rel="noopener noreferrer">
            Article ${externalIcon}
          </a>`
        : "";

      return `
        <article class="recent-publication-item">
          <span class="pub-year">${publication.year}</span>
          <div class="pub-main">
            <h3>${publication.title}</h3>
            <p class="pub-authors">${publication.authors}</p>
            <p class="pub-journal">${source}</p>
            <p>${pick(publication.highlight)}</p>
            <div class="pub-links">
              ${link}
              <span>${publication.track}</span>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderCovers() {
  const grid = document.getElementById("cover-grid");
  grid.innerHTML = state.data.covers
    .map(
      (cover) => `
        <article class="cover-card" data-journal="${cover.journal}">
          <figure class="cover-art">
            <img src="${cover.image}" alt="${pick(cover.alt)}" loading="lazy" />
          </figure>
          <div class="cover-copy">
            <p class="cover-meta">${cover.journal} · ${cover.year}</p>
            <h3>${pick(cover.title)}</h3>
            <p>${pick(cover.body)}</p>
            <a class="cover-link" href="${cover.url}" target="_blank" rel="noopener noreferrer">
              ${linkLabel(cover.linkType)} ${externalIcon}
            </a>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderPeople() {
  const grid = document.getElementById("people-grid");
  const adminStaff = state.data.people.find((person) => person.name === "陈香淼");
  const sections = [
    {
      key: "postdocs",
      title: { en: "Postdoctoral Fellows", zh: "博士后", es: "Postdocs" },
      caption: {
        en: "Independent researchers driving probes, materials, imaging, and translational platforms.",
        zh: "推动探针、材料、影像与转化平台的独立研究力量。",
        es: "Investigadores que impulsan sondas, materiales, imagen y plataformas traslacionales.",
      },
      groups: ["Postdoctoral Fellows"],
    },
    {
      key: "students",
      title: { en: "Students", zh: "学生", es: "Estudiantes" },
      caption: {
        en: "PhD, master, and undergraduate students working across medicine, imaging, chemistry, engineering, and AI.",
        zh: "博士、硕士和本科生，方向横跨医学、影像、化学、工程与 AI。",
        es: "Doctorandos, estudiantes de máster y grado en medicina, imagen, química, ingeniería e IA.",
      },
      groups: ["PhD Students", "Master Students", "Undergraduate Students"],
    },
    {
      key: "staff",
      title: { en: "Research Staff", zh: "技术员 / 科研助理", es: "Personal técnico" },
      caption: {
        en: "The operational backbone for experiments, imaging workflows, and lab coordination.",
        zh: "支撑实验、影像流程和课题组日常协同的关键力量。",
        es: "La base operativa para experimentos, flujos de imagen y coordinación del laboratorio.",
      },
      groups: ["Research Staff"],
    },
  ];

  const personCard = (person) => `
    ${(() => {
      const discipline = getDiscipline(person);
      const tier = getMemberTier(person);
      return `
    <article class="person-card" data-group="${person.group || "Members"}">
      <figure class="person-photo">
        ${
          person.image
            ? `<img src="${person.image}" alt="${person.name}" loading="lazy" />`
            : `<div class="person-placeholder" aria-hidden="true">${person.name.slice(0, 1)}</div>`
        }
        <div class="member-tier member-tier-${tier.key}">${pick(tier.label)}</div>
        <div class="discipline-badge discipline-${discipline.key}" title="${pick(discipline.label)}" aria-label="${pick(discipline.label)}">
          ${disciplineIcons[discipline.key]}
        </div>
      </figure>
      <div class="person-copy">
        <span class="role">${pick(person.role)}</span>
        <h3>${person.name}</h3>
        ${person.affiliation ? `<p class="person-affiliation">${person.affiliation}</p>` : ""}
        ${pick(person.focus) ? `<p>${pick(person.focus)}</p>` : ""}
        <div class="person-meta">
          ${person.joined ? `<span>Since ${person.joined}</span>` : ""}
        </div>
        ${person.email ? `<a href="mailto:${person.email}">${person.email}</a>` : ""}
      </div>
    </article>
  `;
    })()}
  `;

  grid.innerHTML = sections
    .map((section) => {
      const members = state.data.people.filter((person) => {
        if (!section.groups.includes(person.group)) return false;
        if (section.key === "staff" && adminStaff && person.name === adminStaff.name) return false;
        return true;
      });
      if (!members.length) return "";
      return `
        <section class="people-section people-section-${section.key}">
          <div class="people-section-heading">
            <div>
              <span>${members.length}</span>
              <h3>${pick(section.title)}</h3>
            </div>
            <p>${pick(section.caption)}</p>
          </div>
          <div class="people-cards">
            ${members.map(personCard).join("")}
          </div>
        </section>
      `;
    })
    .join("");
}

function renderAdminContact() {
  const container = document.getElementById("admin-contact");
  const person = state.data.people.find((entry) => entry.name === "陈香淼");
  if (!person) {
    container.innerHTML = "";
    return;
  }

  const labels = {
    kicker: { en: "Lab Administration", zh: "课题组行政", es: "Administración del laboratorio" },
    title: { en: "Research Administrative Assistant", zh: "科研行政助理", es: "Asistente administrativa de investigación" },
    body: {
      en: "For onboarding, scheduling, internal coordination, reimbursements, and routine lab matters, you may also contact Xiangmiao Chen.",
      zh: "涉及入组、排期、日常协调、报销或一般课题组事务，也可以联系陈香淼。",
      es: "Para incorporación, agenda, coordinación interna, reembolsos y asuntos rutinarios del laboratorio, también puede contactarse con Xiangmiao Chen.",
    },
    cta: { en: "Email the Lab Office", zh: "联系课题组行政", es: "Contactar administración" },
  };

  container.innerHTML = `
    <article class="admin-contact-card">
      <figure class="admin-contact-photo">
        <img src="${person.image}" alt="${person.name}" loading="lazy" />
      </figure>
      <div class="admin-contact-copy">
        <span class="section-kicker">${pick(labels.kicker)}</span>
        <h3>${person.name}</h3>
        <p class="admin-role">${pick(labels.title)}</p>
        <p>${pick(labels.body)}</p>
        ${person.affiliation ? `<p class="admin-affiliation">${person.affiliation}</p>` : ""}
        <a class="button button-outline" href="mailto:${person.email}">${pick(labels.cta)}</a>
      </div>
    </article>
  `;
}

function renderPeopleSummary() {
  const summary = document.getElementById("people-summary");
  const people = state.data.people;
  const counts = {
    postdocs: people.filter((person) => person.group === "Postdoctoral Fellows").length,
    students: people.filter((person) =>
      ["PhD Students", "Master Students", "Undergraduate Students"].includes(person.group),
    ).length,
    staff: people.filter((person) => person.group === "Research Staff").length,
  };
  const labels = {
    total: { en: "Members", zh: "成员", es: "Integrantes" },
    postdocs: { en: "Postdocs", zh: "博士后", es: "Postdocs" },
    students: { en: "Students", zh: "学生", es: "Estudiantes" },
    staff: { en: "Research Staff", zh: "科研助理", es: "Personal técnico" },
    spectrum: {
      en: "Medicine · Imaging · Chemistry · Materials · AI",
      zh: "医学 · 影像 · 化学 · 材料 · AI",
      es: "Medicina · Imagen · Química · Materiales · IA",
    },
  };

  summary.innerHTML = `
    <article>
      <span>${pick(labels.total)}</span>
      <strong>${people.length}</strong>
    </article>
    <article>
      <span>${pick(labels.postdocs)}</span>
      <strong>${counts.postdocs}</strong>
    </article>
    <article>
      <span>${pick(labels.students)}</span>
      <strong>${counts.students}</strong>
    </article>
    <article>
      <span>${pick(labels.staff)}</span>
      <strong>${counts.staff}</strong>
    </article>
    <article class="people-spectrum">
      <span>${state.lang === "zh" ? "跨学科声部" : state.lang === "es" ? "Espectro" : "Disciplinary Spectrum"}</span>
      <strong>${pick(labels.spectrum)}</strong>
    </article>
  `;
}

function renderPiProfile() {
  const profile = document.getElementById("pi-profile");
  const data = state.data.piProfile;
  profile.innerHTML = `
    <article class="pi-profile-card">
      ${
        data.image
          ? `<figure class="pi-profile-photo"><img src="${data.image}" alt="${pick(data.imageAlt)}" loading="lazy" /></figure>`
          : ""
      }
      <span class="role">${pick(data.role)}</span>
      <h3>${data.name}</h3>
      <p>${pick(data.bio)}</p>
      <div class="profile-tags">
        ${data.tags.map((tag) => `<span>${pick(tag)}</span>`).join("")}
      </div>
    </article>
    <div class="profile-facts">
      ${data.facts
        .map(
          (fact) => `
            <article>
              <span>${pick(fact.label)}</span>
              <strong>${pick(fact.value)}</strong>
            </article>
          `,
        )
        .join("")}
    </div>
    <div class="profile-links">
      ${data.links
        .map(
          (link) => `
            <a href="${link.url}" target="_blank" rel="noopener noreferrer">
              ${pick(link.label)} ${externalIcon}
            </a>
          `,
        )
        .join("")}
    </div>
  `;
}

function render() {
  renderNav();
  renderSlots();
  updateLanguageButtons();
  renderMetrics();
  renderSignals();
  renderNews();
  renderTracks();
  renderResearchMap();
  renderPublications();
  renderRecentPublications();
  renderCovers();
  renderPiProfile();
  renderPeopleSummary();
  renderAdminContact();
  renderPeople();
}

function resizeCanvas() {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const rect = canvas.getBoundingClientRect();
  rhythm.width = rect.width;
  rhythm.height = rect.height;
  canvas.width = Math.floor(rect.width * ratio);
  canvas.height = Math.floor(rect.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  const count = Math.max(42, Math.floor(rect.width / 24));
  rhythm.points = Array.from({ length: count }, (_, index) => ({
    x: (index / (count - 1)) * rect.width,
    y: rect.height * (0.2 + Math.random() * 0.58),
    phase: Math.random() * Math.PI * 2,
    amp: 6 + Math.random() * 26,
    speed: 0.0028 + Math.random() * 0.0045,
  }));
}

function drawRhythm(time) {
  const { width, height, points } = rhythm;
  ctx.clearRect(0, 0, width, height);
  rhythm.beat = (Math.sin(time * 0.0032) + 1) / 2;

  ctx.lineWidth = 1;
  ctx.strokeStyle = `rgba(87, 230, 239, ${0.1 + rhythm.beat * 0.16})`;
  ctx.beginPath();
  points.forEach((point, index) => {
    const y = point.y + Math.sin(time * point.speed + point.phase) * point.amp;
    if (index === 0) ctx.moveTo(point.x, y);
    else ctx.lineTo(point.x, y);
  });
  ctx.stroke();

  for (let i = 0; i < points.length; i += 3) {
    const point = points[i];
    const y = point.y + Math.sin(time * point.speed + point.phase) * point.amp;
    const pulse = 1.2 + rhythm.beat * 2.4 + (i % 4) * 0.36;
    ctx.beginPath();
    ctx.fillStyle = i % 6 === 0 ? "rgba(201, 164, 93, 0.35)" : "rgba(87, 230, 239, 0.38)";
    ctx.arc(point.x, y, pulse, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = `rgba(255,255,255,${0.045 + rhythm.beat * 0.035})`;
  for (let x = 0; x < width; x += 120) {
    ctx.fillRect(x, height * 0.12, 1, height * 0.76);
  }

  requestAnimationFrame(drawRhythm);
}

function updateHeader() {
  header.dataset.elevated = window.scrollY > 18 ? "true" : "false";
}

function bindNavigation() {
  document.addEventListener("click", (event) => {
    const link = event.target.closest('a[href^="#"]');
    if (!link) return;
    const target = document.querySelector(link.getAttribute("href"));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    header.dataset.open = "false";
    navToggle.setAttribute("aria-expanded", "false");
  });

  navToggle.addEventListener("click", () => {
    const isOpen = header.dataset.open === "true";
    header.dataset.open = String(!isOpen);
    navToggle.setAttribute("aria-expanded", String(!isOpen));
  });
}

async function init() {
  const response = await fetch("./data/site.json", { cache: "no-store" });
  state.data = await response.json();
  render();
  bindNavigation();
  resizeCanvas();
  updateHeader();
  requestAnimationFrame(drawRhythm);
}

languageButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.lang = button.dataset.lang;
    localStorage.setItem("tian-lab-language", state.lang);
    render();
  });
});

window.addEventListener("resize", resizeCanvas);
window.addEventListener("scroll", updateHeader, { passive: true });

init().catch((error) => {
  document.body.dataset.error = "true";
  console.error("Failed to initialize Tian Lab site", error);
});

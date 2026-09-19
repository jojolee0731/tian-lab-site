/* Progressive enhancement. Research, people, and papers are in static HTML. */
(() => {
  'use strict';
  const toggle = document.querySelector('#menu-toggle');
  const nav = document.querySelector('#site-nav');
  const mobile = window.matchMedia('(max-width: 949px)');
  const closeMenu = (restoreFocus = false) => {
    nav.classList.remove('is-open');
    toggle.setAttribute('aria-expanded', 'false');
    if (restoreFocus) toggle.focus();
  };
  const syncMenu = () => {
    toggle.hidden = !mobile.matches;
    closeMenu();
  };
  if (toggle && nav) {
    document.documentElement.classList.add('js');
    syncMenu();
    mobile.addEventListener('change', syncMenu);
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      nav.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') closeMenu(true);
    });
    nav.addEventListener('click', event => {
      if (event.target.closest('a')) closeMenu();
    });
  }
  const filters = document.querySelector('.filters');
  if (filters) {
    const year = document.querySelector('#filter-year');
    const topic = document.querySelector('#filter-topic');
    const papers = [...document.querySelectorAll('#publication-list .paper-row')];
    const count = document.querySelector('#filter-count');
    const empty = document.querySelector('#no-results');
    const applyFilters = () => {
      let visible = 0;
      for (const paper of papers) {
        const show = (year.value === 'all' || paper.dataset.year === year.value)
          && (topic.value === 'all' || paper.dataset.topics.split(' ').includes(topic.value));
        paper.hidden = !show;
        if (show) visible += 1;
      }
      count.textContent = `${visible} ${count.dataset.label}`;
      empty.hidden = visible !== 0;
    };
    year.addEventListener('change', applyFilters);
    topic.addEventListener('change', applyFilters);
    document.querySelector('#reset-filters').addEventListener('click', () => {
      year.value = 'all';
      topic.value = 'all';
      applyFilters();
    });
    // Direct paper links must remain visible after navigating within this page.
    window.addEventListener('hashchange', () => {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target?.classList.contains('paper-row') && target.hidden) {
        year.value = 'all'; topic.value = 'all'; applyFilters(); target.scrollIntoView();
      }
    });
    filters.hidden = false;
    applyFilters();
  }
  document.querySelectorAll('.language-nav a').forEach(link => {
    link.addEventListener('click', () => { if (location.hash) link.hash = location.hash; });
  });
  // Preserve old single-page bookmarks while giving every section its own URL.
  const legacy = {research:'research.html', publications:'publications.html',
    'recent-publications':'publications.html', covers:'publications.html#covers',
    people:'people.html', 'pi-profile':'people.html#pi', 'admin-contact':'people.html#admin',
    'recent-publications-title':'publications.html', 'recent-publication-list':'publications.html',
    join:'join.html', contact:'collaborate.html', collaboration:'collaborate.html'};
  if (document.body.dataset.page === 'index' && Object.hasOwn(legacy, location.hash.slice(1))) {
    location.replace(legacy[location.hash.slice(1)]);
  }
  // Preserve the existing production analytics property without tracking local QA.
  if (location.hostname === 'jojolee0731.github.io' && location.pathname.startsWith('/tian-lab-site/')) {
    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    const tag = document.createElement('script');
    tag.async = true;
    tag.src = 'https://www.googletagmanager.com/gtag/js?id=G-5JWWDPMBZ6';
    document.head.appendChild(tag);
    gtag('js', new Date());
    gtag('config', 'G-5JWWDPMBZ6');
  }
})();

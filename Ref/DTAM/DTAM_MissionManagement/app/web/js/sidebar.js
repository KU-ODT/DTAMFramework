/* sidebar.js — collapsible sidebar and accordion sections */
window.ODT = window.ODT || {};

ODT.Sidebar = (function () {
  let collapsed = false;

  function init() {
    const sidebar = document.getElementById('sidebar');
    const collapseBtn = document.getElementById('sidebar-collapse');
    const toggleBtn = document.getElementById('sidebar-toggle');

    collapseBtn.addEventListener('click', () => toggle());
    toggleBtn.addEventListener('click', () => toggle());

    // Accordion sections
    document.querySelectorAll('.section-header').forEach((header) => {
      header.addEventListener('click', () => {
        const section = header.parentElement;
        section.classList.toggle('open');
      });
    });
  }

  function toggle() {
    collapsed = !collapsed;
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebar-toggle');

    if (collapsed) {
      sidebar.classList.add('collapsed');
      toggleBtn.classList.add('visible');
      document.body.classList.add('sidebar-collapsed');
    } else {
      sidebar.classList.remove('collapsed');
      toggleBtn.classList.remove('visible');
      document.body.classList.remove('sidebar-collapsed');
    }

    // Trigger map resize after animation
    setTimeout(() => {
      const map = ODT.MapManager.getMap();
      if (map) map.resize();
    }, 450);
  }

  function isCollapsed() {
    return collapsed;
  }

  return { init, toggle, isCollapsed };
})();

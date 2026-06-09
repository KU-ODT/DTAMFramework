(async () => {
  const resolvedConfig = window.AppConfigReady ? await window.AppConfigReady : config;
  const app = new MapApp(resolvedConfig);
  app.init();
  window.mapApp = app;
})();

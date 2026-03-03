(() => {
  const shellBaseUrl = window.__WORKSPACE_BASE_URL__;
  const launchBaseUrl = window.workforceLaunchContext?.baseUrl || window.workforceLaunchContext?.base_url;

  const deriveWorkspaceBase = () => {
    if (shellBaseUrl) {
      return new URL(`${shellBaseUrl.replace(/\/$/, '')}/static/`, window.location.origin);
    }
    if (launchBaseUrl) {
      return new URL(`${new URL(launchBaseUrl, window.location.href).pathname.replace(/\/$/, '')}/static/`, window.location.origin);
    }

    const match = window.location.pathname.match(/^\/workspace\/[^/]+/);
    if (match) {
      return new URL(`${match[0]}/static/`, window.location.origin);
    }

    return new URL('./static/', window.location.href);
  };

  const scriptBase = document.currentScript?.src ? new URL('.', document.currentScript.src) : deriveWorkspaceBase();
  const manifestUrl = new URL('assets/manifest.json', scriptBase);

  const appendStylesheet = (href) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  };

  const appendScript = (src) => {
    const script = document.createElement('script');
    script.src = src;
    script.defer = true;
    document.body.appendChild(script);
  };

  fetch(manifestUrl)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Unable to load frontend manifest: ${response.status}`);
      }
      return response.text();
    })
    .then((manifestText) => {
      let manifest;
      try {
        manifest = JSON.parse(manifestText);
      } catch (error) {
        const preview = manifestText.slice(0, 160);
        throw new Error(`Unable to parse frontend manifest JSON: ${error}. Preview: ${preview}`);
      }

      const entry = manifest?.entry || {};
      if (entry.css) {
        appendStylesheet(new URL(entry.css, scriptBase).toString());
      }
      if (entry.js) {
        appendScript(new URL(entry.js, scriptBase).toString());
      } else {
        throw new Error('Frontend manifest missing entry.js');
      }
    })
    .catch((error) => {
      console.error(error);
    });
})();

(() => {
  const workspaceMatch = window.location.pathname.match(/^\/workspace\/([^/]+)/);
  const basePath = workspaceMatch ? `/workspace/${workspaceMatch[1]}/` : "/";
  const base = new URL(basePath, window.location.origin);
  const manifestUrl = new URL("assets/manifest.json", base);

  const appendStylesheet = (href) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
  };

  const appendScript = (src) => {
    const script = document.createElement("script");
    script.src = src;
    script.defer = true;
    document.body.appendChild(script);
  };

  fetch(manifestUrl)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Unable to load frontend manifest: ${response.status}`);
      }
      return response.json();
    })
    .then((manifest) => {
      const entry = manifest?.entry || {};
      if (entry.css) {
        appendStylesheet(new URL(entry.css, base).toString());
      }
      if (entry.js) {
        appendScript(new URL(entry.js, base).toString());
      } else {
        throw new Error("Frontend manifest missing entry.js");
      }
    })
    .catch((error) => {
      console.error(error);
    });
})();
